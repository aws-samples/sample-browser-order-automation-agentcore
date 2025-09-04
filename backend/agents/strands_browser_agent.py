#!/usr/bin/env python3
"""
Strands + Browser Tools + AgentCore Browser Agent
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
    from strands import Agent
    from strands.models import BedrockModel
    from strands_tools.browser import AgentCoreBrowser
except ImportError as e:
    print(f"Warning: Required packages not installed: {e}")
    Agent = None
    BedrockModel = None
    AgentCoreBrowser = None

logger = logging.getLogger(__name__)


class StrandsBrowserAgent:
    """Strands + Browser Tools + AgentCore Browser Agent"""

    def __init__(
        self, config: Dict[str, Any], retailer_config: Dict[str, Any], db_manager=None
    ):
        self.config = config
        self.retailer_config = retailer_config
        self.db_manager = db_manager
        self.session_id = None
        self.strands_agent = None

        # Create screenshots directory
        self.screenshots_dir = os.path.join(
            os.path.dirname(__file__), "..", "static", "screenshots"
        )
        os.makedirs(self.screenshots_dir, exist_ok=True)

        if not Agent or not BedrockModel or not AgentCoreBrowser:
            raise ImportError("Required packages not available")

    def _add_log(self, level: str, message: str, step: str = None):
        """Add execution log entry"""
        # Print to stdout for execution log
        print(f"[{level}] {message}")

        if self.db_manager and self.session_id:
            try:
                self.db_manager.add_execution_log(self.session_id, level, message, step)
            except Exception as e:
                logger.error(f"Failed to add execution log: {e}")
        logger.info(f"[{level}] {message}")

    async def _capture_screenshot(self, step_name: str = None) -> str:
        """Capture screenshot and return URL"""
        try:
            # For Strands + Browser Tools, we would need to implement screenshot capture
            # This is a placeholder implementation
            logger.info(f"Screenshot capture requested for step: {step_name}")
            self._add_log(
                "INFO",
                f"Screenshot capture requested: {step_name}",
                step_name or "screenshot",
            )
            return None

        except Exception as e:
            logger.error(f"Failed to capture screenshot: {e}")
            self._add_log(
                "ERROR", f"Screenshot capture failed: {e}", step_name or "screenshot"
            )
            return None

    async def start_session(self, session_id: str) -> Dict[str, Any]:
        """Start Strands + Browser Tools session"""
        try:
            self.session_id = session_id

            # Set up session replay configuration
            self.session_replay_config = {
                "enabled": True,
                "s3_bucket": self.config.get("session_replay_s3_bucket", "sanghwa-oregon"),
                "s3_prefix": self.config.get("session_replay_s3_prefix", f"session-replays/{session_id}/"),
                "session_id": session_id
            }

            # Create AgentCore Browser tool and start session
            region = self.config.get("agentcore_region", "us-west-2")
            
            self._add_log(
                "INFO", "Initializing AgentCore Browser session", "browser_init"
            )
            
            # Initialize browser in a thread to avoid event loop conflicts
            import concurrent.futures
            
            def init_browser():
                try:
                    # Set up a new event loop for this thread to avoid uvloop conflicts
                    try:
                        # Try to use the default event loop policy to avoid uvloop issues
                        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    except Exception as loop_error:
                        self._add_log("WARNING", f"Event loop setup warning: {loop_error}", "browser_init")
                    
                    self.agent_core_browser = AgentCoreBrowser(region=region)
                    
                    # Import the required action model
                    from strands_tools.browser.models import InitSessionAction
                    
                    # Create the action with required parameters
                    action = InitSessionAction(
                        type="init_session",
                        description="Initialize browser session for e-commerce automation",
                        session_name=f"ecommerce-session-{session_id[:10]}"
                    )
                    
                    # Use sync initialization to avoid event loop conflicts
                    if hasattr(self.agent_core_browser, '_init_session'):
                        self.agent_core_browser._init_session(action)
                    elif hasattr(self.agent_core_browser, 'init_session'):
                        self.agent_core_browser.init_session(action)
                    else:
                        # Fallback - just create the browser tool
                        pass
                    
                    return True
                except Exception as e:
                    self._add_log("ERROR", f"Browser initialization failed: {e}", "browser_init")
                    raise e
            
            # Run browser initialization in thread pool
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                await loop.run_in_executor(executor, init_browser)
            
            self._add_log(
                "INFO",
                "AgentCore Browser session initialized successfully",
                "browser_init",
            )

            # Create Strands agent in a separate thread to avoid event loop conflicts
            def create_strands_agent():
                try:
                    # Set up event loop for this thread
                    try:
                        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    except Exception as loop_error:
                        self._add_log("WARNING", f"Event loop setup warning: {loop_error}", "agent_init")
                    
                    # Create Bedrock model with caching enabled
                    bedrock_model = BedrockModel(
                        model_id=self.config.get(
                            "model", "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
                        ),
                        cache_prompt="default",  # Enable system prompt caching
                        cache_tools="default"    # Enable tool caching
                    )

                    # Get browser tool safely
                    browser_tool = None
                    if hasattr(self.agent_core_browser, 'browser'):
                        browser_tool = self.agent_core_browser.browser
                    elif hasattr(self.agent_core_browser, 'get_tool'):
                        browser_tool = self.agent_core_browser.get_tool()
                    
                    tools = [browser_tool] if browser_tool else []

                    # Create Strands agent with browser tools and cached model
                    self.strands_agent = Agent(
                        model=bedrock_model,
                        tools=tools,
                        system_prompt="""You are an expert e-commerce automation assistant specializing in browser-based order processing. 
                        You have access to browser automation tools that allow you to navigate websites, interact with elements, and complete purchase flows.
                        
                        Your capabilities include:
                        - Navigating to product pages and searching for items
                        - Selecting product variants (size, color, quantity)
                        - Adding items to shopping carts
                        - Filling out checkout forms with shipping information
                        - Handling common e-commerce UI patterns and workflows
                        
                        Always be methodical in your approach:
                        1. First navigate to the target URL
                        2. Locate the specific product
                        3. Select the required options
                        4. Add to cart and proceed to checkout
                        5. Fill forms accurately but stop before payment processing
                        
                        If you encounter CAPTCHAs, anti-bot measures, or errors, report them clearly and stop the automation.
                        Provide detailed status updates throughout the process."""
                    )
                    return True
                except Exception as e:
                    self._add_log("ERROR", f"Strands agent creation failed: {e}", "agent_init")
                    raise e
            
            # Create agent in thread pool
            with concurrent.futures.ThreadPoolExecutor() as executor:
                await loop.run_in_executor(executor, create_strands_agent)

            logger.info(f"Strands + Browser Tools session {session_id} started")

            return {
                "session_id": session_id,
                "status": "active",
                "automation_method": "strands_browser",
                "created_at": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to start Strands Browser session: {e}")
            self._add_log(
                "ERROR", f"Failed to start browser session: {e}", "browser_init"
            )
            raise

    async def process_order(self, order, progress_callback=None) -> Dict[str, Any]:
        """Process order using Strands + Browser Tools"""
        if not self.strands_agent:
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

            # Create order prompt
            prompt = f"""
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
                f"Generated automation prompt: {len(prompt)} characters",
                "command_generation",
            )

            if progress_callback:
                await progress_callback(
                    {
                        "order_id": order_id,
                        "status": "processing",
                        "progress": 20,
                        "step": "Executing Strands Browser automation",
                        "automation_method": "strands_browser",
                    }
                )

            # Capture initial screenshot
            initial_screenshot = await self._capture_screenshot("initial_state")

            # Execute automation in thread pool to avoid blocking
            self._add_log(
                "INFO", "Starting Strands agent execution in separate thread", "automation_execution"
            )
            
            def execute_strands_agent():
                try:
                    response = self.strands_agent(prompt)
                    if hasattr(response, 'message') and response.message:
                        if isinstance(response.message, dict) and 'content' in response.message:
                            return response.message["content"][0]["text"]
                        elif hasattr(response.message, 'content'):
                            return response.message.content[0].text if response.message.content else str(response.message)
                        else:
                            return str(response.message)
                    else:
                        return str(response)
                except Exception as e:
                    self._add_log("ERROR", f"Strands execution error: {e}", "automation_execution")
                    return f"FAILED: Strands execution error: {e}"
            
            # Run in thread pool with timeout
            import concurrent.futures
            loop = asyncio.get_event_loop()
            
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = loop.run_in_executor(executor, execute_strands_agent)
                    result_text = await asyncio.wait_for(future, timeout=300.0)  # 5 minute timeout
                
                self._add_log(
                    "INFO",
                    f"Strands agent completed with result: {result_text[:200]}...",
                    "automation_execution",
                )
                
            except asyncio.TimeoutError:
                self._add_log(
                    "ERROR",
                    "Strands agent execution timed out after 5 minutes",
                    "automation_execution",
                )
                result_text = "FAILED: Browser automation timed out after 5 minutes."
                
            except Exception as exec_error:
                self._add_log(
                    "ERROR",
                    f"Thread execution failed: {exec_error}",
                    "automation_execution",
                )
                result_text = f"FAILED: Thread execution error: {exec_error}"

            # Capture final screenshot
            final_screenshot = await self._capture_screenshot("final_state")

            # Check result
            if "completed" in result_text.lower():
                self._add_log("INFO", "Order completed successfully", "completion")
                if progress_callback:
                    await progress_callback(
                        {
                            "order_id": order_id,
                            "status": "completed",
                            "progress": 100,
                            "step": "Order completed successfully",
                            "automation_method": "strands_browser",
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
                    "confirmation_number": f"STRANDS-{order_id[:8]}",
                    "automation_method": "strands_browser",
                    "result": result_text,
                    **session_replay_info
                }

            elif "captcha" in result_text.lower():
                self._add_log(
                    "WARNING",
                    "CAPTCHA detected - requires human intervention",
                    "captcha_detected",
                )
                return {
                    "success": False,
                    "status": "requires_human",
                    "message": "CAPTCHA detected",
                    "automation_method": "strands_browser",
                }

            else:
                error_msg = f"Order processing failed: {result_text}"
                self._add_log("ERROR", error_msg, "automation_failure")
                raise Exception(error_msg)

        except Exception as e:
            error_msg = f"Strands Browser automation failed: {e}"
            self._add_log("ERROR", error_msg, "automation_failure")
            logger.error(error_msg)
            return {
                "success": False,
                "status": "failed",
                "error": str(e),
                "automation_method": "strands_browser",
            }

    def get_live_view_url(self, expires: int = 300) -> str:
        """Get live view URL for AWS DCV"""
        if hasattr(self, 'agent_core_browser') and self.agent_core_browser:
            # Get the underlying browser client
            browser_client = getattr(self.agent_core_browser, '_client', None)
            if browser_client and hasattr(browser_client, 'generate_live_view_url'):
                return browser_client.generate_live_view_url(expires=expires)
        raise RuntimeError("Browser session not active or live view not available")

    async def cleanup(self):
        """Clean up resources"""
        try:
            # Clean up Strands agent
            self.strands_agent = None
            
            # Clean up AgentCore browser if available
            if hasattr(self, 'agent_core_browser') and self.agent_core_browser:
                try:
                    # Cleanup browser session if method exists
                    if hasattr(self.agent_core_browser, 'cleanup'):
                        await self.agent_core_browser.cleanup()
                except Exception as browser_cleanup_error:
                    logger.warning(f"Browser cleanup error: {browser_cleanup_error}")
                finally:
                    self.agent_core_browser = None
            
            logger.info(f"Strands Browser session {self.session_id} cleaned up")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
