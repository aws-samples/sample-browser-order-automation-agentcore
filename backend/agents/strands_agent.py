#!/usr/bin/env python3
"""
Strands Agent
Strands AI agent focused on agentic browser automation using AgentCoreBrowser
Based on proven working implementation with independent order agents
"""

import os
import sys
import logging
import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

# Set up logger first
logger = logging.getLogger(__name__)

# Fix uvloop compatibility issue
try:
    import uvloop
    # Check if we're already using uvloop and avoid patching
    current_loop = None
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        pass
    
    # Only set policy if no loop is running or it's not uvloop
    if not current_loop or not isinstance(current_loop, uvloop.Loop):
        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
except ImportError:
    pass

# Add parent directory to path for config import
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import get_config_manager

try:
    from strands import Agent, tool
    from strands.models import BedrockModel
    import nest_asyncio
    from playwright.async_api import async_playwright
    
    # Import our custom browser tools
    from tools.browser import (
        browser_install,
        browser_navigate,
        browser_click,
        browser_type,
        browser_fill_form,
        browser_take_screenshot,
        browser_evaluate,
        browser_wait_for,
        browser_press_key,
        browser_hover,
        browser_select_option,
        browser_file_upload,
        browser_handle_dialog,
        browser_drag,
        browser_resize,
        browser_tabs,
        browser_navigate_back,
        browser_snapshot,
        browser_network_requests,
        browser_console_messages,
        browser_close,
    )
    BROWSER_TOOLS_AVAILABLE = True
    
    # Apply nest_asyncio only if not using uvloop
    try:
        current_loop = asyncio.get_running_loop()
        loop_type = str(type(current_loop))
        if 'uvloop' not in loop_type:
            nest_asyncio.apply()
        else:
            logger.info("Detected uvloop, skipping nest_asyncio.apply()")
    except RuntimeError:
        # No running loop, safe to apply
        try:
            nest_asyncio.apply()
        except ValueError as e:
            if "Can't patch loop" in str(e):
                logger.warning(f"Skipping nest_asyncio due to loop patching issue: {e}")
            else:
                raise
    except Exception as e:
        logger.warning(f"nest_asyncio setup warning: {e}")
    
except ImportError as e:
    print(f"Warning: Required packages not installed: {e}")
    Agent = None
    tool = None
    BedrockModel = None
    nest_asyncio = None
    async_playwright = None
    BROWSER_TOOLS_AVAILABLE = False
    
    # Set browser tools to None
    browser_install = None
    browser_navigate = None
    browser_click = None
    browser_type = None
    browser_fill_form = None
    browser_take_screenshot = None
    browser_evaluate = None
    browser_wait_for = None
    browser_press_key = None
    browser_hover = None
    browser_select_option = None
    browser_file_upload = None
    browser_handle_dialog = None
    browser_drag = None
    browser_resize = None
    browser_tabs = None
    browser_navigate_back = None
    browser_snapshot = None
    browser_network_requests = None
    browser_console_messages = None
    browser_close = None


