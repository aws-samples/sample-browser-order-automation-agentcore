#!/usr/bin/env python3
"""
FastAPI backend for Order Automation System
Production-ready e-commerce automation platform with Strands agents and Playwright MCP
"""

import os
import json
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager

from fastapi import (
    FastAPI,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    BackgroundTasks,
    Response,
    File,
    UploadFile,
)
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from enum import Enum

# Import our modules
from database import (
    DatabaseManager,
    Order,
    OrderStatus,
    OrderPriority,
    AutomationMethod,
)
from config_manager import ConfigManager
from order_queue import OrderQueue, initialize_order_queue
from agentcore_manager import agentcore_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global instances
db_manager = None
order_queue = None
config_manager = None


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                # Remove dead connections
                self.active_connections.remove(connection)


manager = ConnectionManager()


# Pydantic models for API
class ProductInfo(BaseModel):
    url: str
    name: str
    size: Optional[str] = None
    color: Optional[str] = None
    quantity: int = 1
    price: Optional[float] = None


class ShippingAddress(BaseModel):
    first_name: str
    last_name: str
    address_line_1: str
    city: str
    state: str
    postal_code: str
    country: str = "US"
    phone: Optional[str] = None


class PaymentInfo(BaseModel):
    payment_token: str
    cardholder_name: str


class CreateOrderRequest(BaseModel):
    retailer: str
    automation_method: str
    ai_model: Optional[str] = "us.anthropic.claude-sonnet-4-20250514-v1:0"
    product: ProductInfo
    customer_name: str
    customer_email: str
    shipping_address: ShippingAddress
    payment_info: Optional[PaymentInfo] = None
    priority: str = "normal"
    instructions: Optional[str] = None


class UpdateOrderRequest(BaseModel):
    status: Optional[str] = None
    human_review_notes: Optional[str] = None


class SystemConfigRequest(BaseModel):
    config_key: str
    config_value: Any


# Application lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global db_manager, order_queue

    try:
        # Initialize database
        db_manager = DatabaseManager()
        logger.info("Database initialized")

        # Initialize config manager with database connection
        global config_manager
        config_manager = ConfigManager(db_manager=db_manager)
        logger.info("Configuration manager initialized")

        # Initialize order queue
        global order_queue
        order_queue = initialize_order_queue(db_manager, config_manager)
        await order_queue.start()
        logger.info("Order queue started")

        yield

    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        raise
    finally:
        # Shutdown
        if order_queue:
            await order_queue.stop()
            logger.info("Order queue stopped")


