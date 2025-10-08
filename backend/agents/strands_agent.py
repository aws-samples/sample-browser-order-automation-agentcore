#!/usr/bin/env python3
"""
Strands Agent - Simplified version using Playwright MCP
AI agent for e-commerce automation using AgentCore browser via MCP
"""

import os
import sys
import logging
import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

# Set up logger
logger = logging.getLogger(__name__)

# Add parent directory to path for config import
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import get_config_manager

try:
    from strands import Agent
    from strands.models import BedrockModel
    from strands.tools.mcp import MCPClient
    from mcp import stdio_client, StdioServerParameters
    from bedrock_agentcore.tools.browser_client import (
        BrowserClient as AgentCoreBrowserClient,
    )
except ImportError as e:
    logger.error(f"Required packages not installed: {e}")
    raise


class StrandsAgent:
    """Simplified Strands Agent using Playwright MCP with AgentCore browser"""

    # Class-level lock for session management
    _session_lock = asyncio.Lock()
    _active_sessions = set()

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
        self.agentcore_client = None
        self.mcp_client = None
        self.strands_agent = None
        self._is_processing = False

        # Use the config passed from order_queue (includes AI model)
        self.agent_config = config
        self.region = config.get("agentcore_region", "us-west-2")

    def _add_log(self, level: str, message: str, step: str = None):
        """Add execution log entry"""
        if level == "ERROR":
            logger.error(message)
        elif level == "WARNING":
            logger.warning(message)
        else:
            logger.info(message)

        if self.db_manager and self.session_id:
            try:
                self.db_manager.add_execution_log(self.session_id, level, message, step)

                # Broadcast log update
                try:
                    from app import broadcast_update

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
                        loop = asyncio.get_running_loop()
                        loop.create_task(broadcast_update(log_data))
                    except:
                        pass
                except ImportError:
                    pass
            except Exception as e:
                logger.error(f"Failed to add execution log: {e}")

    async def start_session(self, session_id: str) -> Dict[str, Any]:
        """Start browser session with AgentCore and MCP"""
        async with self._session_lock:
            # Check if session already exists
            if session_id in self._active_sessions:
                self._add_log(
                    "WARNING", f"Session {session_id} already active", "initialization"
                )
                return {
                    "session_id": session_id,
                    "status": "already_active",
                    "automation_method": "strands",
                }

            try:
                self.session_id = session_id
                self._active_sessions.add(session_id)
                self._add_log(
                    "INFO", f"Starting Strands session: {session_id}", "initialization"
                )

                # Create AgentCore browser client using default browser (like Nova Act)
                self.agentcore_client = AgentCoreBrowserClient(region=self.region)
                agentcore_session_id = self.agentcore_client.start(
                    identifier="aws.browser.v1",  # Use default browser like Nova Act
                    session_timeout_seconds=3600,
                )

                # Get CDP connection details
                cdp_url, cdp_headers = self.agentcore_client.generate_ws_headers()
                self._add_log(
                    "INFO",
                    f"AgentCore session created: {agentcore_session_id}",
                    "initialization",
                )

                # Register with BrowserService for live view (like Nova Act)
                try:
                    from services.browser_service import get_browser_service

                    browser_service = get_browser_service()

                    if browser_service:
                        browser_service.register_session(
                            session_id=session_id,
                            browser_client=self.agentcore_client,
                            order_id=session_id,
                            metadata={
                                "automation_method": "strands",
                                "ws_url": cdp_url,
                                "created_at": datetime.now().isoformat(),
                            },
                        )
                        self._add_log(
                            "INFO",
                            "Registered browser session with BrowserService",
                            "initialization",
                        )
                        # Store browser_service reference for later use
                        self.browser_service = browser_service
                except Exception as e:
                    self._add_log(
                        "WARNING",
                        f"Failed to register browser session: {e}",
                        "initialization",
                    )

                # Validate WebSocket URL format (like Nova Act)
                if not cdp_url.startswith("wss://"):
                    error_msg = f"Invalid WebSocket URL format: {cdp_url}"
                    self._add_log("ERROR", error_msg, "initialization")
                    raise RuntimeError("Invalid WebSocket URL format")

                # Create MCP client with CDP headers for Playwright
                cdp_header_args = []
                if cdp_headers:
                    for key, value in cdp_headers.items():
                        cdp_header_args.extend(["--cdp-header", f"{key}:{value}"])

                self._add_log(
                    "INFO",
                    f"Initializing Playwright MCP with WebSocket: {cdp_url[:50]}...",
                    "mcp_setup",
                )

                self.mcp_client = MCPClient(
                    lambda: stdio_client(
                        StdioServerParameters(
                            command="npx",
                            args=[
                                "@playwright/mcp@latest",
                                "--cdp-endpoint",
                                cdp_url,
                                *cdp_header_args,
                                "--browser",
                                "chrome",
                                "--timeout-navigation",
                                "30000",
                                "--timeout-action",
                                "10000",
                            ],
                            env={
                                **os.environ,
                                "NODE_OPTIONS": "--max-old-space-size=2048",
                                "UV_THREADPOOL_SIZE": "4",
                            },
                        )
                    )
                )

                # Initialize MCP tools with better resource management
                def initialize_mcp_tools():
                    tools = []
                    max_retries = 3

                    for attempt in range(max_retries):
                        mcp_context = None
                        try:
                            self._add_log(
                                "INFO",
                                f"Attempting MCP initialization (attempt {attempt + 1})",
                                "initialization",
                            )

                            # Create fresh MCP client for each attempt
                            if attempt > 0:
                                # Recreate MCP client on retry
                                self.mcp_client = MCPClient(
                                    lambda: stdio_client(
                                        StdioServerParameters(
                                            command="npx",
                                            args=[
                                                "@playwright/mcp@latest",
                                                "--cdp-endpoint",
                                                cdp_url,
                                                *cdp_header_args,
                                                "--browser",
                                                "chrome",
                                                "--timeout-navigation",
                                                "30000",
                                                "--timeout-action",
                                                "10000",
                                            ],
                                            env={
                                                **os.environ,
                                                "NODE_OPTIONS": "--max-old-space-size=2048",
                                                "UV_THREADPOOL_SIZE": "4",
                                            },
                                        )
                                    )
                                )

                            mcp_context = self.mcp_client.__enter__()
                            tools = self.mcp_client.list_tools_sync()
                            self._add_log(
                                "INFO",
                                f"Successfully loaded {len(tools)} MCP tools",
                                "initialization",
                            )
                            break

                        except Exception as e:
                            error_msg = str(e)
                            self._add_log(
                                "WARNING",
                                f"MCP initialization failed (attempt {attempt + 1}): {error_msg}",
                                "initialization",
                            )

                            # Cleanup failed context
                            if mcp_context:
                                try:
                                    self.mcp_client.__exit__(None, None, None)
                                except:
                                    pass
                                mcp_context = None

                            # Check for specific error types
                            if (
                                "Connection closed" in error_msg
                                or "client initialization failed" in error_msg
                            ):
                                if attempt < max_retries - 1:
                                    wait_time = (attempt + 1) * 2
                                    self._add_log(
                                        "INFO",
                                        f"Connection issue detected, waiting {wait_time}s before retry",
                                        "initialization",
                                    )
                                    import time

                                    time.sleep(wait_time)
                                    continue

                            if attempt == max_retries - 1:
                                self._add_log(
                                    "ERROR",
                                    f"Failed to initialize MCP after {max_retries} attempts",
                                    "initialization",
                                )
                        finally:
                            # Always cleanup MCP context if still active
                            if mcp_context:
                                try:
                                    self.mcp_client.__exit__(None, None, None)
                                except:
                                    pass

                    return tools

                # Load tools in thread pool with proper cleanup
                import concurrent.futures

                executor = None
                try:
                    executor = concurrent.futures.ThreadPoolExecutor(
                        max_workers=1, thread_name_prefix="mcp-init"
                    )
                    future = executor.submit(initialize_mcp_tools)
                    try:
                        tools = await asyncio.wait_for(
                            asyncio.wrap_future(future), timeout=60.0
                        )
                    except asyncio.TimeoutError:
                        self._add_log(
                            "ERROR", "MCP initialization timed out", "initialization"
                        )
                        future.cancel()
                        tools = []
                finally:
                    if executor:
                        executor.shutdown(wait=False)

                if not tools:
                    raise Exception("Failed to load MCP tools")

                # Use more conservative Bedrock settings for stability
                # Use the model specified in config (passed from order), not default_model
                model_to_use = self.agent_config.get("model") or self.agent_config.get(
                    "default_model"
                )
                self._add_log(
                    "INFO", f"Using AI model: {model_to_use}", "initialization"
                )

                # Enable prompt caching only for Claude Sonnet 3.7 and 4
                supports_caching = (
                    "claude-3-7-sonnet" in model_to_use
                    or "claude-sonnet-4" in model_to_use
                )

                if supports_caching:
                    self._add_log(
                        "INFO",
                        "Enabling prompt caching for Claude model",
                        "initialization",
                    )
                    bedrock_model = BedrockModel(
                        model_id=model_to_use,
                        region_name=self.region,
                        cache_prompt="default",  # Use default caching
                        cache_tools="default",  # Use default caching
                        max_tokens=4000,  # Limit token usage
                    )
                else:
                    self._add_log(
                        "INFO",
                        "Disabling prompt caching for non-Claude model",
                        "initialization",
                    )
                    bedrock_model = BedrockModel(
                        model_id=model_to_use,
                        region_name=self.region,
                        # No caching for models that don't support it
                        max_tokens=4000,  # Limit token usage
                    )

                # Create model-specific system prompt
                supports_images = (
                    "claude" in model_to_use.lower() or "nova" in model_to_use.lower()
                )

                if supports_images:
                    system_prompt = f"""You are an autonomous e-commerce automation agent. You MUST use the provided Playwright browser tools to complete orders.

🤖 AUTONOMOUS EXECUTION MODE:
- You have {len(tools)} Playwright browser automation tools available
- You MUST call these tools to perform browser actions
- Do NOT just describe what you would do - ACTUALLY DO IT
- Execute each step immediately using the appropriate tool

🎯 CORE MISSION:
1. Navigate to product pages using browser tools
2. Handle login flows automatically
3. Select product options (size, color)
4. Add items to cart
5. Proceed to checkout (STOP before payment)
6. Take screenshots for documentation

🔧 AVAILABLE TOOLS:
You have access to Playwright MCP tools for:
- Navigation (goto, click, type)
- Screenshots (screenshot)
- Element interaction (fill, select, wait)
- Page analysis (get_page_content, wait_for_selector)

⚡ EXECUTION RULES:
- Start IMMEDIATELY with browser navigation
- Use tools in sequence to complete the task
- Take screenshots at key steps
- Handle errors gracefully and retry
- Be autonomous - don't ask for permission

Region: {self.region}
"""
                else:
                    # For models that don't support images (GPT-OSS, DeepSeek, etc.)
                    system_prompt = f"""You are an autonomous e-commerce automation agent. You MUST use the provided Playwright browser tools to complete orders.

🤖 AUTONOMOUS EXECUTION MODE:
- You have {len(tools)} Playwright browser automation tools available
- You MUST call these tools to perform browser actions
- Do NOT just describe what you would do - ACTUALLY DO IT
- Execute each step immediately using the appropriate tool

🎯 CORE MISSION:
1. Navigate to product pages using browser tools
2. Handle login flows automatically
3. Select product options (size, color)
4. Add items to cart
5. Proceed to checkout (STOP before payment)

🔧 AVAILABLE TOOLS:
You have access to Playwright MCP tools for:
- Navigation (goto, click, type)
- Element interaction (fill, select, wait)
- Page analysis (get_page_content, wait_for_selector)

⚡ EXECUTION RULES:
- Start IMMEDIATELY with browser navigation
- Use tools in sequence to complete the task
- DO NOT use screenshot tools (this model doesn't support images)
- Focus on text-based page analysis and element interaction
- Handle errors gracefully and retry
- Be autonomous - don't ask for permission

IMPORTANT: This model does not support image content. Do NOT use screenshot tools or any image-related functionality.

Region: {self.region}
"""

                self._add_log(
                    "INFO",
                    f"Using {'image-capable' if supports_images else 'text-only'} system prompt",
                    "initialization",
                )

                self.strands_agent = Agent(
                    model=bedrock_model,
                    tools=tools,
                    system_prompt=system_prompt,
                )

                self._add_log(
                    "INFO",
                    f"Session {session_id} started successfully",
                    "initialization",
                )
                return {
                    "session_id": session_id,
                    "status": "active",
                    "automation_method": "strands",
                    "created_at": datetime.now().isoformat(),
                }

            except Exception as e:
                # Remove from active sessions on failure
                self._active_sessions.discard(session_id)
                error_msg = f"Failed to start session: {e}"
                self._add_log("ERROR", error_msg, "initialization")
                raise

    async def process_order(self, order, progress_callback=None) -> Dict[str, Any]:
        """Process order using MCP Playwright tools"""
        # Prevent concurrent processing
        if self._is_processing:
            return {
                "success": False,
                "status": "failed",
                "error": "Another order is already being processed",
                "automation_method": "strands",
            }

        self._is_processing = True
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
                        "step": "Starting automation",
                        "automation_method": "strands",
                    }
                )

            if not self.strands_agent or not self.mcp_client:
                raise Exception("Strands agent not initialized")

            # Prepare credentials info
            credentials_info = ""
            if self.retailer_config.get("credentials"):
                creds = self.retailer_config["credentials"]
                if creds.get("username") and creds.get("password"):
                    credentials_info = f"""
Login Credentials (use if needed):
- Username: {creds['username']}
- Password: {creds['password']}
"""

            # Create instruction for the agent
            instruction = f"""AUTONOMOUS ORDER EXECUTION TASK

ORDER DETAILS:
Product: {order.product_name}
URL: {order.product_url}
Size: {order.product_size or 'any available'}
Color: {order.product_color or 'any available'}

{credentials_info}

🤖 EXECUTE NOW - Use your browser tools to:

STEP 1: Navigate to product page
- Use goto tool to navigate to: {order.product_url}
- Take screenshot to document the page

STEP 2: Handle login (if required)
- Look for login prompts or sign-in buttons
- If login is needed, use the provided credentials
- Take screenshot after login

STEP 3: Product selection
- Find and select size: {order.product_size or 'any available'}
- Find and select color: {order.product_color or 'any available'}
- Take screenshot of selected options

STEP 4: Add to cart
- Click "Add to Cart" or similar button
- Wait for confirmation
- Take screenshot of cart confirmation

STEP 5: Proceed to checkout
- Navigate to cart/checkout
- STOP before entering payment information
- Take final screenshot

⚡ START EXECUTION IMMEDIATELY - Use your browser tools now!
"""

            if progress_callback:
                await progress_callback(
                    {
                        "order_id": order_id,
                        "status": "processing",
                        "progress": 30,
                        "step": "Executing browser automation",
                        "automation_method": "strands",
                    }
                )

            # Execute with MCP client context in separate thread to avoid blocking
            self._add_log("INFO", "Starting Strands agent execution", "automation")

            def execute_automation():
                new_loop = None
                mcp_context = None
                try:
                    # Create new event loop for this thread
                    import asyncio

                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)

                    try:
                        mcp_context = self.mcp_client.__enter__()
                        self._add_log(
                            "INFO", "MCP client context established", "automation"
                        )

                        # Add retry logic for throttling
                        max_retries = 3
                        for attempt in range(max_retries):
                            try:
                                self._add_log(
                                    "INFO",
                                    f"Calling Strands agent (attempt {attempt + 1})",
                                    "automation",
                                )
                                response = self.strands_agent(instruction)
                                self._add_log(
                                    "INFO",
                                    f"Strands agent responded: {str(response)}",
                                    "automation",
                                )
                                return str(response)
                            except Exception as e:
                                self._add_log(
                                    "ERROR",
                                    f"Strands agent error (attempt {attempt + 1}): {e}",
                                    "automation",
                                )
                                if "throttlingException" in str(
                                    e
                                ) or "Too many requests" in str(e):
                                    if attempt < max_retries - 1:
                                        wait_time = (attempt + 1) * 10
                                        self._add_log(
                                            "WARNING",
                                            f"Throttling detected, waiting {wait_time}s",
                                            "automation",
                                        )
                                        import time

                                        time.sleep(wait_time)
                                        continue
                                if attempt == max_retries - 1:
                                    return f"FAILED: {e}"
                    except Exception as e:
                        self._add_log("ERROR", f"MCP context error: {e}", "automation")
                        return f"FAILED: {e}"
                    finally:
                        # Always cleanup MCP context
                        if mcp_context:
                            try:
                                self.mcp_client.__exit__(None, None, None)
                            except Exception as cleanup_error:
                                self._add_log(
                                    "WARNING",
                                    f"MCP cleanup error: {cleanup_error}",
                                    "automation",
                                )

                except Exception as e:
                    self._add_log(
                        "ERROR", f"Automation thread error: {e}", "automation"
                    )
                    return f"FAILED: {e}"
                finally:
                    # Always cleanup event loop
                    if new_loop:
                        try:
                            new_loop.close()
                        except:
                            pass

            # Run in separate thread with proper resource management
            executor = None
            try:
                import concurrent.futures

                executor = concurrent.futures.ThreadPoolExecutor(
                    max_workers=1, thread_name_prefix=f"strands-{self.session_id[:8]}"
                )
                future = executor.submit(execute_automation)
                try:
                    response_text = await asyncio.wait_for(
                        asyncio.wrap_future(future), timeout=300.0
                    )
                except asyncio.TimeoutError:
                    response_text = "FAILED: Order processing timed out"
                    self._add_log("ERROR", "Order processing timed out", "automation")
                    future.cancel()
            except Exception as e:
                self._add_log("ERROR", f"Thread execution error: {e}", "automation")
                response_text = f"FAILED: {e}"
            finally:
                if executor:
                    executor.shutdown(wait=False)

            self._add_log(
                "INFO", f"Automation completed: {response_text}", "automation"
            )

            # Determine success based on response
            response_lower = response_text.lower()
            if any(
                keyword in response_lower
                for keyword in ["added to cart", "successfully added"]
            ):
                success = True
                status = "completed"
                message = "Order processed successfully"
            elif any(
                keyword in response_lower for keyword in ["error", "failed", "timeout"]
            ):
                success = False
                status = "failed"
                message = "Order processing failed"
            else:
                success = True
                status = "completed"
                message = "Order processing completed"

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
            error_msg = f"Order processing failed: {e}"
            self._add_log("ERROR", error_msg, "automation_failure")
            return {
                "success": False,
                "status": "failed",
                "error": str(e),
                "automation_method": "strands",
            }
        finally:
            self._is_processing = False

    def get_live_view_url(self, expires: int = 300) -> Dict[str, Any]:
        """Get live view URL for browser session (like Nova Act)"""
        try:
            # Try BrowserService first (like Nova Act)
            if self.browser_service and self.session_id:
                self._add_log(
                    "INFO", "Getting live view URL from BrowserService", "live_view"
                )
                result = self.browser_service.get_live_view_url(
                    self.session_id, expires
                )
                if result.get("url"):
                    self._add_log(
                        "INFO",
                        f"Got live view URL: {result['url'][:50]}...",
                        "live_view",
                    )
                    return result
                else:
                    self._add_log(
                        "WARNING",
                        f"BrowserService failed: {result.get('error', 'Unknown error')}",
                        "live_view",
                    )

            # Fallback to direct AgentCore client
            if self.agentcore_client:
                try:
                    live_view_url = self.agentcore_client.generate_live_view_url(
                        expires=expires
                    )
                    if live_view_url:
                        self._add_log(
                            "INFO",
                            f"Generated live view URL directly: {live_view_url[:50]}...",
                            "live_view",
                        )
                        return {
                            "url": live_view_url,
                            "session_id": self.session_id,
                            "type": "dcv",
                            "expires": expires,
                        }
                except Exception as e:
                    self._add_log(
                        "WARNING",
                        f"Direct live view URL generation failed: {e}",
                        "live_view",
                    )

            return {"url": None, "error": "No active browser session"}
        except Exception as e:
            logger.error(f"Failed to get live view URL: {e}")
            return {"url": None, "error": str(e)}

    def enable_manual_control(self) -> Dict[str, Any]:
        """Enable manual control via BrowserService (like Nova Act)"""
        try:
            if not self.browser_service or not self.session_id:
                return {"success": False, "error": "No active browser session"}

            result = self.browser_service.enable_manual_control(self.session_id)
            if result.get("success"):
                self._add_log("INFO", "Manual control enabled", "manual_control")
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    def disable_manual_control(self) -> Dict[str, Any]:
        """Disable manual control via BrowserService (like Nova Act)"""
        try:
            if not self.browser_service or not self.session_id:
                return {"success": False, "error": "No active browser session"}

            result = self.browser_service.disable_manual_control(self.session_id)
            if result.get("success"):
                self._add_log("INFO", "Manual control disabled", "manual_control")
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_session_status(self) -> Dict[str, Any]:
        """Get session status via BrowserService (like Nova Act)"""
        try:
            if not self.browser_service or not self.session_id:
                return {"exists": False, "status": "not_active"}

            return self.browser_service.get_session_info(self.session_id)
        except Exception as e:
            return {"exists": False, "status": "error", "error": str(e)}

    def change_browser_resolution(self, width: int, height: int) -> Dict[str, Any]:
        """Change browser resolution via BrowserService (like Nova Act)"""
        try:
            if not self.browser_service or not self.session_id:
                return {"success": False, "error": "No active browser session"}

            return self.browser_service.change_browser_resolution(
                self.session_id, width, height
            )
        except Exception as e:
            logger.error(f"Failed to change resolution: {e}")
            return {"success": False, "error": str(e)}

    async def cleanup(self, force: bool = False):
        """Clean up agent resources with improved memory management"""
        async with self._session_lock:
            cleanup_errors = []
            try:
                self._add_log(
                    "INFO", f"Cleaning up session {self.session_id}", "cleanup"
                )

                # Remove from active sessions first
                if self.session_id:
                    self._active_sessions.discard(self.session_id)

                # Reset processing flag
                self._is_processing = False

                # Clean up Strands agent first (releases model resources)
                if self.strands_agent:
                    try:
                        # Clear agent reference to free memory
                        self.strands_agent = None
                        self._add_log("INFO", "Strands agent cleared", "cleanup")
                    except Exception as e:
                        cleanup_errors.append(f"Strands agent cleanup: {e}")

                # Clean up MCP client with timeout
                if self.mcp_client:
                    try:
                        # Force cleanup with timeout to prevent hanging
                        import concurrent.futures

                        def cleanup_mcp():
                            try:
                                # MCP client cleanup is handled by context manager
                                self.mcp_client = None
                            except Exception as e:
                                return str(e)
                            return None

                        with concurrent.futures.ThreadPoolExecutor(
                            max_workers=1
                        ) as executor:
                            future = executor.submit(cleanup_mcp)
                            try:
                                error = await asyncio.wait_for(
                                    asyncio.wrap_future(future), timeout=5.0
                                )
                                if error:
                                    cleanup_errors.append(f"MCP cleanup: {error}")
                                else:
                                    self._add_log(
                                        "INFO", "MCP client cleaned up", "cleanup"
                                    )
                            except asyncio.TimeoutError:
                                cleanup_errors.append("MCP cleanup timed out")
                                future.cancel()
                    except Exception as e:
                        cleanup_errors.append(f"MCP cleanup error: {e}")

                # Clean up AgentCore client
                if self.agentcore_client:
                    try:
                        self.agentcore_client.stop()
                        self.agentcore_client = None
                        self._add_log("INFO", "AgentCore client stopped", "cleanup")
                    except Exception as e:
                        cleanup_errors.append(f"AgentCore cleanup: {e}")

                # Unregister from BrowserService
                if self.browser_service and self.session_id:
                    try:
                        self.browser_service.cleanup_session(self.session_id)
                        self._add_log(
                            "INFO", "Unregistered from BrowserService", "cleanup"
                        )
                    except Exception as e:
                        cleanup_errors.append(f"BrowserService cleanup: {e}")

                # Clear all references
                self.session_id = None
                self.browser_service = None

                if cleanup_errors:
                    error_msg = f"Cleanup completed with {len(cleanup_errors)} errors: {'; '.join(cleanup_errors)}"
                    self._add_log("WARNING", error_msg, "cleanup")
                    logger.warning(error_msg)
                else:
                    logger.info("StrandsAgent cleanup completed successfully")

            except Exception as e:
                error_msg = f"Critical cleanup error: {e}"
                logger.error(error_msg)
                if hasattr(self, "_add_log"):
                    self._add_log("ERROR", error_msg, "cleanup")