class StrandsAgent:
    """
    Strands Agent focused on AI-powered browser automation
    Uses AgentCoreBrowser with independent order processing agents
    """

    def __init__(
        self,
        config: Dict[str, Any],
        retailer_config: Dict[str, Any],
        db_manager=None,
        browser_service=None,
    ):
        self.config = config
        self.retailer_config = retailer_config
        self.db_manager = db_manager
        self.browser_service = browser_service
        self.session_id = None
        self.strands_agent = None
        
        # Get config from DB via ConfigManager
        self.config_manager = get_config_manager(db_manager)
        self.agent_config = self.config_manager.get_agent_config("strands")
        self.region = self.agent_config.agentcore_region
        self.processed_orders = []

        # Create screenshots directory
        self.screenshots_dir = os.path.join(
            os.path.dirname(__file__), "..", "static", "screenshots"
        )
        os.makedirs(self.screenshots_dir, exist_ok=True)

        if not Agent or not BedrockModel:
            raise ImportError("Required Strands packages not available")
        
        if not BROWSER_TOOLS_AVAILABLE:
            raise ImportError("Browser tools not available")

    def _add_log(self, level: str, message: str, step: str = None):
        """Add execution log entry with real-time broadcast"""
        # Use logger instead of print to avoid duplication
        if level == "ERROR":
            logger.error(f"{message}")
        elif level == "WARNING":
            logger.warning(f"{message}")
        else:
            logger.info(f"{message}")

        if self.db_manager and self.session_id:
            try:
                self.db_manager.add_execution_log(self.session_id, level, message, step)

                # Broadcast log update in real-time
                import asyncio

                try:
                    # Import broadcast function
                    from app import broadcast_update

                    # Create log update message
                    log_data = {
                        "type": "log_update",
                        "order_id": self.session_id,
                        "log": {
                            "level": level,
                            "message": message,
                            "step": step,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        },
                    }

                    # Try to broadcast (non-blocking)
                    try:
                        # Use asyncio.create_task if we're in an async context
                        try:
                            loop = asyncio.get_running_loop()
                            loop.create_task(broadcast_update(log_data))
                        except RuntimeError:
                            # No running loop, try to get or create one
                            try:
                                loop = asyncio.get_event_loop()
                                if loop.is_running():
                                    loop.create_task(broadcast_update(log_data))
                                else:
                                    # Schedule for later execution
                                    asyncio.ensure_future(broadcast_update(log_data))
                            except Exception:
                                # Skip broadcast if we can't get a loop
                                pass
                    except Exception:
                        # Skip broadcast on any error
                        pass

                except ImportError:
                    # broadcast_update not available, skip
                    pass

            except Exception as e:
                logger.error(f"Failed to add execution log: {e}")

    def create_independent_order_agent(self, order: Dict[str, Any]) -> Agent:
        """Create a completely independent agent for processing a single order.
        Each agent has its own browser instance and message history."""
        try:
            # Initialize Bedrock model with caching
            model = BedrockModel(
                model_id=self.agent_config.default_model,
                region_name=self.region,
                cache_prompt="default",
                cache_tools="default",
            )

            # Set region for browser tools
            os.environ['AWS_DEFAULT_REGION'] = self.region
            
            # Use our custom browser tools
            browser_tools = [
                browser_install,
                browser_navigate,
                browser_click,
                browser_type,
                browser_fill_form,
                browser_take_screenshot,
                browser_evaluate,
                browser_wait_for,
                browser_press_key,
                browser_hover,
                browser_select_option,
                browser_file_upload,
                browser_handle_dialog,
                browser_drag,
                browser_resize,
                browser_tabs,
                browser_navigate_back,
                browser_snapshot,
                browser_network_requests,
                browser_console_messages,
                browser_close,
            ]
            
            self._add_log(
                "INFO",
                f"Using custom browser tools ({len(browser_tools)} tools available) in region {self.region}",
                "browser_setup",
            )

            # Create specialized order processing agent with browser tools
            all_tools = browser_tools

            # Check if we have site credentials
            credentials_info = ""
            if self.retailer_config.get("credentials"):
                creds = self.retailer_config["credentials"]
                if creds.get("username") and creds.get("password"):
                    credentials_info = f"""

SITE LOGIN CREDENTIALS (use if login is required):
- Username: {creds['username']}
- Password: {creds['password']}

If you encounter a login page, use these credentials to sign in before proceeding with the order.
"""

            order_agent = Agent(
                model=model,
                tools=all_tools,
                system_prompt=f"""You are a specialized e-commerce order processing agent using AgentCore browser.
Process this SINGLE order only:

Product: {order.get('product_name', order.get('name', 'Unknown'))}
URL: {order.get('product_url', order.get('url', ''))}
Size: {order.get('product_size', order.get('size', 'any available'))}
Color: {order.get('product_color', order.get('color', 'any available'))}

Steps to complete:
1. Install AgentCore browser and get session ID: browser_install()
2. Navigate to the product URL: browser_navigate(session_id, url)
3. Take initial screenshot: browser_take_screenshot(session_id)
4. If login is required, use the provided credentials to sign in
5. Select the specified size and color if available
6. Add to cart using browser_click() and browser_type()
7. Verify cart contents using browser_snapshot()
8. Take screenshots at each step: browser_take_screenshot(session_id)
9. Check checkout options (DO NOT complete payment)
10. Close browser session when done: browser_close(session_id)

Report each step clearly and handle errors gracefully.
Available tools: {len(all_tools)} AgentCore browser automation tools running in AWS region {self.region}.
{credentials_info}

IMPORTANT: 
- Always start with browser_install() to get a session_id
- Use that session_id for all subsequent browser operations
- The browser runs remotely in AWS and provides live view capabilities
- Take screenshots frequently to document progress
""",
            )

            self._add_log(
                "INFO",
                f"Created independent order agent for {order.get('product_name', 'Unknown')} with {len(all_tools)} tools",
                "agent_creation",
            )
            return order_agent

        except Exception as e:
            self._add_log(
                "ERROR",
                f"Failed to create independent order agent: {e}",
                "agent_creation",
            )
            raise

    async def start_session(self, session_id: str) -> Dict[str, Any]:
        """Start Strands browser session"""
        try:
            self.session_id = session_id
            self._add_log(
                "INFO",
                f"Starting Strands browser session: {session_id}",
                "initialization",
            )

            # Initialize our custom browser manager
            try:
                # Set region environment variable for browser tools
                os.environ['AWS_DEFAULT_REGION'] = self.region
                
                from tools.browser.browser_manager import BrowserManager
                
                # Create browser manager with region
                browser_manager = BrowserManager(region=self.region)
                
                # Initialize browser manager asynchronously
                async def init_browser_manager():
                    await browser_manager._async_initialize()
                    browser_session_id = await browser_manager._async_create_session(session_id)
                    return browser_session_id
                
                # Run async initialization
                import concurrent.futures
                loop = asyncio.get_event_loop()
                
                try:
                    # Try to run in current loop if possible
                    browser_session_id = loop.run_until_complete(init_browser_manager())
                except RuntimeError:
                    # If we can't use current loop, use thread executor
                    def run_async_init():
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        try:
                            return new_loop.run_until_complete(init_browser_manager())
                        finally:
                            new_loop.close()
                    
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(run_async_init)
                        browser_session_id = future.result(timeout=30)
                
                self.browser_session_id = browser_session_id
                self.browser_manager = browser_manager
                
                self._add_log(
                    "INFO",
                    f"Custom browser manager initialized with session: {browser_session_id}",
                    "initialization",
                )
                
                # Store browser session info for live view (optional)
                self.agentcore_client = None  # Not using direct AgentCore client
                self.ws_url = None
                self.headers = None
                    
            except Exception as e:
                self._add_log(
                    "WARNING",
                    f"Custom browser manager initialization failed: {e}",
                    "initialization",
                )
                self.browser_session_id = None
                self.browser_manager = None
                self.agentcore_client = None

            # Create main Strands agent for coordination
            bedrock_model = BedrockModel(
                model_id=self.agent_config.default_model,
                cache_prompt="default",
                cache_tools="default",
            )

            # Create coordination agent with our custom browser tools
            tools = [
                browser_install,
                browser_navigate,
                browser_click,
                browser_type,
                browser_fill_form,
                browser_take_screenshot,
                browser_evaluate,
                browser_wait_for,
                browser_press_key,
                browser_hover,
                browser_select_option,
                browser_file_upload,
                browser_handle_dialog,
                browser_drag,
                browser_resize,
                browser_tabs,
                browser_navigate_back,
                browser_snapshot,
                browser_network_requests,
                browser_console_messages,
                browser_close,
            ]

            self.strands_agent = Agent(
                model=bedrock_model,
                tools=tools,
                system_prompt=f"""You are an e-commerce automation agent that processes orders using AgentCore browser tools.

Your role is to:
1. Use the browser tools to navigate e-commerce websites
2. Search for and select products  
3. Add items to cart and proceed through checkout
4. Handle login, size/color selection, and shipping information
5. Report progress and handle errors gracefully

You have access to {len(tools)} AgentCore browser automation tools running in AWS region {self.region}.

IMPORTANT SESSION MANAGEMENT:
- A browser session has already been created for you with session_id: {getattr(self, 'browser_session_id', 'unknown')}
- Use this session_id for all browser operations
- Do NOT call browser_install() again - the session is already active
- Start directly with browser_navigate(session_id, url) to begin automation

Available tools include:
- browser_navigate: Navigate to URLs using AgentCore browser
- browser_click: Click elements
- browser_type: Type text into fields
- browser_fill_form: Fill multiple form fields
- browser_take_screenshot: Take screenshots for documentation
- browser_wait_for: Wait for elements to appear
- browser_snapshot: Get page HTML content
- browser_close: Close the session when done

The browser is running remotely in AWS and provides live view capabilities.
Always use the provided session_id for all browser operations.
""",
            )

            self._add_log(
                "INFO", f"Session {session_id} started successfully", "initialization"
            )

            return {
                "session_id": session_id,
                "status": "active",
                "automation_method": "strands",
                "created_at": datetime.now().isoformat(),
                "browser_session_id": getattr(self, 'browser_session_id', None),
            }

        except Exception as e:
            error_msg = f"Failed to start session: {e}"
            self._add_log("ERROR", error_msg, "initialization")
            logger.error(error_msg)
            raise

    def save_single_result(
        self, result: Dict[str, Any], filename: str = "strands_results_live.json"
    ):
        """Save a single result immediately to JSON"""
        try:
            # Load existing results if file exists
            if os.path.exists(filename):
                with open(filename, "r", encoding="utf-8") as file:
                    existing_results = json.load(file)
            else:
                existing_results = []

            # Add new result
            existing_results.append(result)

            # Save back to file with pretty formatting
            with open(filename, "w", encoding="utf-8") as file:
                json.dump(existing_results, file, indent=2, ensure_ascii=False)

        except Exception as e:
            self._add_log("ERROR", f"Error saving result: {e}", "save_result")

    async def process_order(self, order, progress_callback=None) -> Dict[str, Any]:
        """Process order using independent Strands agent"""
        try:
            order_id = order.id
            self._add_log(
                "INFO",
                f"Starting order processing for {order.product_name}",
                "order_processing",
            )

            if progress_callback:
                await progress_callback(
                    {
                        "order_id": order_id,
                        "status": "processing",
                        "progress": 10,
                        "step": "Creating independent order agent",
                        "automation_method": "strands",
                    }
                )

            # Convert order object to dict for agent creation
            order_dict = {
                "product_name": order.product_name,
                "product_url": order.product_url,
                "product_size": order.product_size,
                "product_color": order.product_color,
                "shipping_address": order.shipping_address,
            }

            # Use main Strands agent with existing browser session instead of creating independent agent
            if not self.strands_agent:
                raise Exception("Strands agent not initialized")

            if progress_callback:
                await progress_callback(
                    {
                        "order_id": order_id,
                        "status": "processing",
                        "progress": 30,
                        "step": "Executing order automation with existing browser session",
                        "automation_method": "strands",
                    }
                )

            # Check if we have site credentials
            credentials_info = ""
            if self.retailer_config.get("credentials"):
                creds = self.retailer_config["credentials"]
                if creds.get("username") and creds.get("password"):
                    credentials_info = f"""

Site Login Credentials (use if login is required):
- Username: {creds['username']}
- Password: {creds['password']}

If you encounter a login page, use these credentials to sign in before proceeding.
"""

            # Process the order with dedicated agent
            instruction = f"""Process this e-commerce order using session_id: {getattr(self, 'browser_session_id', 'unknown')}

Product: {order.product_name}
URL: {order.product_url}
Size: {order.product_size or 'any available'}
Color: {order.product_color or 'any available'}

Shipping Information:
- Name: {order.shipping_address.get('first_name', '')} {order.shipping_address.get('last_name', '')}
- Address: {order.shipping_address.get('address_line_1', '')}, {order.shipping_address.get('city', '')}, {order.shipping_address.get('state', '')} {order.shipping_address.get('postal_code', '')}

Steps to follow:
1. Navigate to the product URL: browser_navigate("{getattr(self, 'browser_session_id', 'unknown')}", "{order.product_url}")
2. Take initial screenshot: browser_take_screenshot("{getattr(self, 'browser_session_id', 'unknown')}")
3. Handle login if required using provided credentials
4. Select size and color if available
5. Add to cart
6. Take screenshot of cart: browser_take_screenshot("{getattr(self, 'browser_session_id', 'unknown')}")
7. Proceed to checkout (DO NOT complete payment)
8. Take final screenshot: browser_take_screenshot("{getattr(self, 'browser_session_id', 'unknown')}")

Follow all steps methodically and report your progress.
{credentials_info}
"""

            # Execute with Strands agent using browser tools
            def execute_strands_agent():
                try:
                    # Enhanced instruction with browser session ID
                    enhanced_instruction = f"""
{instruction}

CRITICAL: Use session_id "{getattr(self, 'browser_session_id', 'unknown')}" for ALL browser operations.
The browser session is already initialized and ready to use.
Do NOT call browser_install() - start directly with browser_navigate().
"""
                    
                    response = self.strands_agent(enhanced_instruction)
                    return str(response)
                except Exception as e:
                    self._add_log(
                        "ERROR",
                        f"Strands agent execution error: {e}",
                        "automation_execution",
                    )
                    return f"FAILED: Strands agent execution error: {e}"

            # Run with timeout
            loop = asyncio.get_event_loop()
            try:
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = loop.run_in_executor(executor, execute_strands_agent)
                    response_text = await asyncio.wait_for(
                        future, timeout=300.0
                    )  # 5 minute timeout
            except asyncio.TimeoutError:
                response_text = "FAILED: Order processing timed out after 5 minutes"
                self._add_log(
                    "ERROR", "Order processing timed out", "automation_execution"
                )

            self._add_log(
                "INFO",
                f"Order agent completed: {response_text[:200]}...",
                "automation_execution",
            )

            # Create result based on response
            result = {
                "product_name": order.product_name,
                "status": "pending",
                "order_id": order_id,
                "message": "",
                "timestamp": datetime.now().isoformat(),
            }

            # Parse response to determine success
            response_lower = response_text.lower()
            if any(
                keyword in response_lower
                for keyword in ["added to cart", "cart updated", "successfully added"]
            ):
                if any(
                    keyword in response_lower
                    for keyword in ["checkout", "proceed", "cart"]
                ):
                    result["status"] = "success"
                    result["message"] = "Order processed successfully"
                    success = True
                    status = "completed"
                else:
                    result["status"] = "partial"
                    result["message"] = "Added to cart but checkout not verified"
                    success = False
                    status = "partial"
            elif any(
                keyword in response_lower
                for keyword in [
                    "error",
                    "failed",
                    "not found",
                    "unavailable",
                    "timeout",
                ]
            ):
                result["status"] = "failed"
                result["message"] = "Order processing failed"
                success = False
                status = "failed"
            elif any(
                keyword in response_lower
                for keyword in ["captcha", "blocked", "requires_human"]
            ):
                result["status"] = "requires_human"
                result["message"] = "Manual intervention required"
                success = False
                status = "requires_human"
            else:
                result["status"] = "completed"
                result["message"] = "Order processing completed"
                success = True
                status = "completed"

            # Store response (truncated)
            if not result["message"] or result["message"] in [
                "Order processing failed",
                "Order processing completed",
            ]:
                result["message"] = response_text.replace("\n", " ").strip()[:200]

            # Save result
            self.save_single_result(result)

            if progress_callback:
                await progress_callback(
                    {
                        "order_id": order_id,
                        "status": status,
                        "progress": 100,
                        "step": f"Order {status}",
                        "automation_method": "strands",
                    }
                )

            self._add_log(
                "INFO",
                f"Order processing completed with status: {status}",
                "completion",
            )

            return {
                "success": success,
                "status": status,
                "confirmation_number": f"STRANDS-{order_id[:8]}" if success else None,
                "automation_method": "strands",
                "result": response_text,
                "manual_control_available": True,
            }

        except Exception as e:
            error_msg = f"Strands automation failed: {e}"
            self._add_log("ERROR", error_msg, "automation_failure")
            logger.error(error_msg)
            return {
                "success": False,
                "status": "failed",
                "error": str(e),
                "automation_method": "strands",
            }

    def get_live_view_url(self, expires: int = 300) -> Dict[str, Any]:
        """Get live view URL for real-time browser session viewing"""
        try:
            # Try to get live view URL from browser manager's AgentCore clients
            if hasattr(self, 'browser_manager') and self.browser_manager and hasattr(self, 'browser_session_id'):
                session = self.browser_manager.get_session(self.browser_session_id)
                if session and session.agentcore_client:
                    try:
                        # Generate live view URL using AgentCore client
                        live_view_url = session.agentcore_client.generate_live_view_url(expires=expires)
                        
                        if live_view_url:
                            self._add_log("INFO", f"Generated live view URL from browser session: {live_view_url[:50]}...", "live_view")
                            return {
                                "url": live_view_url,
                                "session_id": getattr(self, 'session_id', None),
                                "browser_session_id": self.browser_session_id,
                                "type": "dcv",
                                "expires": expires
                            }
                    except Exception as e:
                        self._add_log("WARNING", f"Failed to get live view from browser session: {e}", "live_view")
            
            # Fallback to BrowserService if available
            if self.browser_service and self.session_id:
                return self.browser_service.get_live_view_url(self.session_id, expires)
            
            return {"url": None, "error": "No active browser session with live view support"}

        except Exception as e:
            logger.error(f"Failed to get live view URL: {e}")
            self._add_log("ERROR", f"Live view URL generation failed: {e}", "live_view")
            return {"url": None, "error": str(e)}

    async def process_orders_batch(
        self,
        orders: List[Dict[str, Any]],
        batch_size: int = 3,
        progress_callback=None,
        result_callback=None,
    ) -> List[Dict[str, Any]]:
        """Process multiple orders in batches using independent agents"""
        all_results = []
        total_orders = len(orders)

        self._add_log(
            "INFO",
            f"Processing {total_orders} orders in batches of {batch_size}",
            "batch_processing",
        )

        for i in range(0, total_orders, batch_size):
            batch_orders = orders[i : i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (total_orders + batch_size - 1) // batch_size

            self._add_log(
                "INFO",
                f"Processing batch {batch_num}/{total_batches} ({len(batch_orders)} orders)",
                "batch_processing",
            )

            try:
                # Process orders in parallel using independent subagents
                async def process_order_async(order_dict, order_num):
                    """Async wrapper for order processing with independent agent"""
                    loop = asyncio.get_event_loop()

                    def process_with_independent_agent():
                        """Create and use independent agent for this order"""
                        try:
                            # Create completely independent agent for this order
                            order_agent = self.create_independent_order_agent(
                                order_dict
                            )

                            # Process the order
                            instruction = f"""Process this e-commerce order:
Product: {order_dict['product_name']}
URL: {order_dict['product_url']}
Size: {order_dict.get('product_size', 'any available')}
Color: {order_dict.get('product_color', 'any available')}

Follow all steps methodically and report your progress."""

                            response = order_agent(instruction)
                            response_text = str(response)

                            # Create result
                            result = {
                                "product_name": order_dict["product_name"],
                                "status": "pending",
                                "order_id": f"BATCH-{order_num}",
                                "message": "",
                                "timestamp": datetime.now().isoformat(),
                            }

                            # Parse response to determine success
                            response_lower = response_text.lower()
                            if any(
                                keyword in response_lower
                                for keyword in [
                                    "added to cart",
                                    "cart updated",
                                    "successfully added",
                                ]
                            ):
                                if any(
                                    keyword in response_lower
                                    for keyword in ["checkout", "proceed", "cart"]
                                ):
                                    result["status"] = "success"
                                    result["message"] = "Order processed successfully"
                                else:
                                    result["status"] = "partial"
                                    result["message"] = (
                                        "Added to cart but checkout not verified"
                                    )
                            elif any(
                                keyword in response_lower
                                for keyword in [
                                    "error",
                                    "failed",
                                    "not found",
                                    "unavailable",
                                ]
                            ):
                                result["status"] = "failed"
                                result["message"] = "Order processing failed"
                            else:
                                result["status"] = "completed"
                                result["message"] = "Order processing completed"

                            # Store response (truncated)
                            if not result["message"] or result["message"] in [
                                "Order processing failed",
                                "Order processing completed",
                            ]:
                                result["message"] = response_text.replace(
                                    "\n", " "
                                ).strip()[:200]

                            # Save result immediately
                            self.save_single_result(result)

                            return result

                        except Exception as e:
                            error_result = {
                                "product_name": order_dict["product_name"],
                                "status": "error",
                                "order_id": f"BATCH-{order_num}",
                                "message": f"Independent agent error: {str(e)}",
                                "timestamp": datetime.now().isoformat(),
                            }
                            self.save_single_result(error_result)
                            return error_result

                    # Run in thread pool to avoid asyncio conflicts
                    return await loop.run_in_executor(
                        None, process_with_independent_agent
                    )

                # Create tasks for all orders in this batch
                batch_tasks = []
                for j, order_dict in enumerate(batch_orders):
                    order_num = i + j + 1
                    task = asyncio.create_task(
                        process_order_async(order_dict, order_num)
                    )
                    batch_tasks.append(task)

                # Execute all tasks concurrently
                batch_results = await asyncio.gather(
                    *batch_tasks, return_exceptions=True
                )

                # Process results
                for j, result in enumerate(batch_results):
                    if isinstance(result, Exception):
                        # Handle exceptions from parallel processing
                        order_num = i + j + 1
                        order_dict = batch_orders[j]
                        error_result = {
                            "product_name": order_dict["product_name"],
                            "status": "error",
                            "order_id": f"BATCH-{order_num}",
                            "message": f"Parallel processing error: {str(result)}",
                            "timestamp": datetime.now().isoformat(),
                        }
                        all_results.append(error_result)
                        self.save_single_result(error_result)
                    else:
                        # Successful result from subagent
                        all_results.append(result)

            except Exception as e:
                # Handle batch processing errors
                for j, order_dict in enumerate(batch_orders):
                    order_num = i + j + 1
                    error_result = {
                        "product_name": order_dict["product_name"],
                        "status": "error",
                        "order_id": f"BATCH-{order_num}",
                        "message": f"Batch processing error: {str(e)}",
                        "timestamp": datetime.now().isoformat(),
                    }
                    all_results.append(error_result)
                    self.save_single_result(error_result)

            # Update progress after batch completion
            if progress_callback:
                completed_orders = len(all_results)
                progress_percent = (completed_orders / total_orders) * 90
                await progress_callback(
                    progress_percent,
                    f"Completed batch {batch_num}/{total_batches} - {completed_orders}/{total_orders} orders",
                )

            # Delay between batches
            if i + batch_size < total_orders:
                await asyncio.sleep(3)

        self._add_log(
            "INFO",
            f"All {total_orders} orders processed with independent agents",
            "batch_processing",
        )
        self.processed_orders = all_results
        return all_results

    def change_browser_resolution(self, width: int, height: int) -> Dict[str, Any]:
        """Change browser resolution via BrowserService"""
        try:
            if not self.browser_service or not self.session_id:
                return {"success": False, "error": "No active browser session"}

            return self.browser_service.change_browser_resolution(
                self.session_id, width, height
            )

        except Exception as e:
            logger.error(f"Failed to change resolution: {e}")
            return {"success": False, "error": str(e)}

    def enable_manual_control(self) -> Dict[str, Any]:
        """Enable manual control via BrowserService"""
        try:
            if not self.browser_service or not self.session_id:
                return {"success": False, "error": "No active browser session"}

            return self.browser_service.enable_manual_control(self.session_id)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def disable_manual_control(self) -> Dict[str, Any]:
        """Disable manual control via BrowserService"""
        try:
            if not self.browser_service or not self.session_id:
                return {"success": False, "error": "No active browser session"}

            return self.browser_service.disable_manual_control(self.session_id)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_session_status(self) -> Dict[str, Any]:
        """Get session status and information via BrowserService"""
        try:
            if not self.browser_service or not self.session_id:
                return {"exists": False, "status": "not_active"}

            return self.browser_service.get_session_info(self.session_id)

        except Exception as e:
            return {"exists": False, "status": "error", "error": str(e)}

    async def resume_automation(self, product_name: str):
        """Resume automation after manual control is released"""
        try:
            self._add_log(
                "INFO", "Resuming automation after manual control", "resume_automation"
            )

            # Continue with automation from where we left off
            prompt = f"""
            RESUME AUTOMATION TASK:
            Continue the automation process for ordering: {product_name}
            
            You are resuming after manual intervention. The user has completed some manual steps.
            
            CURRENT SITUATION:
            - Manual control has been released
            - Browser session is still active
            - Continue from current page state
            
            NEXT STEPS:
            1. Take screenshot to see current state: take_screenshot(step_name="resume_state")
            2. Analyze what has been completed manually
            3. Continue with remaining automation steps
            4. Complete the order process
            5. Take final screenshot: take_screenshot(step_name="automation_resumed")
            
            Use take_screenshot() frequently to document progress.
            If you encounter issues again, use take_control() for human intervention.
            """

            # Execute the resume automation
            def execute_resume():
                try:
                    return self.strands_agent(prompt)
                except Exception as e:
                    return f"ERROR: Resume execution failed: {e}"

            # Execute with timeout
            import concurrent.futures

            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.get_event_loop()

            # Execute resume asynchronously
            async def async_execute_resume():
                try:
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(None, execute_resume)
                    return result
                except Exception as e:
                    return f"FAILED: Resume automation error: {e}"

            try:
                result_text = await async_execute_resume()
            except Exception as e:
                result_text = f"FAILED: Resume automation error: {e}"

            # Process result
            result_lower = result_text.lower()
            if "success" in result_lower and "failed" not in result_lower:
                status = "completed"
                self._add_log(
                    "INFO",
                    "Automation resumed and completed successfully",
                    "resume_complete",
                )
            elif "take_control" in result_lower or "manual control" in result_lower:
                status = "manual_control"
                self._add_log(
                    "INFO", "Automation requires manual control again", "resume_manual"
                )
            else:
                status = "failed"
                self._add_log("ERROR", "Automation resume failed", "resume_failed")

            # Update order status
            if self.db_manager:
                self.db_manager.update_order_status(self.session_id, status)

            return {"success": True, "status": status, "message": result_text}

        except Exception as e:
            logger.error(f"Failed to resume automation: {e}")
            self._add_log("ERROR", f"Resume automation failed: {e}", "resume_error")
            if self.db_manager:
                self.db_manager.update_order_status(self.session_id, "failed")
            return {"success": False, "error": str(e)}

    async def cleanup(self, force: bool = False):
        """Clean up agent resources but preserve browser session for stateless operation

        Args:
            force: Not used in stateless mode - sessions are always preserved
        """
        try:
            # In stateless mode, we don't clean up browser sessions
            # They should be reusable by other agent instances
            should_preserve = True  # Always preserve in stateless mode
            
            self._add_log(
                "INFO",
                f"Agent cleanup completed, browser session {self.session_id} preserved for reuse",
                "cleanup",
            )

            # Clean up local references only

            # Clean up Strands agent (but keep browser_service reference for manual control)
            self.strands_agent = None
            if force or not should_preserve:
                self.browser_service = None
                # Clean up browser session if needed
                if hasattr(self, 'browser_session_id') and self.browser_session_id and hasattr(self, 'browser_manager'):
                    try:
                        # Run async cleanup
                        async def cleanup_session():
                            await self.browser_manager._async_close_session(self.browser_session_id)
                        
                        # Execute cleanup
                        try:
                            loop = asyncio.get_event_loop()
                            if loop.is_running():
                                import concurrent.futures
                                def run_cleanup():
                                    new_loop = asyncio.new_event_loop()
                                    asyncio.set_event_loop(new_loop)
                                    try:
                                        return new_loop.run_until_complete(cleanup_session())
                                    finally:
                                        new_loop.close()
                                
                                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                                    executor.submit(run_cleanup).result(timeout=10)
                            else:
                                loop.run_until_complete(cleanup_session())
                        except RuntimeError:
                            asyncio.run(cleanup_session())
                            
                        self._add_log("INFO", f"Closed browser session: {self.browser_session_id}", "cleanup")
                    except Exception as e:
                        self._add_log("WARNING", f"Failed to close browser session: {e}", "cleanup")
                # Clean up AgentCore client
                if hasattr(self, 'agentcore_client'):
                    self.agentcore_client = None

            logger.info("StrandsAgent cleanup complete")

        except Exception as e:
            logger.error(f"Cleanup error: {e}")
