#!/usr/bin/env python3
"""
Nova Act + AgentCore Browser Agent
Simple integration for e-commerce automation
"""

import os
import logging
import base64
import uuid
import asyncio
from datetime import datetime
from typing import Dict, Any

try:
    from bedrock_agentcore.tools.browser_client import browser_session
    from nova_act import NovaAct
    from strands import Agent
    from strands.models import BedrockModel
except ImportError as e:
    print(f"Warning: Required packages not installed: {e}")
    browser_session = None
    NovaAct = None
    Agent = None
    BedrockModel = None

logger = logging.getLogger(__name__)


class NovaActAgent:
    """Nova Act + AgentCore Browser Agent for e-commerce automation"""

    def __init__(
        self, config: Dict[str, Any], retailer_config: Dict[str, Any], db_manager=None
    ):
        self.config = config
        self.retailer_config = retailer_config
        self.db_manager = db_manager
        self.session_id = None
        self.agentcore_client = None
        self.agentcore_context = None
        self.nova_session = None
        self.strands_agent = None
        self.api_key = os.getenv(
            "NOVA_ACT_API_KEY", "46775fb2-8640-408c-8a94-761b2bfd0d80"
        )

        # Create screenshots directory
        self.screenshots_dir = os.path.join(
            os.path.dirname(__file__), "..", "static", "screenshots"
        )
        os.makedirs(self.screenshots_dir, exist_ok=True)

        if not browser_session or not NovaAct or not Agent or not BedrockModel:
            raise ImportError("Required packages not available")

    def _add_log(self, level: str, message: str, step: str = None):
        """Add execution log entry"""
        if self.db_manager and self.session_id:
            try:
                self.db_manager.add_execution_log(self.session_id, level, message, step)
            except Exception as e:
                logger.error(f"Failed to add execution log: {e}")
        logger.info(f"[{level}] {message}")

    def get_live_view_url(self) -> str:
        """Get live view URL for real-time browser session viewing"""
        try:
            if not self.agentcore_client:
                return None

            # Generate live view URL using AgentCore
            live_view_url = self.agentcore_client.generate_live_view_url()

            self._add_log(
                "INFO", f"Generated live view URL: {live_view_url[:50]}...", "live_view"
            )

            return live_view_url

        except Exception as e:
            logger.error(f"Failed to generate live view URL: {e}")
            self._add_log("ERROR", f"Live view URL generation failed: {e}", "live_view")
            return None

    async def _capture_screenshot(self, step_name: str = None) -> str:
        """Capture screenshot and return URL - Disabled to avoid concurrent connection issues"""
        # Temporarily disable screenshot capture to avoid concurrent connection issues
        # with Nova Act. AgentCore doesn't support multiple concurrent connections to same session.
        self._add_log(
            "INFO",
            "Screenshot capture disabled to avoid concurrent connection issues with Nova Act",
            step_name or "screenshot",
        )
        return None

    async def start_session(
        self, session_id: str, browser_session_id: str = None
    ) -> Dict[str, Any]:
        """Start Nova Act + AgentCore Browser session"""
        try:
            self.session_id = session_id

            # Set up session replay configuration
            self.session_replay_config = {
                "enabled": True,
                "s3_bucket": self.config.get("session_replay_s3_bucket", "sanghwa-oregon"),
                "s3_prefix": self.config.get("session_replay_s3_prefix", f"session-replays/{session_id}/"),
                "session_id": session_id
            }

            if browser_session_id:
                # Use existing browser session
                from agentcore_manager import agentcore_manager

                cdp_info = await agentcore_manager.get_cdp_info(browser_session_id)

                if not cdp_info:
                    raise RuntimeError(
                        f"Browser session {browser_session_id} not found"
                    )

                ws_url = cdp_info["cdp_endpoint"]
                headers = cdp_info["headers"]

                logger.info(f"Using existing browser session: {browser_session_id}")
            else:
                # Create new AgentCore browser session
                region = self.config.get("agentcore_region", "us-west-2")

                # Use context manager properly
                self.agentcore_context = browser_session(region)
                self.agentcore_client = self.agentcore_context.__enter__()

                # Get CDP endpoint
                ws_url, headers = self.agentcore_client.generate_ws_headers()

            # Store CDP info for Nova Act initialization
            self.ws_url = ws_url
            self.headers = headers

            # Initialize Nova Act with AgentCore
            self.nova_session = NovaAct(
                cdp_endpoint_url=ws_url,
                cdp_headers=headers,
                preview={"playwright_actuation": True},
                nova_act_api_key=self.api_key,
                starting_page="https://www.google.com",
            )

            # Also create a Strands agent for hybrid approach
            try:
                bedrock_model = BedrockModel(
                    model_id=self.config.get(
                        "model", "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
                    ),
                    cache_prompt="default"
                )
                
                self.strands_agent = Agent(
                    model=bedrock_model,
                    system_prompt="""You are an e-commerce automation assistant working alongside Nova Act browser automation.
                    You can analyze automation results, provide guidance, and help with complex decision-making during the automation process.
                    Your role is to interpret results, handle errors, and provide intelligent analysis of the automation workflow."""
                )
                
                logger.info("Strands agent created for hybrid Nova Act approach")
            except Exception as strands_error:
                logger.warning(f"Could not create Strands agent: {strands_error}")
                self.strands_agent = None

            logger.info(f"Nova Act + AgentCore Browser session {session_id} started")

            return {
                "session_id": session_id,
                "status": "active",
                "automation_method": "nova_act",
                "created_at": datetime.now().isoformat(),
                "browser_session_id": browser_session_id,
            }

        except Exception as e:
            logger.error(f"Failed to start Nova Act session: {e}")
            raise

    async def process_order(self, order, progress_callback=None) -> Dict[str, Any]:
        """Process order using Nova Act"""
        if not self.nova_session:
            raise RuntimeError("Session not started")

        try:
            order_id = order.id
            self._add_log(
                "INFO",
                f"Starting order processing for {order.product_name}",
                "initialization",
            )

            # Set up session replay for this order if available
            if hasattr(self, 'session_replay_config') and self.session_replay_config.get('enabled'):
                try:
                    # Import database manager here to avoid circular imports
                    import sys
                    import os
                    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
                    from database import DatabaseManager
                    db_manager = DatabaseManager()
                    
                    # Update session replay info in database
                    db_manager.update_session_replay_info(
                        order_id=order_id,
                        s3_bucket=self.session_replay_config['s3_bucket'],
                        s3_prefix=self.session_replay_config['s3_prefix'],
                        enabled=True,
                        session_id=self.session_replay_config['session_id']
                    )
                    
                    self._add_log(
                        "INFO",
                        f"Session replay configured for order {order_id}: {self.session_replay_config['s3_bucket']}/{self.session_replay_config['s3_prefix']}",
                        "session_replay",
                    )
                except Exception as replay_error:
                    self._add_log(
                        "WARNING",
                        f"Failed to set up session replay for order {order_id}: {replay_error}",
                        "session_replay",
                    )

            # Create order command
            command = f"""
            Complete this e-commerce order:
            1. Navigate to {order.product_url}
            2. Find product: {order.product_name}
            3. Select size: {order.product_size or 'any available'}
            4. Select color: {order.product_color or 'any available'}
            5. Add to cart
            6. Proceed to checkout
            7. Fill shipping: {order.shipping_address.get('first_name', '')} {order.shipping_address.get('last_name', '')}, {order.shipping_address.get('address_line_1', '')}, {order.shipping_address.get('city', '')}, {order.shipping_address.get('state', '')} {order.shipping_address.get('postal_code', '')}
            
            Stop if you encounter CAPTCHAs or errors.
            """

            self._add_log(
                "INFO",
                f"Generated automation command: {len(command)} characters",
                "command_generation",
            )

            if progress_callback:
                await progress_callback(
                    {
                        "order_id": order_id,
                        "status": "processing",
                        "progress": 10,
                        "step": "Starting Nova Act client",
                        "automation_method": "nova_act",
                    }
                )

            # Start Nova Act client
            self._add_log("INFO", "Starting Nova Act client", "client_startup")

            # Initialize Nova Act in thread pool to avoid event loop conflicts
            import concurrent.futures
            
            def init_nova_act():
                try:
                    # Set up event loop for this thread to avoid uvloop conflicts
                    try:
                        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    except Exception as loop_error:
                        self._add_log("WARNING", f"Event loop setup warning: {loop_error}", "client_startup")
                    
                    # Initialize Nova Act
                    nova_session = NovaAct(
                        cdp_endpoint_url=self.ws_url,
                        cdp_headers=self.headers,
                        preview={"playwright_actuation": True},
                        nova_act_api_key=self.api_key,
                        starting_page="https://www.google.com",
                    )
                    
                    # Start Nova Act session
                    nova_session.start()
                    return nova_session
                    
                except Exception as e:
                    self._add_log("ERROR", f"Nova Act initialization failed: {e}", "client_startup")
                    raise e
            
            # Run Nova Act initialization in thread pool
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                self.nova_session = await loop.run_in_executor(executor, init_nova_act)

            self._add_log(
                "INFO", "Nova Act client started successfully", "client_startup"
            )

            if progress_callback:
                await progress_callback(
                    {
                        "order_id": order_id,
                        "status": "processing",
                        "progress": 20,
                        "step": "Executing Nova Act automation",
                        "automation_method": "nova_act",
                    }
                )

            # Capture initial screenshot
            initial_screenshot = await self._capture_screenshot("initial_state")

            # Execute automation
            self._add_log(
                "INFO",
                f"Executing automation command: {command[:100]}...",
                "automation_execution",
            )

            # Run Nova Act automation in thread pool to avoid blocking
            def execute_nova_act():
                try:
                    return self.nova_session.act(command)
                except Exception as e:
                    self._add_log("ERROR", f"Nova Act execution error: {e}", "automation_execution")
                    return f"FAILED: Nova Act execution error: {e}"
            
            # Execute in thread pool with timeout
            import concurrent.futures
            loop = asyncio.get_event_loop()
            
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = loop.run_in_executor(executor, execute_nova_act)
                    result = await asyncio.wait_for(future, timeout=300.0)  # 5 minute timeout
                    
            except asyncio.TimeoutError:
                self._add_log(
                    "ERROR",
                    "Nova Act execution timed out after 5 minutes",
                    "automation_execution",
                )
                result = "FAILED: Nova Act automation timed out after 5 minutes."
                
            except Exception as exec_error:
                self._add_log(
                    "ERROR",
                    f"Thread execution failed: {exec_error}",
                    "automation_execution",
                )
                result = f"FAILED: Thread execution error: {exec_error}"

            self._add_log(
                "INFO",
                f"Automation completed with result: {str(result)[:200]}...",
                "automation_execution",
            )

            # Capture final screenshot
            final_screenshot = await self._capture_screenshot("final_state")

            # Check result
            if result and "completed" in str(result).lower():
                if progress_callback:
                    await progress_callback(
                        {
                            "order_id": order_id,
                            "status": "completed",
                            "progress": 100,
                            "step": "Order completed successfully",
                            "automation_method": "nova_act",
                        }
                    )

                # Prepare session replay info for return
                session_replay_info = {}
                if hasattr(self, 'session_replay_config') and self.session_replay_config.get('enabled'):
                    session_replay_info = {
                        "session_replay_enabled": True,
                        "session_replay_s3_bucket": self.session_replay_config['s3_bucket'],
                        "session_replay_s3_prefix": self.session_replay_config['s3_prefix'],
                        "session_id": self.session_replay_config['session_id']
                    }

                return {
                    "success": True,
                    "status": "completed",
                    "confirmation_number": f"NOVA-{order_id[:8]}",
                    "automation_method": "nova_act",
                    "result": str(result),
                    **session_replay_info
                }

            elif result and "captcha" in str(result).lower():
                return {
                    "success": False,
                    "status": "requires_human",
                    "message": "CAPTCHA detected",
                    "automation_method": "nova_act",
                }

            else:
                raise Exception(f"Order processing failed: {result}")

        except Exception as e:
            logger.error(f"Nova Act automation failed: {e}")
            return {
                "success": False,
                "status": "failed",
                "error": str(e),
                "automation_method": "nova_act",
            }

    async def cleanup(self):
        """Clean up resources"""
        try:
            # Clean up Strands agent
            self.strands_agent = None
            
            # Clean up Nova Act in thread pool to avoid blocking
            if self.nova_session:
                def cleanup_nova_act():
                    try:
                        if hasattr(self.nova_session, 'stop'):
                            self.nova_session.stop()
                        if hasattr(self.nova_session, "__exit__"):
                            self.nova_session.__exit__(None, None, None)
                        return True
                    except Exception as e:
                        logger.warning(f"Error stopping Nova Act client: {e}")
                        return False
                
                # Run cleanup in thread pool
                import concurrent.futures
                loop = asyncio.get_event_loop()
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    await loop.run_in_executor(executor, cleanup_nova_act)
                
                self.nova_session = None
                logger.info("Nova Act client stopped")

            # Clean up AgentCore context
            if hasattr(self, "agentcore_context") and self.agentcore_context:
                try:
                    self.agentcore_context.__exit__(None, None, None)
                except Exception as e:
                    logger.warning(f"Error cleaning up AgentCore context: {e}")
                finally:
                    self.agentcore_context = None
                    self.agentcore_client = None

            logger.info(f"Nova Act session {self.session_id} cleaned up")

        except Exception as e:
            logger.error(f"Cleanup error: {e}")

    def get_live_view_url(self, expires: int = 300) -> str:
        """Get live view URL for AWS DCV - delegated to LiveViewService"""
        try:
            from ..services.live_view_service import get_live_view_service
            
            # Get or create live view service
            live_view_service = get_live_view_service(self.config, self.db_manager)
            
            # Get session for this order (from database)
            if self.db_manager and hasattr(self, 'session_id') and self.session_id:
                order = self.db_manager.get_order(self.session_id)
                if order:
                    # Try to get existing session or create new one
                    live_session_id = live_view_service.get_session_for_order(order.id)
                    if not live_session_id:
                        live_session_id = live_view_service.create_live_session(
                            order.id, 
                            "nova_act"
                        )
                    
                    if live_session_id:
                        presigned_url = live_view_service.get_presigned_url(live_session_id, expires=expires)
                        if presigned_url:
                            return presigned_url
            
            raise RuntimeError("Could not get live view URL - no valid session")
            
        except Exception as e:
            raise RuntimeError(f"Live view URL generation failed: {e}")