# Create FastAPI app
app = FastAPI(
    title="Order Automation System",
    description="Production-ready e-commerce automation platform",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for screenshots
screenshots_dir = os.path.join(os.path.dirname(__file__), 'static', 'screenshots')
os.makedirs(screenshots_dir, exist_ok=True)
app.mount("/api/screenshots", StaticFiles(directory=screenshots_dir), name="screenshots")


# Removed duplicate live-view endpoint - using the one below that properly handles order status


# Broadcast helper
async def broadcast_update(data: Dict[str, Any]):
    """Broadcast update to all connected WebSocket clients"""
    message = json.dumps(data)
    await manager.broadcast(message)


# API Routes


@app.get("/")
async def root():
    return {"message": "Order Automation System API", "version": "1.0.0"}


@app.get("/favicon.ico")
async def favicon():
    """Return a simple favicon response"""
    return Response(status_code=204)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check database connection
        stats = db_manager.get_order_stats()

        # Check queue status
        queue_metrics = await order_queue.get_queue_metrics()

        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "database": "connected",
            "queue_status": queue_metrics.queue_status.value,
            "total_orders": stats.get("total_orders", 0),
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")


# Order Management
@app.post("/api/orders")
async def create_order(request: CreateOrderRequest, background_tasks: BackgroundTasks):
    """Create a new order"""
    try:
        # Validate retailer and automation method
        if not config_manager.is_retailer_supported(request.retailer):
            raise HTTPException(
                status_code=400, detail=f"Retailer {request.retailer} is not supported"
            )

        if not config_manager.validate_order_config(
            request.retailer, request.automation_method
        ):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid configuration for {request.retailer} with {request.automation_method}",
            )

        # Convert priority
        try:
            priority = OrderPriority(request.priority.upper())
        except ValueError:
            priority = OrderPriority.NORMAL

        # Convert automation method
        try:
            automation_method = AutomationMethod(request.automation_method)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid automation method: {request.automation_method}",
            )

        # Handle payment info - provide default if not provided
        payment_token = (
            request.payment_info.payment_token
            if request.payment_info
            else f'tok_demo_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
        )

        # Create order
        order_id = await order_queue.add_order(
            retailer=request.retailer,
            automation_method=request.automation_method,
            ai_model=request.ai_model,
            product_name=request.product.name,
            product_url=request.product.url,
            customer_name=request.customer_name,
            customer_email=request.customer_email,
            shipping_address=request.shipping_address.dict(),
            product_size=request.product.size,
            product_color=request.product.color,
            product_price=request.product.price,
            payment_token=payment_token,
            priority=priority,
            instructions=request.instructions,
        )

        # Get created order
        order = db_manager.get_order(order_id)

        # Broadcast order creation
        await broadcast_update(
            {"type": "order_created", "order": order.to_dict() if order else None}
        )

        return {"order_id": order_id, "status": "created"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create order: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/orders")
async def get_orders(
    limit: int = 50, status: Optional[str] = None, retailer: Optional[str] = None
):
    """Get orders with optional filtering"""
    try:
        status_filter = [status] if status else None
        orders = db_manager.get_all_orders(
            limit=limit, status_filter=status_filter, retailer_filter=retailer
        )

        return {"orders": [order.to_dict() for order in orders], "total": len(orders)}

    except Exception as e:
        logger.error(f"Failed to get orders: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/orders/{order_id}")
async def get_order(order_id: str):
    """Get specific order"""
    try:
        order = db_manager.get_order(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        order_dict = order.to_dict()
        
        # Add formatted error information for failed orders
        if order.status == OrderStatus.FAILED and order.error_message:
            order_dict["error_details"] = {
                "message": order.error_message,
                "timestamp": order.updated_at.isoformat() if order.updated_at else None,
                "step": order.current_step or "Unknown step"
            }

        return order_dict

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get order {order_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/orders/{order_id}")
async def update_order(order_id: str, request: UpdateOrderRequest):
    """Update order (for human review)"""
    try:
        order = db_manager.get_order(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        # Update order status if provided
        if request.status:
            try:
                status = OrderStatus(request.status.upper())
                db_manager.update_order_status(
                    order_id=order_id,
                    status=status,
                    human_review_notes=request.human_review_notes,
                )
            except ValueError:
                raise HTTPException(
                    status_code=400, detail=f"Invalid status: {request.status}"
                )

        # Get updated order
        updated_order = db_manager.get_order(order_id)

        # Broadcast update
        await broadcast_update(
            {
                "type": "order_updated",
                "order": updated_order.to_dict() if updated_order else None,
            }
        )

        return updated_order.to_dict() if updated_order else None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update order {order_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/orders/{order_id}/live-view")
async def get_order_live_view(order_id: str):
    """Get live view URL for an active order"""
    try:
        order = db_manager.get_order(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        # Return order info even if not processing - let frontend handle gracefully
        response_data = {
            "order_id": order_id,
            "status": order.status.value,
            "automation_method": order.automation_method.value if order.automation_method else None,
            "live_view_url": None,
            "live_view_available": False,
            "message": None
        }
        
        # Only try to get live view if order is processing
        if order.status == OrderStatus.PROCESSING:
            try:
                # Get the active agent from the queue
                active_agent = await order_queue.get_active_agent(order_id)
                if active_agent and hasattr(active_agent, 'get_live_view_url'):
                    try:
                        live_view_info = active_agent.get_live_view_url()
                        if live_view_info and isinstance(live_view_info, dict) and live_view_info.get("url"):
                            response_data.update({
                                "live_view_url": live_view_info["url"],
                                "live_view_session_id": live_view_info.get("session_id", order_id),
                                "live_view_type": live_view_info.get("type", "dcv"),
                                "live_view_headers": live_view_info.get("headers"),
                                "live_view_available": True,
                                "message": "Live view is available"
                            })
                        elif isinstance(live_view_info, str):
                            # Backward compatibility for string URLs
                            response_data.update({
                                "live_view_url": live_view_info,
                                "live_view_session_id": order_id,
                                "live_view_type": "dcv",
                                "live_view_available": True,
                                "message": "Live view is available"
                            })
                        else:
                            response_data["message"] = "Live view not supported by this automation method"
                    except Exception as url_error:
                        logger.warning(f"Failed to get live view URL for order {order_id}: {url_error}")
                        response_data["message"] = "Live view temporarily unavailable"
                else:
                    response_data["message"] = "No active agent found for this order"
            except Exception as agent_error:
                logger.warning(f"Failed to get active agent for order {order_id}: {agent_error}")
                response_data["message"] = "Agent information temporarily unavailable"
        else:
            response_data["message"] = f"Live view only available for processing orders. Current status: {order.status.value}"
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get live view for order {order_id}: {e}")
        # Return error info instead of raising exception
        return {
            "order_id": order_id,
            "status": "error",
            "live_view_url": None,
            "live_view_available": False,
            "message": f"Error retrieving live view: {str(e)}"
        }


@app.get("/api/debug/active-agents")
async def get_active_agents():
    """Debug endpoint to check active agents"""
    try:
        active_agents = {}
        for order_id, agent in order_queue.active_agents.items():
            active_agents[order_id] = {
                "type": type(agent).__name__,
                "has_get_presigned_url": hasattr(agent, 'get_presigned_url'),
                "session_id": getattr(agent, 'session_id', None)
            }
        return {
            "active_agents": active_agents,
            "processing_orders": list(order_queue.processing_orders.keys())
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/orders/{order_id}/presigned-url")
async def get_presigned_url(order_id: str):
    """Get presigned URL for DCV connection via LiveViewService"""
    try:
        order = db_manager.get_order(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        # Use LiveViewService for presigned URL generation
        try:
            from services.live_view_service import get_live_view_service
            
            # Get automation config for LiveViewService
            config = config_manager.get_automation_config(order.automation_method.value)
            if not config:
                raise HTTPException(status_code=500, detail="Automation configuration not found")
            
            # Get or create live view service
            live_view_service = get_live_view_service(config, db_manager)
            
            # Try to get existing session or create new one
            live_session_id = live_view_service.get_session_for_order(order_id)
            if not live_session_id:
                logger.info(f"Creating new live view session for order {order_id}")
                live_session_id = live_view_service.create_live_session(
                    order_id, 
                    order.automation_method.value
                )
            
            if not live_session_id:
                raise HTTPException(status_code=503, detail="Failed to create live view session")
            
            # Get presigned URL
            presigned_url = live_view_service.get_presigned_url(live_session_id, expires=300)
            
            if not presigned_url:
                raise HTTPException(status_code=503, detail="Failed to generate presigned URL")
            
            return {
                "order_id": order_id,
                "sessionId": live_session_id,
                "presignedUrl": presigned_url,
                "authToken": live_session_id,
                "expires": 300
            }
            
        except HTTPException:
            raise
        except Exception as service_error:
            logger.error(f"LiveViewService error for order {order_id}: {service_error}")
            raise HTTPException(status_code=500, detail=f"Live view service error: {str(service_error)}")
        else:
            raise HTTPException(status_code=400, detail=f"Presigned URL only available for processing orders. Current status: {order.status.value}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get presigned URL for order {order_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/live-view/sessions")
async def list_live_sessions():
    """List all active live view sessions"""
    try:
        from services.live_view_service import get_live_view_service
        
        # Get default config for service access
        config = config_manager.get_automation_config("strands_playwright_mcp")
        if not config:
            raise HTTPException(status_code=500, detail="Configuration not available")
        
        live_view_service = get_live_view_service(config, db_manager)
        sessions = live_view_service.list_active_sessions()
        
        return {
            "sessions": sessions,
            "count": len(sessions)
        }
        
    except Exception as e:
        logger.error(f"Failed to list live sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/live-view/sessions/{session_id}/status")
async def get_live_session_status(session_id: str):
    """Get status of a specific live view session"""
    try:
        from services.live_view_service import get_live_view_service
        
        # Get default config for service access
        config = config_manager.get_automation_config("strands_playwright_mcp")
        if not config:
            raise HTTPException(status_code=500, detail="Configuration not available")
        
        live_view_service = get_live_view_service(config, db_manager)
        status = live_view_service.get_session_status(session_id)
        
        if not status.get("exists"):
            raise HTTPException(status_code=404, detail="Live view session not found")
        
        return status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get live session status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/live-view/sessions/{session_id}")
async def terminate_live_session(session_id: str):
    """Terminate a live view session"""
    try:
        from services.live_view_service import get_live_view_service
        
        # Get default config for service access
        config = config_manager.get_automation_config("strands_playwright_mcp")
        if not config:
            raise HTTPException(status_code=500, detail="Configuration not available")
        
        live_view_service = get_live_view_service(config, db_manager)
        success = live_view_service.terminate_session(session_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Live view session not found")
        
        return {"message": f"Live view session {session_id} terminated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to terminate live session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/orders/{order_id}/session-replay")
async def get_session_replay(order_id: str):
    """Get session replay information for an order"""
    try:
        order = db_manager.get_order(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        # Get session replay info from database
        replay_info = db_manager.get_session_replay_info(order_id)
        
        if not replay_info.get("enabled") or not replay_info.get("s3_bucket"):
            raise HTTPException(
                status_code=404, 
                detail="Session replay not available for this order"
            )
        
        return {
            "order_id": order_id,
            "session_id": replay_info.get("session_id"),
            "s3_bucket": replay_info.get("s3_bucket"),
            "s3_prefix": replay_info.get("s3_prefix"),
            "replay_available": True,
            "automation_method": order.automation_method
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get session replay for order {order_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/orders/{order_id}/session-replay/status")
async def get_session_replay_status(order_id: str):
    """Get detailed session replay status and metadata"""
    try:
        order = db_manager.get_order(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        # Get session replay info from database
        replay_info = db_manager.get_session_replay_info(order_id)
        
        if not replay_info.get("enabled"):
            return {
                "order_id": order_id,
                "replay_available": False,
                "reason": "Session replay was not enabled for this order",
                "automation_method": order.automation_method
            }
        
        # Check if S3 data exists (this would require AWS SDK in a real implementation)
        # For now, we'll assume it exists if the database has the info
        s3_bucket = replay_info.get("s3_bucket")
        s3_prefix = replay_info.get("s3_prefix")
        session_id = replay_info.get("session_id")
        
        if not s3_bucket or not s3_prefix:
            return {
                "order_id": order_id,
                "replay_available": False,
                "reason": "Session replay S3 configuration is incomplete",
                "automation_method": order.automation_method
            }
        
        return {
            "order_id": order_id,
            "session_id": session_id,
            "s3_bucket": s3_bucket,
            "s3_prefix": s3_prefix,
            "replay_available": True,
            "automation_method": order.automation_method,
            "cli_commands": {
                "view_specific": f"python view_recordings.py --bucket {s3_bucket} --prefix {s3_prefix} --session {session_id}",
                "view_latest": f"python view_recordings.py --bucket {s3_bucket} --prefix {s3_prefix}",
                "interactive": "python -m live_view_sessionreplay.browser_interactive_session"
            },
            "documentation_url": "https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore-browser-observability.html"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get session replay status for order {order_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/orders/{order_id}/retry")
async def retry_order(order_id: str, background_tasks: BackgroundTasks):
    """Retry a failed order"""
    try:
        order = db_manager.get_order(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        if order.status not in [OrderStatus.FAILED, OrderStatus.CANCELLED]:
            raise HTTPException(
                status_code=400, detail="Only failed or cancelled orders can be retried"
            )

        # Reset order status to pending
        db_manager.update_order_status(order_id, OrderStatus.PENDING)

        # Add back to queue
        background_tasks.add_task(order_queue.process_order, order_id)

        # Broadcast update
        await broadcast_update({"type": "order_retried", "order_id": order_id})

        return {"message": "Order queued for retry", "order_id": order_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retry order {order_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/orders/{order_id}")
async def cancel_order(order_id: str):
    """Cancel an order"""
    try:
        success = await order_queue.cancel_order(order_id)
        if not success:
            raise HTTPException(
                status_code=404, detail="Order not found or cannot be cancelled"
            )

        # Broadcast cancellation
        await broadcast_update({"type": "order_cancelled", "order_id": order_id})

        return {"message": "Order cancelled successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel order {order_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/orders/cleanup/completed")
async def delete_completed_orders():
    """Delete all completed and failed orders"""
    try:
        deleted_count = db_manager.delete_completed_orders()

        return {
            "message": f"Deleted {deleted_count} completed orders",
            "deleted_count": deleted_count,
        }

    except Exception as e:
        logger.error(f"Failed to delete completed orders: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/orders/upload-csv")
async def upload_orders_csv(
    file: UploadFile = File(...), background_tasks: BackgroundTasks = BackgroundTasks()
):
    """Upload CSV file to create multiple orders"""
    try:
        if not file.filename.endswith(".csv"):
            raise HTTPException(status_code=400, detail="File must be a CSV")

        # Read CSV content
        content = await file.read()
        csv_content = content.decode("utf-8")

        # Parse CSV
        import csv
        import io

        csv_reader = csv.DictReader(io.StringIO(csv_content))
        created_orders = []

        for row in csv_reader:
            try:
                # Create order from CSV row
                order_data = {
                    "customer_name": row.get("customer_name", "Demo Customer").strip(),
                    "customer_email": row.get(
                        "customer_email", "demo@example.com"
                    ).strip(),
                    "retailer": row.get("retailer", "farfetch").strip(),
                    "automation_method": row.get(
                        "automation_method", "strands_browser"
                    ).strip(),
                    "ai_model": row.get(
                        "ai_model", "us.anthropic.claude-sonnet-4-20250514-v1:0"
                    ).strip(),
                    "product": {
                        "url": row.get(
                            "product_url", row.get("curateditem_url", "")
                        ).strip(),
                        "name": row.get("product_name", row.get("name", "")).strip(),
                        "size": row.get("size", "").strip() or None,
                        "color": row.get("color", "").strip() or None,
                        "quantity": int(row.get("quantity", 1)),
                        "price": (
                            float(row.get("price", 0))
                            if row.get("price", "").strip()
                            else None
                        ),
                    },
                    "shipping_address": {
                        "first_name": row.get("shipping_first_name", "Demo").strip(),
                        "last_name": row.get("shipping_last_name", "Customer").strip(),
                        "address_line_1": row.get(
                            "shipping_address_1", "123 Main St"
                        ).strip(),
                        "address_line_2": row.get("shipping_address_2", "").strip()
                        or None,
                        "city": row.get("shipping_city", "New York").strip(),
                        "state": row.get("shipping_state", "NY").strip(),
                        "postal_code": row.get("shipping_postal_code", "10001").strip(),
                        "country": row.get("shipping_country", "US").strip(),
                    },
                    "payment_info": {
                        "payment_token": row.get(
                            "payment_token",
                            f'tok_demo_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
                        ).strip(),
                        "cardholder_name": row.get(
                            "cardholder_name",
                            row.get("customer_name", "Demo Customer"),
                        ).strip(),
                    },
                    "priority": row.get("priority", "normal").strip(),
                    "instructions": row.get("instructions", "").strip() or None,
                }

                # Validate required fields (skip validation if defaults are used)
                required_product_fields = ["url", "name"]
                for field in required_product_fields:
                    if not order_data["product"].get(field):
                        raise ValueError(f"Missing required product field: {field}")

                # Convert priority
                try:
                    priority = OrderPriority(order_data["priority"].upper())
                except ValueError:
                    priority = OrderPriority.NORMAL

                # Create order
                order_id = await order_queue.add_order(
                    retailer=order_data["retailer"],
                    automation_method=order_data["automation_method"],
                    ai_model=order_data["ai_model"],
                    product_name=order_data["product"]["name"],
                    product_url=order_data["product"]["url"],
                    customer_name=order_data["customer_name"],
                    customer_email=order_data["customer_email"],
                    shipping_address=order_data["shipping_address"],
                    product_size=order_data["product"]["size"],
                    product_color=order_data["product"]["color"],
                    product_price=order_data["product"]["price"],
                    payment_token=order_data["payment_info"]["payment_token"],
                    priority=priority,
                    instructions=order_data["instructions"],
                )

                created_orders.append(order_id)

            except Exception as e:
                logger.error(f"Failed to create order from CSV row: {e}")
                continue

        return {
            "message": f"Created {len(created_orders)} orders from CSV",
            "created_count": len(created_orders),
            "order_ids": created_orders,
        }

    except Exception as e:
        logger.error(f"Failed to upload CSV: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Queue Management
@app.get("/api/queue/metrics")
async def get_queue_metrics():
    """Get queue metrics and statistics"""
    try:
        metrics = await order_queue.get_queue_metrics()
        return {
            "queue_status": metrics.queue_status.value,
            "total_orders": metrics.total_orders,
            "pending_orders": metrics.pending_orders,
            "processing_orders": metrics.processing_orders,
            "completed_orders": metrics.completed_orders,
            "failed_orders": metrics.failed_orders,
            "review_queue": metrics.review_queue,
            "avg_processing_time": metrics.avg_processing_time,
            "success_rate": metrics.success_rate,
            "orders_today": metrics.orders_today,
        }

    except Exception as e:
        logger.error(f"Failed to get queue metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/queue/pause")
async def pause_queue():
    """Pause the order queue"""
    try:
        await order_queue.pause()
        return {"message": "Queue paused successfully"}

    except Exception as e:
        logger.error(f"Failed to pause queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/queue/resume")
async def resume_queue():
    """Resume the order queue"""
    try:
        await order_queue.resume()
        return {"message": "Queue resumed successfully"}

    except Exception as e:
        logger.error(f"Failed to resume queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/queue/status")
async def get_queue_status():
    """Get current queue status"""
    try:
        status = "active"  # Default status
        if hasattr(order_queue, "is_paused") and order_queue.is_paused:
            status = "paused"
        elif hasattr(order_queue, "paused") and order_queue.paused:
            status = "paused"

        return {"status": status}

    except Exception as e:
        logger.error(f"Failed to get queue status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Performance Metrics
@app.get("/api/metrics/performance")
async def get_performance_metrics():
    """Get system performance metrics"""
    try:
        # Get queue metrics
        queue_metrics = await order_queue.get_queue_metrics()

        # Calculate performance metrics
        total_orders = queue_metrics.total_orders
        success_rate = queue_metrics.success_rate
        avg_processing_time = queue_metrics.avg_processing_time

        # Get agent performance (if available)
        agent_performance = {
            "nova_agent": {
                "success_rate": 0.85,
                "avg_processing_time": 120,
                "total_processed": total_orders // 2 if total_orders > 0 else 0,
            },
            "playwright_mcp": {
                "success_rate": 0.78,
                "avg_processing_time": 180,
                "total_processed": total_orders // 2 if total_orders > 0 else 0,
            },
        }

        return {
            "metrics": {
                "overall_metrics": {
                    "total_orders": total_orders,
                    "success_rate": success_rate,
                    "avg_processing_time": avg_processing_time,
                    "orders_today": queue_metrics.orders_today,
                },
                "agent_performance": agent_performance,
                "queue_status": queue_metrics.queue_status.value,
                "timestamp": datetime.now().isoformat(),
            }
        }

    except Exception as e:
        logger.error(f"Failed to get performance metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# AgentCore Browser Management
@app.get("/api/agentcore/browsers")
async def get_browsers(region: str = "us-west-2"):
    """Get all AgentCore Browsers"""
    try:
        browsers = await agentcore_manager.get_browsers(region)
        return {"browsers": browsers}

    except Exception as e:
        logger.error(f"Failed to get browsers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agentcore/browsers")
async def create_browser(request: dict):
    """Create a new AgentCore Browser"""
    try:
        region = request.get("region", "us-west-2")
        name = request.get("name")
        description = request.get("description")
        recording_enabled = request.get("recording_enabled", True)
        s3_bucket = request.get("s3_bucket", "sanghwa-oregon")
        s3_prefix = request.get("s3_prefix", "videos/")

        browser = await agentcore_manager.create_browser(
            region=region,
            name=name,
            description=description,
            recording_enabled=recording_enabled,
            s3_bucket=s3_bucket,
            s3_prefix=s3_prefix,
        )

        return browser

    except Exception as e:
        logger.error(f"Failed to create browser: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agentcore/browsers/{browser_id}")
async def get_browser(browser_id: str):
    """Get specific browser details"""
    try:
        browser = await agentcore_manager.get_browser(browser_id)

        if not browser:
            raise HTTPException(status_code=404, detail="Browser not found")

        return browser

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get browser: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/agentcore/browsers/{browser_id}")
async def delete_browser(browser_id: str):
    """Delete an AgentCore Browser"""
    try:
        success = await agentcore_manager.delete_browser(browser_id)

        if not success:
            raise HTTPException(status_code=404, detail="Browser not found")

        return {"message": f"Browser {browser_id} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete browser: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agentcore/browsers/{browser_id}/sessions")
async def get_browser_sessions(browser_id: str):
    """Get sessions for an AgentCore Browser"""
    try:
        sessions = await agentcore_manager.get_browser_sessions(browser_id)
        return {"sessions": sessions}

    except Exception as e:
        logger.error(f"Failed to get browser sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agentcore/browsers/{browser_id}/sessions")
async def create_browser_session(browser_id: str):
    """Create a new session for an AgentCore Browser"""
    try:
        session = await agentcore_manager.create_session(browser_id)

        return session

    except Exception as e:
        logger.error(f"Failed to create browser session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/agentcore/sessions/{session_id}")
async def delete_browser_session(session_id: str):
    """Delete a browser session"""
    try:
        success = await agentcore_manager.delete_session(session_id)

        if not success:
            raise HTTPException(status_code=404, detail="Browser session not found")

        return {"message": f"Browser session {session_id} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete browser session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Configuration Management
@app.get("/api/config/retailers")
async def get_retailers():
    """Get supported retailers"""
    try:
        retailers = config_manager.get_supported_retailers()
        retailer_configs = {}

        for retailer in retailers:
            config = config_manager.get_retailer_config(retailer)
            if config:
                retailer_configs[retailer] = {
                    "name": config.get("name"),
                    "base_url": config.get("base_url"),
                    "automation_methods": config.get("automation_methods", []),
                    "preferred_method": config.get("preferred_method"),
                    "status": config.get("status", "active"),
                    "priority": config.get("priority", 999),
                    "requires_account": config.get("requires_account", False),
                }

        return {"supported_retailers": retailers, "retailer_configs": retailer_configs}

    except Exception as e:
        logger.error(f"Failed to get retailers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/config/automation-methods")
async def get_automation_methods():
    """Get available automation methods"""
    try:
        return {
            "automation_methods": [
                {
                    "id": "strands_browser",
                    "name": "Strands + Browser Tools + AgentCore Browser",
                    "description": "Reliable automation using Strands agent with browser tools and AgentCore Browser",
                },
                {
                    "id": "nova_act",
                    "name": "Nova Act + AgentCore Browser",
                    "description": "Advanced AI-powered automation using Nova Act with AgentCore Browser",
                },
                {
                    "id": "strands_playwright_mcp",
                    "name": "Strands + Playwright MCP + AgentCore Browser",
                    "description": "Structured browser automation with Strands, Playwright MCP, and AgentCore Browser",
                },
            ]
        }

    except Exception as e:
        logger.error(f"Failed to get automation methods: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/config/system")
async def get_system_config():
    """Get system configuration"""
    try:
        return config_manager.get_all_configs()

    except Exception as e:
        logger.error(f"Failed to get system config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/config/system")
async def update_system_config(request: SystemConfigRequest):
    """Update system configuration"""
    try:
        config_manager.update_system_config(request.config_key, request.config_value)

        # If queue settings were updated, reload them
        if request.config_key == "queue_settings":
            await order_queue.update_settings(request.config_value)

        return {"message": "Configuration updated successfully"}

    except Exception as e:
        logger.error(f"Failed to update system config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Session Management
@app.get("/api/sessions")
async def get_sessions():
    """Get browser sessions status"""
    try:
        # Mock session data for now - in real implementation this would come from browser session manager
        sessions = [
            {
                "id": "session_1",
                "status": "active",
                "retailer": "farfetch",
                "created_at": datetime.now().isoformat(),
                "last_activity": datetime.now().isoformat(),
                "orders_processed": 3,
                "current_order": None,
            },
            {
                "id": "session_2",
                "status": "idle",
                "retailer": "net_a_porter",
                "created_at": datetime.now().isoformat(),
                "last_activity": datetime.now().isoformat(),
                "orders_processed": 1,
                "current_order": None,
            },
        ]

        return {
            "sessions": sessions,
            "total": len(sessions),
            "active_count": len([s for s in sessions if s["status"] == "active"]),
            "idle_count": len([s for s in sessions if s["status"] == "idle"]),
        }

    except Exception as e:
        logger.error(f"Failed to get sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Human Review
@app.get("/api/review/queue")
async def get_review_queue():
    """Get orders requiring human review"""
    try:
        orders = db_manager.get_all_orders(status_filter=["requires_human"], limit=50)

        return {"orders": [order.to_dict() for order in orders], "total": len(orders)}

    except Exception as e:
        logger.error(f"Failed to get review queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/review/{order_id}/resolve")
async def resolve_review(order_id: str, request: UpdateOrderRequest):
    """Resolve human review for an order"""
    try:
        order = db_manager.get_order(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        if order.status != OrderStatus.REQUIRES_HUMAN:
            raise HTTPException(
                status_code=400, detail="Order does not require human review"
            )

        # Update order status
        status = (
            OrderStatus(request.status.upper())
            if request.status
            else OrderStatus.COMPLETED
        )
        db_manager.update_order_status(
            order_id=order_id,
            status=status,
            requires_human_review=False,
            human_review_notes=request.human_review_notes,
        )

        # Get updated order
        updated_order = db_manager.get_order(order_id)

        # Broadcast update
        await broadcast_update(
            {
                "type": "review_resolved",
                "order": updated_order.to_dict() if updated_order else None,
            }
        )

        return updated_order.to_dict() if updated_order else None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resolve review for order {order_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Test endpoints for demo
@app.post("/api/test/sample-order")
async def create_sample_order(automation_method: str = "strands_browser"):
    """Create a sample order for testing"""
    try:
        # Sample order data
        sample_order = {
            "retailer": "farfetch",
            "automation_method": automation_method,
            "product": {
                "url": "https://www.farfetch.com/shopping/women/gucci-gg-marmont-small-matelasse-shoulder-bag-item-12345.aspx",
                "name": "Gucci GG Marmont Small Matelassé Shoulder Bag",
                "size": None,
                "color": "Black",
                "quantity": 1,
                "price": 1890.00,
            },
            "customer_name": "Jane Doe",
            "customer_email": "jane.doe@example.com",
            "shipping_address": {
                "first_name": "Jane",
                "last_name": "Doe",
                "address_line_1": "123 Main St",
                "city": "New York",
                "state": "NY",
                "postal_code": "10001",
                "country": "US",
                "phone": "555-123-4567",
            },
            "payment_info": {
                "payment_token": "tok_sample_12345",
                "cardholder_name": "Jane Doe",
            },
            "priority": "normal",
        }

        # Create the order using the existing endpoint logic
        order_id = await order_queue.add_order(
            retailer=sample_order["retailer"],
            automation_method=automation_method,
            product_name=sample_order["product"]["name"],
            product_url=sample_order["product"]["url"],
            customer_name=sample_order["customer_name"],
            customer_email=sample_order["customer_email"],
            shipping_address=sample_order["shipping_address"],
            product_size=sample_order["product"]["size"],
            product_color=sample_order["product"]["color"],
            product_price=sample_order["product"]["price"],
            payment_token=sample_order["payment_info"]["payment_token"],
            priority=OrderPriority.NORMAL,
        )

        # Get created order
        order = db_manager.get_order(order_id)

        # Broadcast order creation
        await broadcast_update(
            {"type": "order_created", "order": order.to_dict() if order else None}
        )

        return {
            "order_id": order_id,
            "status": "created",
            "message": f"Sample order created with {automation_method}",
        }

    except Exception as e:
        logger.error(f"Failed to create sample order: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/automation/compare")
async def compare_automation_methods():
    """Compare automation methods by creating sample orders with both"""
    try:
        # Create sample orders with both methods
        results = []

        for method in ["strands_browser", "strands_playwright_mcp", "nova_act"]:
            try:
                order_id = await order_queue.add_order(
                    retailer="farfetch",
                    automation_method=method,
                    product_name="Gucci GG Marmont Small Matelassé Shoulder Bag",
                    product_url="https://www.farfetch.com/shopping/women/gucci-gg-marmont-small-matelasse-shoulder-bag-item-12345.aspx",
                    customer_name="Jane Doe",
                    customer_email="jane.doe@example.com",
                    shipping_address={
                        "first_name": "Jane",
                        "last_name": "Doe",
                        "address_line_1": "123 Main St",
                        "city": "New York",
                        "state": "NY",
                        "postal_code": "10001",
                        "country": "US",
                        "phone": "555-123-4567",
                    },
                    product_color="Black",
                    product_price=1890.00,
                    payment_token="tok_sample_12345",
                    priority=OrderPriority.NORMAL,
                )
                results.append({"method": method, "order_id": order_id})
            except Exception as e:
                logger.error(f"Failed to create {method} order: {e}")
                results.append({"method": method, "error": str(e)})

        return {
            "comparison_id": f"comp_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "results": results,
            "message": "Comparison orders created successfully",
        }

    except Exception as e:
        logger.error(f"Failed to create comparison orders: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
            # Echo back for heartbeat
            await websocket.send_text(
                json.dumps(
                    {"type": "heartbeat", "timestamp": datetime.now().isoformat()}
                )
            )
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(status_code=404, content={"detail": "Resource not found"})


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
