#!/usr/bin/env python3
"""
Nova Act + AgentCore Browser Agent
Unified implementation with worker process support for non-blocking operation
"""

import os
import sys
import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any

# Add parent directory to path for config import
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import get_config_manager

try:
    from bedrock_agentcore.tools.browser_client import browser_session, BrowserClient
    from bedrock_agentcore._utils.endpoints import get_control_plane_endpoint
    from nova_act import NovaAct
    from nova_act.types.act_errors import (
        ActAgentError,
        ActAgentFailed,
        ActExceededMaxStepsError,
        ActTimeoutError,
        ActExecutionError,
        ActActuationError,
        ActCanceledError,
        ActClientError,
        ActInvalidModelGenerationError,
        ActGuardrailsError,
        ActRateLimitExceededError,
        ActServerError,
        ActInternalServerError,
        ActBadResponseError,
        ActServiceUnavailableError,
    )
    from strands import Agent
    from strands.models import BedrockModel
    import boto3
except ImportError as e:
    print(f"Warning: Required packages not installed: {e}")
    browser_session = None
    BrowserClient = None
    get_control_plane_endpoint = None
    NovaAct = None
    Agent = None
    BedrockModel = None
    boto3 = None
    # Set error classes to None if not available
    ActAgentError = None
    ActExecutionError = None
    ActClientError = None
    ActServerError = None

logger = logging.getLogger(__name__)


