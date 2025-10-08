#!/usr/bin/env python3
"""
Order queue management for automation system
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

from database import (
    DatabaseManager,
    Order,
    OrderStatus,
    OrderPriority,
    AutomationMethod,
)
from services.settings_service import SettingsService

logger = logging.getLogger(__name__)


class QueueStatus(Enum):
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"


@dataclass
class QueueMetrics:
    """Queue performance metrics"""

    total_orders: int = 0
    pending_orders: int = 0
    processing_orders: int = 0
    completed_orders: int = 0
    failed_orders: int = 0
    review_queue: int = 0
    avg_processing_time: float = 0.0
    success_rate: float = 0.0
    orders_today: int = 0
    queue_status: QueueStatus = QueueStatus.STOPPED


class OrderQueue:
    """Order queue manager with priority handling"""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.settings_service = SettingsService(db_manager)
        self.status = QueueStatus.STOPPED
        self.processing_orders: Dict[str, asyncio.Task] = {}
        self.active_agents: Dict[str, Any] = {}  # Track active agents by order_id
        self.max_concurrent = 5
        self.queue_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        self.paused = False

        # Load queue settings
        self._load_queue_settings()

    def _load_queue_settings(self):
        """Load queue settings from config"""
        try:
            system_config = self.settings_service.get_system_config()
            queue_settings = {
                "max_concurrent_orders": system_config.get("max_concurrent_orders", 5),
                "order_timeout_minutes": 30,
            }
            self.max_concurrent = queue_settings.get("max_concurrent_orders", 5)
            self.order_timeout = queue_settings.get("order_timeout_minutes", 30) * 60
            self.retry_delay = queue_settings.get("retry_delay_seconds", 60)
            self.max_queue_size = queue_settings.get("max_queue_size", 500)

            logger.info(f"Queue settings loaded: max_concurrent={self.max_concurrent}")

        except Exception as e:
            logger.error(f"Failed to load queue settings: {e}")
            # Use defaults
            self.max_concurrent = 5
            self.order_timeout = 1800  # 30 minutes
            self.retry_delay = 60
            self.max_queue_size = 500

    async def start(self):
        """Start the order queue processor"""
        if self.status == QueueStatus.RUNNING:
            logger.warning("Queue is already running")
            return

        try:
            self.status = QueueStatus.RUNNING
            self._shutdown_event.clear()

            # Start the main queue processing task
            self.queue_task = asyncio.create_task(self._process_queue())

            logger.info("Order queue started successfully")

        except Exception as e:
            logger.error(f"Failed to start order queue: {e}")
            self.status = QueueStatus.STOPPED
            raise

    async def stop(self):
        """Stop the order queue processor"""
        if self.status == QueueStatus.STOPPED:
            return

        try:
            self.status = QueueStatus.STOPPED
            self._shutdown_event.set()

            # Cancel the main queue task
            if self.queue_task and not self.queue_task.done():
                self.queue_task.cancel()
                try:
                    await self.queue_task
                except asyncio.CancelledError:
                    pass

            # Cancel all processing orders
            for order_id, task in list(self.processing_orders.items()):
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                del self.processing_orders[order_id]

            logger.info("Order queue stopped successfully")

        except Exception as e:
            logger.error(f"Failed to stop order queue: {e}")

    async def pause(self):
        """Pause the order queue (stop accepting new orders)"""
        if self.status == QueueStatus.RUNNING:
            self.status = QueueStatus.PAUSED
            self.paused = True
            logger.info("Order queue paused")

    async def resume(self):
        """Resume the order queue"""
        if self.status == QueueStatus.PAUSED:
            self.status = QueueStatus.RUNNING
            self.paused = False
            logger.info("Order queue resumed")

    async def _process_queue(self):
        """Main queue processing loop"""
        logger.info("Queue processor started")

        try:
            while not self._shutdown_event.is_set():
                try:
                    # Check if we can process more orders
                    if (
                        self.status == QueueStatus.RUNNING
                        and len(self.processing_orders) < self.max_concurrent
                    ):

                        # Get next order from database
                        order = self.db_manager.get_next_order()

                        if order:
                            # Start processing the order
                            task = asyncio.create_task(self._process_order(order))
                            self.processing_orders[order.id] = task

                            logger.info(f"Started processing order {order.id}")
                        else:
                            # No orders to process, wait a bit
                            await asyncio.sleep(5)
                    else:
                        # Queue is paused or at capacity, wait
                        await asyncio.sleep(2)

                    # Clean up completed tasks
                    await self._cleanup_completed_tasks()

                except Exception as e:
                    logger.error(f"Error in queue processor: {e}")
                    await asyncio.sleep(5)

        except asyncio.CancelledError:
            logger.info("Queue processor cancelled")
        except Exception as e:
            logger.error(f"Queue processor failed: {e}")
        finally:
            logger.info("Queue processor stopped")

    async def _cleanup_completed_tasks(self):
        """Clean up completed processing tasks"""
        completed_orders = []

        for order_id, task in self.processing_orders.items():
            if task.done():
                completed_orders.append(order_id)
                try:
                    # Get the result to handle any exceptions
                    await task
                except Exception as e:
                    logger.error(f"Order {order_id} processing failed: {e}")

        # Remove completed tasks
        for order_id in completed_orders:
            del self.processing_orders[order_id]

    async def _process_order(self, order: Order):
        """Process a single order"""
        try:
            logger.info(
                f"Started processing order {order.id} for {order.retailer} using {order.automation_method.value}"
            )

            # Basic validation: retailer URLs already validated during order creation
            logger.info(
                f"Processing order for {order.retailer} with {order.automation_method.value}"
            )
            logger.info("Configuration validation passed")

            # Create agent based on automation method
            logger.info(
                f"Getting automation config for {order.automation_method.value}"
            )
            agent_config = self.settings_service.get_automation_config(
                order.automation_method.value
            )
            logger.info(f"Agent config retrieved: {agent_config}")

            # Add AI model to config if specified
            if hasattr(order, "ai_model") and order.ai_model:
                logger.info(f"Adding AI model to config: {order.ai_model}")
                agent_config["model"] = order.ai_model
                agent_config["model_provider"] = self._get_model_provider(
                    order.ai_model
                )

            # Add db_manager to config for execution logging
            agent_config["db_manager"] = self.db_manager

            logger.info(f"Creating agent for {order.automation_method.value}...")

            # Create agent directly based on method
            # Get retailer configuration from database
            retailer_urls = self.settings_service.get_retailer_urls(order.retailer)
            default_url = next(
                (url for url in retailer_urls if url["is_default"]),
                retailer_urls[0] if retailer_urls else None,
            )

            # Get site credentials for this retailer
            site_credentials = None
            try:
                # Look for credentials in AWS Secrets Manager
                from services.secrets_manager import get_secrets_manager
                secrets_manager = get_secrets_manager()
                
                secret = secrets_manager.get_secret(order.retailer, include_password=True)
                if secret:
                    credentials = {
                        "username": secret.get("username"),
                        "password": secret.get("password"),
                        "additional_fields": secret.get("additional_fields", {})
                    }
                elif default_url:
                    # Try to search by URL if no exact name match
                    all_secrets = secrets_manager.list_secrets(include_passwords=True)
                    for secret in all_secrets:
                        if secret.get("site_url") and default_url.get("starting_url"):
                            # Check if URLs match (basic domain matching)
                            try:
                                from urllib.parse import urlparse

                                secret_domain = urlparse(secret.site_url).netloc.lower()
                                retailer_domain = urlparse(
                                    default_url["starting_url"]
                                ).netloc.lower()
                                if (
                                    secret_domain == retailer_domain
                                    or secret_domain in retailer_domain
                                    or retailer_domain in secret_domain
                                ):
                                    secrets = [secret]
                                    break
                            except Exception:
                                continue

                if secrets:
                    site_credentials = {
                        "username": secrets[0].username,
                        "password": secrets[0].password,
                        "additional_fields": secrets[0].additional_fields or {},
                        "site_name": secrets[0].site_name,
                        "site_url": secrets[0].site_url,
                    }
                    logger.info(f"Found site credentials for {order.retailer}")
                else:
                    logger.info(f"No site credentials found for {order.retailer}")
            except Exception as cred_error:
                logger.warning(f"Failed to retrieve site credentials: {cred_error}")

            retailer_config = {
                "name": order.retailer.replace("_", " ").title(),
                "base_url": default_url["starting_url"] if default_url else "",
                "automation_methods": ["strands", "nova_act"],
                "preferred_method": "nova_act",
                "status": "active",
                "credentials": site_credentials,  # Add credentials to config
            }

            if order.automation_method.value == "nova_act":
                from agents.nova_act_agent import NovaActAgent

                agent = NovaActAgent(
                    agent_config, retailer_config, db_manager=self.db_manager
                )
            elif order.automation_method.value == "strands":
                from agents.strands_agent import StrandsAgent
                from services.browser_service import get_browser_service

                browser_service = get_browser_service(agent_config, self.db_manager)
                agent = StrandsAgent(
                    agent_config,
                    retailer_config,
                    db_manager=self.db_manager,
                    browser_service=browser_service,
                )
            else:
                raise ValueError(
                    f"Unknown automation method: {order.automation_method.value}"
                )

            # Track active agent
            self.active_agents[order.id] = agent

            # Start agent session
            logger.info(f"Starting session for agent...")
            try:
                session_result = await agent.start_session(session_id=order.id)
                logger.info(f"Session started: {session_result}")
            except Exception as session_error:
                logger.error(f"Failed to start agent session: {session_error}")
                # Update order status to failed
                self.db_manager.update_order_status(
                    order_id=order.id,
                    status=OrderStatus.FAILED,
                    progress=100,
                    current_step="Processing failed due to system error",
                    error_message="Session not started",
                )
                return

            if not session_result or session_result.get("status") != "active":
                logger.error(f"Session failed to start properly: {session_result}")
                self.db_manager.update_order_status(
                    order_id=order.id,
                    status=OrderStatus.FAILED,
                    progress=100,
                    current_step="Processing failed due to system error",
                    error_message="Session initialization failed",
                )
                return

            # Progress callback for real-time updates
            async def progress_callback(progress_data):
                # Update order in database
                self.db_manager.update_order_status(
                    order_id=order.id,
                    status=OrderStatus(progress_data["status"]),
                    progress=progress_data.get("progress"),
                    current_step=progress_data.get("step"),
                    session_id=progress_data.get("session_id"),
                )

                # Broadcast update (this would be handled by WebSocket manager)
                logger.info(
                    f"Order {order.id} progress: {progress_data['progress']}% - {progress_data['step']}"
                )

            # Process the order
            result = await agent.process_order(order, progress_callback)

            # Update final status
            if result.get("success"):
                self.db_manager.update_order_status(
                    order_id=order.id,
                    status=OrderStatus.COMPLETED,
                    progress=100,
                    current_step="Order completed successfully",
                    order_confirmation_number=result.get("confirmation_number"),
                    tracking_number=result.get("tracking_number"),
                    estimated_delivery=result.get("estimated_delivery"),
                )
                logger.info(f"Order {order.id} completed successfully")

            elif result.get("status") == "requires_human":
                self.db_manager.update_order_status(
                    order_id=order.id,
                    status=OrderStatus.REQUIRES_HUMAN,
                    progress=result.get("progress", 75),
                    current_step=result.get("message", "Human intervention required"),
                    requires_human_review=True,
                    error_message=result.get("message"),
                )
                logger.warning(f"Order {order.id} requires human intervention")
                # Keep agent active for manual control - do not cleanup
                logger.info(
                    f"Keeping browser session active for manual intervention: {order.id}"
                )

            else:
                self.db_manager.update_order_status(
                    order_id=order.id,
                    status=OrderStatus.FAILED,
                    progress=100,
                    current_step="Order processing failed",
                    error_message=result.get("error", "Unknown error"),
                )
                logger.error(f"Order {order.id} failed: {result.get('error')}")

                # Clean up agent resources for failed orders with timeout
                try:
                    await asyncio.wait_for(agent.cleanup(force=True), timeout=10.0)
                except asyncio.TimeoutError:
                    logger.warning(f"Agent cleanup timed out for failed order {order.id}")
                except Exception as cleanup_error:
                    logger.error(f"Agent cleanup failed for order {order.id}: {cleanup_error}")
                finally:
                    # Always remove from active agents
                    if order.id in self.active_agents:
                        del self.active_agents[order.id]

            # Clean up agent resources only for completed orders
            if result.get("success"):
                try:
                    await asyncio.wait_for(agent.cleanup(), timeout=10.0)
                except asyncio.TimeoutError:
                    logger.warning(f"Agent cleanup timed out for successful order {order.id}")
                except Exception as cleanup_error:
                    logger.error(f"Agent cleanup failed for order {order.id}: {cleanup_error}")
                finally:
                    # Always remove from active agents
                    if order.id in self.active_agents:
                        del self.active_agents[order.id]

        except Exception as e:
            import traceback

            error_details = f"Error: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
            logger.error(f"Failed to process order {order.id}: {error_details}")

            # Create user-friendly error message
            user_friendly_error = str(e)
            if "ImportError" in str(e):
                user_friendly_error = (
                    f"Required automation packages not installed: {str(e)}"
                )
            elif "ConfigManager" in str(e):
                user_friendly_error = f"Configuration error: {str(e)}"
            elif "AgentFactory" in str(e):
                user_friendly_error = f"Agent creation failed: {str(e)}"

            # Update order status to failed
            try:
                self.db_manager.update_order_status(
                    order_id=order.id,
                    status=OrderStatus.FAILED,
                    progress=100,
                    current_step="Processing failed due to system error",
                    error_message=user_friendly_error,
                )
            except Exception as db_error:
                logger.error(f"Failed to update order status: {db_error}")

            # Clean up agent on error with timeout
            if order.id in self.active_agents:
                try:
                    agent = self.active_agents[order.id]
                    # Use asyncio.wait_for to prevent hanging
                    await asyncio.wait_for(agent.cleanup(force=True), timeout=10.0)
                except asyncio.TimeoutError:
                    logger.warning(f"Agent cleanup timed out for order {order.id}")
                except Exception as cleanup_error:
                    logger.error(
                        f"Failed to cleanup agent for order {order.id}: {cleanup_error}"
                    )
                finally:
                    # Always remove from active agents
                    if order.id in self.active_agents:
                        del self.active_agents[order.id]

    async def add_order(
        self,
        retailer: str,
        automation_method: str,
        product_name: str,
        product_url: str,
        customer_name: str,
        customer_email: str,
        shipping_address: Dict[str, Any],
        ai_model: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Add a new order to the queue"""
        try:
            # Validate inputs
            retailer_urls = self.settings_service.get_retailer_urls(retailer)
            if not retailer_urls:
                raise ValueError(
                    f"Retailer {retailer} is not configured. Please add retailer URLs in Settings."
                )

            # Convert automation method string to enum
            try:
                method_enum = AutomationMethod(automation_method)
            except ValueError:
                raise ValueError(f"Invalid automation method: {automation_method}")

            # Basic validation: retailer URLs already validated
            logger.info(f"Creating order for {retailer} with {automation_method}")

            # Check queue size
            pending_count = len(
                [
                    o
                    for o in self.db_manager.get_all_orders(status_filter=["pending"])
                    if o.status == OrderStatus.PENDING
                ]
            )
            if pending_count >= self.max_queue_size:
                raise ValueError(f"Queue is full (max {self.max_queue_size} orders)")

            # Create order in database
            order_id = self.db_manager.create_order(
                retailer=retailer,
                automation_method=method_enum,
                product_name=product_name,
                product_url=product_url,
                customer_name=customer_name,
                customer_email=customer_email,
                shipping_address=shipping_address,
                ai_model=ai_model,
                **kwargs,
            )

            logger.info(f"Added order {order_id} to queue")
            return order_id

        except Exception as e:
            logger.error(f"Failed to add order to queue: {e}")
            raise

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        try:
            # Cancel processing task if running
            if order_id in self.processing_orders:
                task = self.processing_orders[order_id]
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                del self.processing_orders[order_id]

            # Update database
            return self.db_manager.cancel_order(order_id)

        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False

    async def get_queue_metrics(self) -> QueueMetrics:
        """Get current queue metrics"""
        try:
            stats = self.db_manager.get_order_stats()

            return QueueMetrics(
                total_orders=stats.get("total_orders", 0),
                pending_orders=stats.get("pending", 0),
                processing_orders=stats.get("processing", 0),
                completed_orders=stats.get("completed", 0),
                failed_orders=stats.get("failed", 0),
                review_queue=stats.get("review_queue", 0),
                avg_processing_time=stats.get("avg_processing_time", 0.0),
                success_rate=stats.get("success_rate", 0.0),
                orders_today=stats.get("orders_today", 0),
                queue_status=self.status,
            )

        except Exception as e:
            logger.error(f"Failed to get queue metrics: {e}")
            return QueueMetrics(queue_status=self.status)

    async def get_processing_orders(self) -> List[str]:
        """Get list of currently processing order IDs"""
        return list(self.processing_orders.keys())

    async def get_active_agent(self, order_id: str):
        """Get the active agent for a specific order"""
        return self.active_agents.get(order_id)

    async def update_settings(self, settings: Dict[str, Any]):
        """Update queue settings"""
        try:
            # Update config manager
            # Update queue settings in system config
            self.settings_service.update_system_config(settings)

            # Reload settings
            self._load_queue_settings()

            logger.info("Queue settings updated successfully")

        except Exception as e:
            logger.error(f"Failed to update queue settings: {e}")
            raise

    def _get_model_provider(self, model_id: str) -> str:
        """Determine model provider from model ID"""
        if "anthropic" in model_id.lower() or "claude" in model_id.lower():
            return "anthropic"
        elif "amazon" in model_id.lower() or "nova" in model_id.lower():
            return "bedrock"
        elif "openai" in model_id.lower() or "gpt" in model_id.lower():
            return "openai"
        else:
            return "anthropic"  # Default fallback


# Global order queue instance (will be initialized in main app)
order_queue: Optional[OrderQueue] = None


def initialize_order_queue(db_manager: DatabaseManager) -> OrderQueue:
    """Initialize the global order queue"""
    global order_queue
    order_queue = OrderQueue(db_manager)
    return order_queue


def get_order_queue() -> OrderQueue:
    """Get the global order queue instance"""
    if order_queue is None:
        raise RuntimeError("Order queue not initialized")
    return order_queue