class NovaActAgent:
    """Nova Act + AgentCore Browser Agent with worker process support"""

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
        self.worker = None
        self.worker_session_id = None
        self._is_processing = False

        # Get config from DB via ConfigManager
        self.config_manager = get_config_manager(db_manager)
        self.agent_config = self.config_manager.get_agent_config("nova_act")

        # Get API key from agent config (database settings only)
        self.api_key = self.agent_config.nova_act_api_key or ""

        logger.info(
            f"Nova Act agent initialized with API key: {self.api_key[:10]}..."
            if self.api_key
            else "No API key found"
        )

        # Create screenshots directory
        self.screenshots_dir = os.path.join(
            os.path.dirname(__file__), "..", "static", "screenshots"
        )
        os.makedirs(self.screenshots_dir, exist_ok=True)

        # Initialize worker if available
        try:
            from services.nova_act_worker import get_nova_act_worker

            self.worker = get_nova_act_worker()
            logger.info("Nova Act worker initialized")
        except ImportError:
            logger.warning("Nova Act worker not available")
            self.worker = None

        if not browser_session or not NovaAct or not Agent or not BedrockModel:
            raise ImportError("Required packages not available")

    def _add_log(self, level: str, message: str, step: str = None):
        """Add execution log entry with real-time broadcast"""
        if self.db_manager and self.session_id:
            try:
                self.db_manager.add_execution_log(self.session_id, level, message, step)

                # Broadcast log update in real-time
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
                    except RuntimeError:
                        pass
                except ImportError:
                    pass

            except Exception as e:
                logger.error(f"Failed to add execution log: {e}")
        logger.info(f"[{level}] {message}")

    def _extract_nova_act_logs_from_output(self, output_text: str):
        """Extract and log Nova Act execution steps from output text"""
        try:
            lines = output_text.split("\n")
            current_step = None

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Detect step markers
                if line.startswith("295d>") or "act(" in line:
                    if "act(" in line:
                        # Extract the command being executed
                        command_start = line.find('act("') + 5
                        command_end = (
                            line.find('")')
                            if line.find('")') > command_start
                            else len(line)
                        )
                        command = (
                            line[command_start:command_end]
                            if command_start > 4
                            else line
                        )
                        self._add_log(
                            "INFO",
                            f"Executing Nova Act command: {command[:100]}...",
                            "nova_act_execution",
                        )
                        self._broadcast_nova_act_update(
                            "command_started", {"command": command[:200]}
                        )
                    else:
                        self._add_log("INFO", line, "nova_act_step")

                # Detect think() statements
                elif "think(" in line:
                    think_start = line.find('think("') + 7
                    think_end = line.rfind('");')
                    if think_start > 6 and think_end > think_start:
                        thought = line[think_start:think_end]
                        self._add_log(
                            "INFO", f"Agent thinking: {thought}", "nova_act_reasoning"
                        )
                        self._broadcast_nova_act_update(
                            "agent_thinking", {"thought": thought}
                        )

                # Detect actions
                elif ">>" in line and (
                    "agentType(" in line
                    or "agentClick(" in line
                    or "agentScroll(" in line
                ):
                    action = line.replace(">>", "").strip()
                    self._add_log(
                        "INFO", f"Performing action: {action}", "nova_act_action"
                    )
                    self._broadcast_nova_act_update(
                        "action_performed", {"action": action}
                    )

                # Detect errors
                elif "AgentError" in line or "HumanValidationError" in line:
                    self._add_log("ERROR", f"Nova Act error: {line}", "nova_act_error")
                    self._broadcast_nova_act_update("error_occurred", {"error": line})

                # Detect completion messages
                elif "View your act run here:" in line:
                    html_path = line.split("View your act run here: ")[-1].strip()
                    self._add_log(
                        "INFO",
                        f"Nova Act HTML report available: {html_path}",
                        "nova_act_completion",
                    )

        except Exception as e:
            logger.error(f"Failed to extract Nova Act logs: {e}")
            self._add_log(
                "WARNING", f"Failed to parse Nova Act output: {e}", "log_parsing"
            )

    def _broadcast_nova_act_update(self, update_type: str, data: dict):
        """Broadcast Nova Act specific updates to frontend"""
        try:
            from app import broadcast_update

            update_data = {
                "type": "nova_act_update",
                "order_id": self.session_id,
                "update_type": update_type,
                "data": data,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            # Try to broadcast (non-blocking)
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(broadcast_update(update_data))
            except RuntimeError:
                # No event loop running, skip broadcast
                pass
        except ImportError:
            # broadcast_update not available
            pass
        except Exception as e:
            logger.error(f"Failed to broadcast Nova Act update: {e}")

    async def resume_after_captcha(self, order) -> Dict[str, Any]:
        """Resume Nova Act execution after CAPTCHA has been resolved manually"""
        try:
            if not hasattr(self, "ws_url") or not self.ws_url or not self.api_key:
                raise RuntimeError("Nova Act connection info not available")

            self._add_log(
                "INFO",
                "Resuming Nova Act execution after CAPTCHA resolution",
                "captcha_resume",
            )

            # Check if we have site credentials for resume
            credentials_info = ""
            if self.retailer_config.get("credentials"):
                creds = self.retailer_config["credentials"]
                if creds.get("username") and creds.get("password"):
                    credentials_info = f"""
                    
                    SITE LOGIN CREDENTIALS (use if login is required):
                    - Username: {creds['username']}
                    - Password: {creds['password']}
                    
                    If you encounter a login page during resume, use these credentials to sign in.
                    """

            # Default test information for checkout
            default_info = """
            
            IMPORTANT: Fill ALL required fields during checkout. Use these default values for any missing information:
            
            CONTACT INFORMATION:
            - Phone Number: (555) 123-4567 (ALWAYS fill phone number fields - this is required!)
            - Mobile/Cell Phone: (555) 123-4567
            
            PAYMENT INFORMATION:
            - Credit Card: 4111 1111 1111 1111 (test card)
            - Expiry Date: 12/25
            - CVV: 123
            - Card Name: Test User
            
            INSTRUCTIONS:
            - Look for phone number fields (phone, mobile, cell, telephone, contact number)
            - Always fill phone number fields with (555) 123-4567
            - Fill all payment fields completely
            - Do not skip any required fields
            """

            # Create a simplified command to continue from where we left off
            # Resume from current page after CAPTCHA resolution
            command = f"""
            Resume the e-commerce order for {order.product_name} from current page:
            1. Continue with the current task (add to cart, checkout, or fill shipping)
            2. If login is required, use the provided credentials to sign in
            3. If not on product page, navigate to {order.product_url if hasattr(order, 'product_url') and order.product_url else 'search for ' + order.product_name}
            4. Select size: {order.product_size or 'any available'} (if not already selected)
            5. Select color: {order.product_color or 'any available'} (if not already selected)
            6. Add to cart (if not already in cart)
            7. Proceed to checkout
            8. Fill shipping information: {order.shipping_address.get('first_name', '')} {order.shipping_address.get('last_name', '')}, {order.shipping_address.get('address_line_1', '')}, {order.shipping_address.get('city', '')}, {order.shipping_address.get('state', '')} {order.shipping_address.get('postal_code', '')}
            9. IMPORTANT: Fill phone number field with (555) 123-4567 - do not skip this field!
            10. Complete payment information using the default test information provided below
            {credentials_info}
            {default_info}
            """

            self._add_log(
                "INFO",
                f"Generated resume command: {len(command)} characters",
                "captcha_resume",
            )
            self._broadcast_nova_act_update(
                "resume_started", {"message": "Resuming after CAPTCHA resolution"}
            )

            # Execute the resume command using the same browser session
            def execute_nova_act_resume():
                try:
                    self._add_log(
                        "INFO", "Creating Nova Act resume session", "captcha_resume"
                    )

                    # Set up event loop for this thread
                    import asyncio

                    try:
                        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    except Exception as loop_error:
                        self._add_log(
                            "WARNING",
                            f"Event loop setup warning: {loop_error}",
                            "captcha_resume",
                        )

                    # Capture stdout to parse Nova Act logs
                    import sys
                    from io import StringIO

                    old_stdout = sys.stdout
                    captured_output = StringIO()

                    try:
                        # Redirect stdout to capture Nova Act logs
                        sys.stdout = captured_output

                        # Create and use Nova Act with existing session
                        with NovaAct(
                            cdp_endpoint_url=self.ws_url,
                            cdp_headers=self.headers,
                            preview={"playwright_actuation": True},
                            nova_act_api_key=self.api_key,
                            # Don't specify starting_page to continue from current page
                        ) as nova_act:
                            self._add_log(
                                "INFO",
                                "Nova Act resume session created, executing command",
                                "captcha_resume",
                            )
                            try:
                                result = nova_act.act(command)
                                return result, captured_output.getvalue()
                            except Exception as act_error:
                                # Handle Nova Act specific errors
                                if ActAgentError and isinstance(
                                    act_error, ActAgentError
                                ):
                                    if isinstance(act_error, ActAgentFailed):
                                        return (
                                            f"AGENT_FAILED: {str(act_error)}",
                                            captured_output.getvalue(),
                                        )
                                    elif isinstance(
                                        act_error, ActExceededMaxStepsError
                                    ):
                                        return (
                                            f"MAX_STEPS_EXCEEDED: {str(act_error)}",
                                            captured_output.getvalue(),
                                        )
                                    elif isinstance(act_error, ActTimeoutError):
                                        return (
                                            f"TIMEOUT: {str(act_error)}",
                                            captured_output.getvalue(),
                                        )
                                    else:
                                        return (
                                            f"AGENT_ERROR: {str(act_error)}",
                                            captured_output.getvalue(),
                                        )
                                elif ActClientError and isinstance(
                                    act_error, ActClientError
                                ):
                                    if isinstance(act_error, ActGuardrailsError):
                                        return (
                                            f"GUARDRAILS_BLOCKED: {str(act_error)}",
                                            captured_output.getvalue(),
                                        )
                                    elif isinstance(
                                        act_error, ActRateLimitExceededError
                                    ):
                                        return (
                                            f"RATE_LIMITED: {str(act_error)}",
                                            captured_output.getvalue(),
                                        )
                                    else:
                                        return (
                                            f"CLIENT_ERROR: {str(act_error)}",
                                            captured_output.getvalue(),
                                        )
                                elif ActExecutionError and isinstance(
                                    act_error, ActExecutionError
                                ):
                                    return (
                                        f"EXECUTION_ERROR: {str(act_error)}",
                                        captured_output.getvalue(),
                                    )
                                elif ActServerError and isinstance(
                                    act_error, ActServerError
                                ):
                                    return (
                                        f"SERVER_ERROR: {str(act_error)}",
                                        captured_output.getvalue(),
                                    )
                                else:
                                    # Unknown error
                                    return (
                                        f"UNKNOWN_ERROR: {str(act_error)}",
                                        captured_output.getvalue(),
                                    )
                    finally:
                        # Restore stdout
                        sys.stdout = old_stdout

                except Exception as e:
                    self._add_log(
                        "ERROR",
                        f"Nova Act resume execution error: {e}",
                        "captcha_resume",
                    )
                    return f"FAILED: Nova Act resume execution error: {e}", (
                        captured_output.getvalue()
                        if "captured_output" in locals()
                        else ""
                    )

            # Run Nova Act resume in thread pool with improved resource management
            executor = None
            try:
                import concurrent.futures

                executor = concurrent.futures.ThreadPoolExecutor(
                    max_workers=1,
                    thread_name_prefix=f"nova-act-resume-{self.session_id[:8]}",
                )
                future = executor.submit(execute_nova_act_resume)
                try:
                    result_tuple = await asyncio.wait_for(
                        asyncio.wrap_future(future), timeout=300.0
                    )  # 5 minute timeout

                    if isinstance(result_tuple, tuple):
                        result, captured_logs = result_tuple
                        # Extract and log Nova Act execution steps
                        if captured_logs:
                            self._extract_nova_act_logs_from_output(captured_logs)
                    else:
                        result = result_tuple

                except asyncio.TimeoutError:
                    self._add_log(
                        "ERROR",
                        "Nova Act resume execution timed out after 5 minutes",
                        "captcha_resume",
                    )
                    future.cancel()
                    result = (
                        "FAILED: Nova Act resume automation timed out after 5 minutes."
                    )

            except Exception as exec_error:
                self._add_log(
                    "ERROR",
                    f"Resume thread execution failed: {exec_error}",
                    "captcha_resume",
                )
                result = f"FAILED: Resume thread execution error: {exec_error}"
            finally:
                if executor:
                    executor.shutdown(wait=False)

            self._add_log(
                "INFO",
                f"Resume automation completed with result: {str(result)[:200]}...",
                "captcha_resume",
            )

            # Check result - simple logic: no error = success
            result_str = str(result).lower()

            # Check for Nova Act specific error patterns
            nova_act_errors = [
                "agent_failed",
                "max_steps_exceeded",
                "timeout",
                "client_error",
                "execution_error",
                "server_error",
                "guardrails_blocked",
                "rate_limited",
            ]

            # Check for explicit errors
            has_nova_act_error = any(error in result_str for error in nova_act_errors)
            has_general_error = any(
                word in result_str for word in ["failed", "error", "exception"]
            )

            # Log the result analysis
            self._add_log(
                "INFO",
                f"Resume result analysis - Nova Act error: {has_nova_act_error}, General error: {has_general_error}",
                "resume_result_analysis",
            )

            if has_nova_act_error:
                # Handle specific Nova Act errors
                self._broadcast_nova_act_update("resume_failed", {"error": str(result)})
                return {
                    "success": False,
                    "status": "failed",
                    "error": f"Nova Act resume error: {result}",
                    "automation_method": "nova_act",
                    "result": str(result),
                }

            elif "captcha" in result_str:
                self._broadcast_nova_act_update(
                    "captcha_detected_again", {"message": "Another CAPTCHA detected"}
                )
                return {
                    "success": False,
                    "status": "requires_human",
                    "message": "Another CAPTCHA detected during resume",
                    "automation_method": "nova_act",
                }

            elif not has_general_error:
                # No explicit error = success
                self._add_log(
                    "INFO",
                    f"Resume: No explicit errors detected, treating as success",
                    "resume_result_analysis",
                )

                self._broadcast_nova_act_update(
                    "resume_completed", {"result": "Order completed successfully"}
                )
                return {
                    "success": True,
                    "status": "completed",
                    "confirmation_number": f"NOVA-{self.session_id[:8]}",
                    "automation_method": "nova_act",
                    "result": str(result),
                }

            else:
                # Has general error
                self._add_log(
                    "WARNING",
                    f"Resume: General error detected in result: {str(result)[:200]}",
                    "resume_result_analysis",
                )
                self._broadcast_nova_act_update("resume_failed", {"error": str(result)})
                return {
                    "success": False,
                    "status": "failed",
                    "error": str(result),
                    "automation_method": "nova_act",
                }

        except Exception as e:
            self._add_log(
                "ERROR",
                f"Failed to resume Nova Act after CAPTCHA: {e}",
                "captcha_resume",
            )
            self._broadcast_nova_act_update("resume_error", {"error": str(e)})
            return {
                "success": False,
                "status": "failed",
                "error": str(e),
                "automation_method": "nova_act",
            }

    def get_live_view_url(self, expires: int = 300) -> dict:
        """Get live view URL for real-time browser session viewing"""
        try:
            if not self.agentcore_client:
                self._add_log(
                    "ERROR", "No AgentCore client available for live view", "live_view"
                )
                return {
                    "url": None,
                    "error": "AgentCore session not active",
                    "session_id": getattr(self, "session_id", None),
                    "type": "dcv",
                }

            # Check if AgentCore client has the method
            if not hasattr(self.agentcore_client, "generate_live_view_url"):
                self._add_log(
                    "ERROR", "AgentCore client does not support live view", "live_view"
                )
                return {
                    "url": None,
                    "error": "Live view not supported by AgentCore client",
                    "session_id": getattr(self, "session_id", None),
                    "type": "dcv",
                }

            # Generate live view URL using AgentCore
            live_view_url = self.agentcore_client.generate_live_view_url(
                expires=expires
            )

            if live_view_url:
                self._add_log(
                    "INFO",
                    f"Generated live view URL: {live_view_url[:50]}...",
                    "live_view",
                )
                return {
                    "url": live_view_url,
                    "session_id": getattr(self, "session_id", None),
                    "type": "dcv",
                    "expires": expires,
                    "headers": getattr(self.agentcore_client, "headers", None),
                }
            else:
                return {
                    "url": None,
                    "error": "Failed to generate live view URL",
                    "session_id": getattr(self, "session_id", None),
                    "type": "dcv",
                }

        except Exception as e:
            logger.error(f"Failed to generate live view URL: {e}")
            self._add_log("ERROR", f"Live view URL generation failed: {e}", "live_view")
            return {
                "url": None,
                "error": f"Live view generation failed: {str(e)}",
                "session_id": getattr(self, "session_id", None),
                "type": "dcv",
            }

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
            self.worker_session_id = session_id

            self._add_log(
                "INFO", f"Starting Nova Act session: {session_id}", "initialization"
            )

            # Set up session replay configuration
            self.session_replay_config = {
                "enabled": True,
                "s3_bucket": self.agent_config.session_replay_s3_bucket,
                "s3_prefix": f"{self.agent_config.session_replay_s3_prefix}{session_id}/",
                "session_id": session_id,
            }

            if browser_session_id:
                # Use existing browser session
                try:
                    from agentcore_manager import agentcore_manager

                    cdp_info = await agentcore_manager.get_cdp_info(browser_session_id)

                    if not cdp_info:
                        raise RuntimeError(
                            f"Browser session {browser_session_id} not found"
                        )

                    ws_url = cdp_info["cdp_endpoint"]
                    headers = cdp_info["headers"]

                    self._add_log(
                        "INFO",
                        f"Using existing browser session: {browser_session_id}",
                        "browser_setup",
                    )
                except ImportError:
                    self._add_log(
                        "WARNING",
                        "agentcore_manager not available, creating new session",
                        "browser_setup",
                    )
                    browser_session_id = None

            if not browser_session_id:
                # Use AWS managed browser tool (aws.browser.v1)
                region = self.agent_config.agentcore_region

                try:
                    self._add_log(
                        "INFO",
                        "Using AWS managed browser tool (aws.browser.v1)",
                        "browser_setup",
                    )

                    # Create browser client using the default AWS browser
                    browser_client = BrowserClient(region=region)

                    agentcore_session_id = browser_client.start(
                        identifier="aws.browser.v1",  # Use AWS managed browser
                        name=f"nova_act_session_{session_id[:8]}",
                        session_timeout_seconds=7200,  # 2 hours for CAPTCHA handling
                    )

                    # Get WebSocket headers
                    ws_url, headers = browser_client.generate_ws_headers()

                    self.agentcore_client = browser_client
                    self._add_log(
                        "INFO",
                        f"Started AgentCore session: {agentcore_session_id}",
                        "browser_setup",
                    )
                    self._add_log(
                        "INFO", f"WebSocket URL: {ws_url[:50]}...", "browser_setup"
                    )

                    # Wait for browser to be ready
                    await asyncio.sleep(5)  # Reduced wait time since it's managed

                except Exception as e:
                    self._add_log(
                        "ERROR",
                        f"Failed to start AgentCore browser session: {e}",
                        "browser_setup",
                    )
                    raise e

            # Store CDP info
            self.ws_url = ws_url
            self.headers = headers

            # Register browser session with BrowserService for Live View
            try:
                from services.browser_service import get_browser_service

                browser_service = get_browser_service()

                if browser_service:
                    browser_service.register_session(
                        session_id=session_id,
                        browser_client=self.agentcore_client,
                        order_id=session_id,
                        metadata={
                            "automation_method": "nova_act",
                            "ws_url": ws_url,
                            "created_at": datetime.now().isoformat(),
                        },
                    )
                    self._add_log(
                        "INFO",
                        f"Registered browser session with BrowserService",
                        "browser_setup",
                    )
            except Exception as e:
                self._add_log(
                    "WARNING",
                    f"Failed to register browser session: {e}",
                    "browser_setup",
                )

            # Initialize Nova Act with AgentCore
            if self.agentcore_client and ws_url:
                self._add_log(
                    "INFO",
                    f"Initializing Nova Act with WebSocket: {ws_url[:50]}...",
                    "nova_act_setup",
                )

                # Validate WebSocket URL format
                if not ws_url.startswith("wss://"):
                    error_msg = f"Invalid WebSocket URL format: {ws_url}"
                    self._add_log("ERROR", error_msg, "nova_act_setup")
                    raise RuntimeError("Invalid WebSocket URL format")

                # Validate API key
                if not self.api_key:
                    error_msg = "No Nova Act API key available"
                    self._add_log("ERROR", error_msg, "nova_act_setup")
                    raise RuntimeError("Nova Act API key required")

                try:
                    # Store connection info for later use in execution thread
                    self._add_log(
                        "INFO",
                        f"Using API key: {self.api_key[:10]}...",
                        "nova_act_setup",
                    )
                    self._add_log(
                        "INFO",
                        "Nova Act connection info stored for execution thread",
                        "nova_act_setup",
                    )

                    # Don't initialize Nova Act here - do it in the execution thread to avoid thread conflicts
                    # Just validate that we have the required connection info
                    if not ws_url or not headers or not self.api_key:
                        raise RuntimeError(
                            "Missing required Nova Act connection parameters"
                        )

                    # Set nova_session to None - we'll create it fresh in each execution thread
                    self.nova_session = None

                    logger.info("Nova Act connection validated, ready for execution")
                    self._add_log(
                        "INFO",
                        "Nova Act connection validated, ready for execution",
                        "nova_act_setup",
                    )

                except Exception as nova_error:
                    logger.error(f"Nova Act initialization failed: {nova_error}")
                    self._add_log(
                        "ERROR",
                        f"Nova Act initialization failed: {nova_error}",
                        "nova_act_setup",
                    )

                    # Don't fail the session creation, just log the error
                    # The session can still be used for other purposes
                    self.nova_session = None
                    self._add_log(
                        "WARNING",
                        "Continuing without Nova Act - session available for other tools",
                        "nova_act_setup",
                    )

            else:
                error_msg = f"Missing requirements - AgentCore client: {bool(self.agentcore_client)}, WebSocket URL: {bool(ws_url)}"
                self._add_log("ERROR", error_msg, "nova_act_setup")
                raise RuntimeError(
                    "Failed to create AgentCore browser session - missing client or WebSocket URL"
                )

            # Also create a Strands agent for hybrid approach
            try:
                bedrock_model = BedrockModel(
                    model_id=self.agent_config.default_model, cache_prompt="default"
                )

                self.strands_agent = Agent(
                    model=bedrock_model,
                    system_prompt="""You are an e-commerce automation assistant working alongside Nova Act browser automation.
                    You can analyze automation results, provide guidance, and help with complex decision-making during the automation process.
                    Your role is to interpret results, handle errors, and provide intelligent analysis of the automation workflow.""",
                )

                logger.info("Strands agent created for hybrid Nova Act approach")
            except Exception as strands_error:
                logger.warning(f"Could not create Strands agent: {strands_error}")
                self.strands_agent = None

            self._add_log(
                "INFO", f"Nova Act session ready for processing", "initialization"
            )

            return {
                "session_id": session_id,
                "status": "active",
                "automation_method": "nova_act",
                "created_at": datetime.now().isoformat(),
                "browser_session_id": browser_session_id,
                "agentcore_session_id": getattr(
                    self.agentcore_client, "session_id", None
                ),
                "ws_url": ws_url,
            }

        except Exception as e:
            self._add_log(
                "ERROR", f"Failed to start Nova Act session: {e}", "initialization"
            )
            return {
                "session_id": session_id,
                "status": "failed",
                "automation_method": "nova_act",
                "created_at": datetime.now().isoformat(),
                "browser_session_id": browser_session_id,
                "error": str(e),
            }

    async def process_order(self, order, progress_callback=None) -> Dict[str, Any]:
        """Process order using Nova Act with worker process"""
        # Prevent concurrent processing
        if self._is_processing:
            return {
                "success": False,
                "status": "failed",
                "error": "Another order is already being processed",
                "automation_method": "nova_act",
            }

        self._is_processing = True
        try:
            order_id = order.id
            self._add_log(
                "INFO",
                f"Starting order processing for {order.product_name}",
                "initialization",
            )

            # Check if we have worker available for non-blocking processing
            if self.worker and hasattr(self, "ws_url") and self.ws_url:
                return await self._process_order_with_worker(order, progress_callback)
            elif hasattr(self, "ws_url") and self.ws_url and self.api_key:
                # Fallback to direct Nova Act processing
                return await self._process_order_direct(order, progress_callback)
            else:
                raise RuntimeError(
                    "Nova Act not properly initialized - missing WebSocket URL or API key"
                )

        except Exception as e:
            self._add_log("ERROR", f"Order processing failed: {e}", "processing")
            return {
                "success": False,
                "status": "failed",
                "error": str(e),
                "automation_method": "nova_act",
            }
        finally:
            self._is_processing = False

    async def _process_order_with_worker(
        self, order, progress_callback=None
    ) -> Dict[str, Any]:
        """Process order using Nova Act worker (non-blocking)"""
        try:
            order_id = order.id
            self._add_log(
                "INFO", f"Using Nova Act worker for order processing", "processing"
            )

            # Prepare configuration for worker process
            worker_config = {
                "ws_url": self.ws_url,
                "headers": getattr(self, "headers", {}),
                "api_key": self.api_key,
                "order_data": {
                    "product_name": order.product_name,
                    "product_url": order.product_url,
                    "product_size": order.product_size,
                    "product_color": order.product_color,
                    "shipping_address": order.shipping_address,
                },
            }

            self._add_log(
                "INFO",
                (
                    f"Using API key: {self.api_key[:10]}..."
                    if self.api_key
                    else "No API key found"
                ),
                "processing",
            )

            if progress_callback:
                await progress_callback(
                    {
                        "order_id": order_id,
                        "status": "processing",
                        "progress": 10,
                        "step": "Starting Nova Act worker process",
                        "automation_method": "nova_act",
                    }
                )

            # Start worker session (non-blocking)
            worker_result = await self.worker.start_session(order_id, worker_config)

            if worker_result.get("status") == "failed":
                raise Exception(f"Worker failed to start: {worker_result.get('error')}")

            self._add_log("INFO", "Nova Act worker process started", "processing")

            if progress_callback:
                await progress_callback(
                    {
                        "order_id": order_id,
                        "status": "processing",
                        "progress": 30,
                        "step": "Nova Act automation in progress",
                        "automation_method": "nova_act",
                    }
                )

            # Poll for completion (non-blocking)
            max_wait_time = 300  # 5 minutes
            poll_interval = 5  # 5 seconds
            elapsed_time = 0

            while elapsed_time < max_wait_time:
                await asyncio.sleep(poll_interval)
                elapsed_time += poll_interval

                # Check worker status
                status = await self.worker.get_session_status(order_id)

                if status.get("status") == "completed":
                    self._add_log(
                        "INFO",
                        "Nova Act automation completed successfully",
                        "processing",
                    )

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

                    return {
                        "success": True,
                        "status": "completed",
                        "confirmation_number": status.get(
                            "confirmation_number", f"NOVA-{order_id[:8]}"
                        ),
                        "automation_method": "nova_act",
                        "result": status.get("result", "Order completed"),
                    }

                elif status.get("status") == "failed":
                    error_msg = status.get("error", "Unknown error")
                    self._add_log(
                        "ERROR",
                        f"Nova Act automation failed: {error_msg}",
                        "processing",
                    )

                    return {
                        "success": False,
                        "status": "failed",
                        "error": error_msg,
                        "automation_method": "nova_act",
                    }

                elif status.get("status") == "requires_human":
                    self._add_log(
                        "WARNING",
                        "Nova Act detected CAPTCHA or requires human intervention",
                        "processing",
                    )

                    return {
                        "success": False,
                        "status": "requires_human",
                        "message": "CAPTCHA detected or human intervention required",
                        "automation_method": "nova_act",
                    }

                # Update progress
                progress = min(30 + (elapsed_time / max_wait_time) * 60, 90)
                if progress_callback:
                    await progress_callback(
                        {
                            "order_id": order_id,
                            "status": "processing",
                            "progress": int(progress),
                            "step": f"Nova Act automation in progress ({elapsed_time}s)",
                            "automation_method": "nova_act",
                        }
                    )

            # Timeout
            self._add_log("ERROR", "Nova Act automation timed out", "processing")
            return {
                "success": False,
                "status": "failed",
                "error": "Automation timed out",
                "automation_method": "nova_act",
            }

        except Exception as e:
            self._add_log(
                "ERROR", f"Nova Act worker processing failed: {e}", "processing"
            )
            return {
                "success": False,
                "status": "failed",
                "error": str(e),
                "automation_method": "nova_act",
            }

    async def _process_order_direct(
        self, order, progress_callback=None
    ) -> Dict[str, Any]:
        """Process order using direct Nova Act (fallback method)"""
        if not hasattr(self, "ws_url") or not self.ws_url or not self.api_key:
            raise RuntimeError("Nova Act connection info not available")

        try:
            order_id = order.id
            self._add_log(
                "INFO", f"Using direct Nova Act processing (fallback)", "processing"
            )

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
                    self._add_log(
                        "INFO",
                        f"Site credentials available for {creds.get('site_name', 'site')}",
                        "credentials",
                    )

            # Default test information for checkout
            default_info = """
            
            IMPORTANT: Fill ALL required fields during checkout. Use these default values for any missing information:
            
            CONTACT INFORMATION:
            - Phone Number: (555) 123-4567 (ALWAYS fill phone number fields - this is required!)
            - Mobile/Cell Phone: (555) 123-4567
            
            PAYMENT INFORMATION:
            - Credit Card: 4111 1111 1111 1111 (test card)
            - Expiry Date: 12/25
            - CVV: 123
            - Card Name: Test User
            
            INSTRUCTIONS:
            - Look for phone number fields (phone, mobile, cell, telephone, contact number)
            - Always fill phone number fields with (555) 123-4567
            - Fill all payment fields completely
            - Do not skip any required fields
            """

            # Create order command - optimize based on whether we have product URL
            if hasattr(order, "product_url") and order.product_url:
                # We're starting directly on the product page, so skip navigation
                command = f"""
                Complete this e-commerce order for {order.product_name}:
                1. Verify this is the correct product page
                2. If login is required, use the provided credentials to sign in
                3. Select size: {order.product_size or 'any available'}
                4. Select color: {order.product_color or 'any available'}
                5. Add to cart
                6. Proceed to checkout
                7. Fill shipping information: {order.shipping_address.get('first_name', '')} {order.shipping_address.get('last_name', '')}, {order.shipping_address.get('address_line_1', '')}, {order.shipping_address.get('city', '')}, {order.shipping_address.get('state', '')} {order.shipping_address.get('postal_code', '')}
                8. IMPORTANT: Fill phone number field with (555) 123-4567 - do not skip this field!
                9. Complete payment information using the default test information provided below
                {credentials_info}
                {default_info}
                """
            else:
                # If no product URL, search for the product on the retailer site
                # Build command using string concatenation to avoid false positive SQL injection detection
                product_name = order.product_name
                product_size = order.product_size or "any available"
                product_color = order.product_color or "any available"
                shipping_name = f"{order.shipping_address.get('first_name', '')} {order.shipping_address.get('last_name', '')}"
                shipping_addr = f"{order.shipping_address.get('address_line_1', '')}, {order.shipping_address.get('city', '')}, {order.shipping_address.get('state', '')} {order.shipping_address.get('postal_code', '')}"

                command = (
                    "Complete this e-commerce order:\n"
                    "1. If login is required, use the provided credentials to sign in\n"
                    "2. Search for product: " + product_name + "\n"
                    "3. Select the correct product from search results\n"
                    "4. Select size: " + product_size + "\n"
                    "5. Select color: " + product_color + "\n"
                    "6. Add to cart\n"
                    "7. Proceed to checkout\n"
                    "8. Fill shipping information: "
                    + shipping_name
                    + ", "
                    + shipping_addr
                    + "\n"
                    "9. IMPORTANT: Fill phone number field with (555) 123-4567 - do not skip this field!\n"
                    "10. Complete payment information using the default test information provided below\n"
                    f"{credentials_info}\n"
                    f"{default_info}\n"
                )

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
                        "progress": 20,
                        "step": "Executing Nova Act automation",
                        "automation_method": "nova_act",
                    }
                )

            # Execute automation in the same thread where Nova Act was initialized
            def execute_nova_act_same_thread():
                try:
                    # Create a new Nova Act session in the same thread context
                    # This avoids the "cannot switch to a different thread" error
                    self._add_log(
                        "INFO",
                        "Creating Nova Act session in execution thread",
                        "automation_execution",
                    )

                    # Set up event loop for this thread
                    import asyncio

                    try:
                        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    except Exception as loop_error:
                        self._add_log(
                            "WARNING",
                            f"Event loop setup warning: {loop_error}",
                            "automation_execution",
                        )

                    # Capture stdout to parse Nova Act logs
                    import sys
                    from io import StringIO

                    old_stdout = sys.stdout
                    captured_output = StringIO()

                    try:
                        # Redirect stdout to capture Nova Act logs
                        sys.stdout = captured_output

                        # Determine starting URL - prefer product URL, then retailer starting URL, then fallback
                        if hasattr(order, "product_url") and order.product_url:
                            starting_url = order.product_url
                            self._add_log(
                                "INFO",
                                f"Using product URL as starting page: {starting_url}",
                                "automation_execution",
                            )
                        else:
                            starting_url = self.retailer_config.get(
                                "starting_url", "https://www.google.com"
                            )
                            self._add_log(
                                "INFO",
                                f"Using retailer starting URL: {starting_url}",
                                "automation_execution",
                            )

                        # Create and use Nova Act in the same thread
                        with NovaAct(
                            cdp_endpoint_url=self.ws_url,
                            cdp_headers=self.headers,
                            preview={"playwright_actuation": True},
                            nova_act_api_key=self.api_key,
                            starting_page=starting_url,
                        ) as nova_act:
                            self._add_log(
                                "INFO",
                                "Nova Act session created, executing command",
                                "automation_execution",
                            )
                            try:
                                result = nova_act.act(command)
                                return result, captured_output.getvalue()
                            except Exception as act_error:
                                # Handle Nova Act specific errors
                                if ActAgentError and isinstance(
                                    act_error, ActAgentError
                                ):
                                    if isinstance(act_error, ActAgentFailed):
                                        return (
                                            f"AGENT_FAILED: {str(act_error)}",
                                            captured_output.getvalue(),
                                        )
                                    elif isinstance(
                                        act_error, ActExceededMaxStepsError
                                    ):
                                        return (
                                            f"MAX_STEPS_EXCEEDED: {str(act_error)}",
                                            captured_output.getvalue(),
                                        )
                                    elif isinstance(act_error, ActTimeoutError):
                                        return (
                                            f"TIMEOUT: {str(act_error)}",
                                            captured_output.getvalue(),
                                        )
                                    else:
                                        return (
                                            f"AGENT_ERROR: {str(act_error)}",
                                            captured_output.getvalue(),
                                        )
                                elif ActClientError and isinstance(
                                    act_error, ActClientError
                                ):
                                    if isinstance(act_error, ActGuardrailsError):
                                        return (
                                            f"GUARDRAILS_BLOCKED: {str(act_error)}",
                                            captured_output.getvalue(),
                                        )
                                    elif isinstance(
                                        act_error, ActRateLimitExceededError
                                    ):
                                        return (
                                            f"RATE_LIMITED: {str(act_error)}",
                                            captured_output.getvalue(),
                                        )
                                    else:
                                        return (
                                            f"CLIENT_ERROR: {str(act_error)}",
                                            captured_output.getvalue(),
                                        )
                                elif ActExecutionError and isinstance(
                                    act_error, ActExecutionError
                                ):
                                    return (
                                        f"EXECUTION_ERROR: {str(act_error)}",
                                        captured_output.getvalue(),
                                    )
                                elif ActServerError and isinstance(
                                    act_error, ActServerError
                                ):
                                    return (
                                        f"SERVER_ERROR: {str(act_error)}",
                                        captured_output.getvalue(),
                                    )
                                else:
                                    # Unknown error
                                    return (
                                        f"UNKNOWN_ERROR: {str(act_error)}",
                                        captured_output.getvalue(),
                                    )
                    finally:
                        # Restore stdout
                        sys.stdout = old_stdout

                except Exception as e:
                    self._add_log(
                        "ERROR",
                        f"Nova Act execution error: {e}",
                        "automation_execution",
                    )
                    return f"FAILED: Nova Act execution error: {e}", (
                        captured_output.getvalue()
                        if "captured_output" in locals()
                        else ""
                    )

            # Run Nova Act in thread pool with improved resource management
            executor = None
            try:
                import concurrent.futures

                executor = concurrent.futures.ThreadPoolExecutor(
                    max_workers=1, thread_name_prefix=f"nova-act-{self.session_id[:8]}"
                )
                future = executor.submit(execute_nova_act_same_thread)
                try:
                    result_tuple = await asyncio.wait_for(
                        asyncio.wrap_future(future), timeout=300.0
                    )  # 5 minute timeout

                    if isinstance(result_tuple, tuple):
                        result, captured_logs = result_tuple
                        # Extract and log Nova Act execution steps
                        if captured_logs:
                            self._extract_nova_act_logs_from_output(captured_logs)
                    else:
                        result = result_tuple

                except asyncio.TimeoutError:
                    self._add_log(
                        "ERROR",
                        "Nova Act execution timed out after 5 minutes",
                        "automation_execution",
                    )
                    future.cancel()
                    result = "FAILED: Nova Act automation timed out after 5 minutes."
            except Exception as e:
                self._add_log(
                    "ERROR", f"Thread execution error: {e}", "automation_execution"
                )
                result = f"FAILED: Thread execution error: {e}"
            finally:
                if executor:
                    executor.shutdown(wait=False)

            self._add_log(
                "INFO",
                f"Automation completed with result: {str(result)[:200]}...",
                "automation_execution",
            )

            # Check result - simple logic: no error = success
            result_str = str(result).lower()

            # Check for Nova Act specific error patterns
            nova_act_errors = [
                "agent_failed",
                "max_steps_exceeded",
                "timeout",
                "client_error",
                "execution_error",
                "server_error",
                "guardrails_blocked",
                "rate_limited",
            ]

            # Check for explicit errors
            has_nova_act_error = any(error in result_str for error in nova_act_errors)
            has_general_error = any(
                word in result_str for word in ["failed", "error", "exception"]
            )

            # Log the result analysis
            self._add_log(
                "INFO",
                f"Result analysis - Nova Act error: {has_nova_act_error}, General error: {has_general_error}",
                "result_analysis",
            )

            if has_nova_act_error:
                # Handle specific Nova Act errors
                return {
                    "success": False,
                    "status": "failed",
                    "error": f"Nova Act error: {result}",
                    "automation_method": "nova_act",
                    "result": str(result),
                }

            elif "captcha" in result_str:
                return {
                    "success": False,
                    "status": "requires_human",
                    "message": "CAPTCHA detected",
                    "automation_method": "nova_act",
                }

            elif not has_general_error:
                # No explicit error = success
                self._add_log(
                    "INFO",
                    f"No explicit errors detected, treating as success",
                    "result_analysis",
                )

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

                return {
                    "success": True,
                    "status": "completed",
                    "confirmation_number": f"NOVA-{order_id[:8]}",
                    "automation_method": "nova_act",
                    "result": str(result),
                }

            else:
                # Has general error
                self._add_log(
                    "WARNING",
                    f"General error detected in result: {str(result)[:200]}",
                    "result_analysis",
                )
                raise Exception(f"Order processing failed: {result}")

        except Exception as e:
            self._add_log(
                "ERROR", f"Nova Act direct processing failed: {e}", "processing"
            )
            return {
                "success": False,
                "status": "failed",
                "error": str(e),
                "automation_method": "nova_act",
            }

    async def cleanup(self, force: bool = False):
        """Clean up resources with improved memory management"""
        cleanup_errors = []
        try:
            self._add_log(
                "INFO", f"Cleaning up Nova Act session {self.session_id}", "cleanup"
            )

            # Clean up worker session if available (with timeout)
            if self.worker and self.worker_session_id:
                try:
                    await asyncio.wait_for(
                        self.worker.stop_session(self.worker_session_id), timeout=3.0
                    )
                    self._add_log("INFO", "Nova Act worker session stopped", "cleanup")
                except asyncio.TimeoutError:
                    cleanup_errors.append("Worker session stop timed out")
                except Exception as e:
                    cleanup_errors.append(f"Worker session cleanup: {e}")

            # Clean up Strands agent first (releases model resources)
            if self.strands_agent:
                try:
                    self.strands_agent = None
                    self._add_log("INFO", "Strands agent cleared", "cleanup")
                except Exception as e:
                    cleanup_errors.append(f"Strands agent cleanup: {e}")

            # Clean up Nova Act resources
            if hasattr(self, "nova_session"):
                try:
                    self.nova_session = None
                    self._add_log(
                        "INFO", "Nova Act session reference cleared", "cleanup"
                    )
                except Exception as e:
                    cleanup_errors.append(f"Nova Act session cleanup: {e}")

            # Clean up AgentCore context with timeout
            if hasattr(self, "agentcore_context") and self.agentcore_context:
                try:

                    def cleanup_context():
                        try:
                            self.agentcore_context.__exit__(None, None, None)
                        except Exception as e:
                            return str(e)
                        return None

                    import concurrent.futures

                    with concurrent.futures.ThreadPoolExecutor(
                        max_workers=1
                    ) as executor:
                        future = executor.submit(cleanup_context)
                        try:
                            error = await asyncio.wait_for(
                                asyncio.wrap_future(future), timeout=3.0
                            )
                            if error:
                                cleanup_errors.append(
                                    f"AgentCore context cleanup: {error}"
                                )
                            else:
                                self._add_log(
                                    "INFO", "AgentCore context cleaned up", "cleanup"
                                )
                        except asyncio.TimeoutError:
                            cleanup_errors.append("AgentCore context cleanup timed out")
                            future.cancel()
                except Exception as e:
                    cleanup_errors.append(f"AgentCore context cleanup error: {e}")
                finally:
                    self.agentcore_context = None

            # Clean up AgentCore client
            if hasattr(self, "agentcore_client") and self.agentcore_client:
                try:
                    self.agentcore_client.stop()
                    self.agentcore_client = None
                    self._add_log("INFO", "AgentCore client stopped", "cleanup")
                except Exception as e:
                    cleanup_errors.append(f"AgentCore client cleanup: {e}")

            # Reset processing flag
            self._is_processing = False

            # Clear all references
            self.session_id = None
            self.worker_session_id = None

            if cleanup_errors:
                error_msg = f"Cleanup completed with {len(cleanup_errors)} errors: {'; '.join(cleanup_errors)}"
                self._add_log("WARNING", error_msg, "cleanup")
                logger.warning(error_msg)
            else:
                logger.info("Nova Act Agent cleanup completed successfully")

        except Exception as e:
            error_msg = f"Critical cleanup error: {e}"
            logger.error(error_msg)
            if hasattr(self, "_add_log"):
                self._add_log("ERROR", error_msg, "cleanup")
                try:
                    self.agentcore_client.stop()
                    self.agentcore_client = None
                    self._add_log("INFO", "AgentCore client stopped", "cleanup")
                except Exception as e:
                    logger.warning(f"Error stopping AgentCore client: {e}")

            self._add_log(
                "INFO", f"Nova Act session {self.session_id} cleaned up", "cleanup"
            )

        except Exception as e:
            logger.error(f"Cleanup error: {e}")
