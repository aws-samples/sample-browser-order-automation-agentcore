#!/usr/bin/env python3
"""
Strands + Playwright MCP Agent
Core automation agent using Strands AI with Playwright MCP tools
"""

import os
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any

try:
    from mcp import stdio_client, StdioServerParameters
    from strands import Agent
    from strands.models import BedrockModel
    from strands.tools.mcp import MCPClient
except ImportError as e:
    print(f"Warning: Required packages not installed: {e}")
    MCPClient = None
    Agent = None
    BedrockModel = None

logger = logging.getLogger(__name__)


class LoggingMCPClient:
    """MCP Client wrapper that logs all tool executions"""

    def __init__(self, mcp_client, log_callback):
        self.mcp_client = mcp_client
        self.log_callback = log_callback

    def __enter__(self):
        self.mcp_client.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self.mcp_client.__exit__(exc_type, exc_val, exc_tb)

    def list_tools_sync(self):
        tools = self.mcp_client.list_tools_sync()
        self.log_callback("INFO", f"MCP tools listed: {len(tools)} tools available", "mcp_tools")
        return tools

    def call_tool_sync(self, tool_name, arguments):
        """Log tool calls and results"""
        self.log_callback("INFO", f"Executing MCP tool: {tool_name} with args: {str(arguments)[:200]}", "mcp_tool_call")
        
        try:
            result = self.mcp_client.call_tool_sync(tool_name, arguments)
            
            # Log tool result
            if hasattr(result, "content") and result.content:
                content_summary = str(result.content)[:300]
                self.log_callback("INFO", f"Tool {tool_name} completed: {content_summary}...", "mcp_tool_result")
            else:
                self.log_callback("INFO", f"Tool {tool_name} completed successfully", "mcp_tool_result")
            
            return result
            
        except Exception as e:
            self.log_callback("ERROR", f"Tool {tool_name} failed: {str(e)}", "mcp_tool_error")
            raise


class StrandsPlaywrightMCPAgent:
    """Strands + Playwright MCP Agent"""

    def __init__(
        self, config: Dict[str, Any], retailer_config: Dict[str, Any], db_manager=None
    ):
        self.config = config
        self.retailer_config = retailer_config
        self.db_manager = db_manager
        self.session_id = None
        self.strands_agent = None
        self.mcp_client = None

        if not MCPClient or not Agent or not BedrockModel:
            raise ImportError("Required packages not available")

    def _add_log(self, level: str, message: str, step: str = None):
        """Add execution log entry"""
        print(f"[{level}] {message}")

        if self.db_manager and self.session_id:
            try:
                self.db_manager.add_execution_log(self.session_id, level, message, step)
            except Exception as e:
                logger.error(f"Failed to add execution log: {e}")
        logger.info(f"[{level}] {message}")

    def _extract_response_text(self, response) -> str:
        """Extract text from response"""
        try:
            if hasattr(response, "message") and response.message:
                if isinstance(response.message, dict) and "content" in response.message:
                    content = response.message["content"]
                    if isinstance(content, list) and len(content) > 0:
                        return content[0].get("text", str(content[0]))
                    else:
                        return str(content)
                else:
                    return str(response.message)
            else:
                return str(response)
        except Exception:
            return str(response)

    async def start_session(self, session_id: str) -> Dict[str, Any]:
        """Start Strands + Playwright MCP session"""
        try:
            self.session_id = session_id
            self._add_log("INFO", f"Starting Strands + Playwright MCP session: {session_id}", "initialization")

            # Initialize MCP client
            playwright_mcp_dir = os.path.join(os.path.dirname(__file__), "..", "..", "playwright-mcp")
            mcp_args = [
                playwright_mcp_dir,
                "--headless",
                "--viewport-size", "1280,720",
                "--ignore-https-errors",
            ]

            self._add_log("INFO", "Initializing MCP client", "mcp_setup")

            try:
                # Create base MCP client
                base_mcp_client = MCPClient(
                    lambda: stdio_client(StdioServerParameters(command="npx", args=mcp_args))
                )
                
                # Wrap with logging client
                self.mcp_client = LoggingMCPClient(base_mcp_client, self._add_log)

                # Test MCP connection
                async def test_mcp_connection():
                    with self.mcp_client:
                        tools = self.mcp_client.list_tools_sync()
                        self._add_log("INFO", f"MCP tools available: {len(tools)}", "mcp_setup")
                        
                        # Tools are available and ready for use
                        
                        return tools

                tools = await asyncio.wait_for(test_mcp_connection(), timeout=30.0)

            except asyncio.TimeoutError:
                self._add_log("WARNING", "MCP initialization timed out", "mcp_setup")
                self.mcp_client = None
                tools = []
            except Exception as e:
                self._add_log("WARNING", f"MCP initialization failed: {e}", "mcp_setup")
                self.mcp_client = None
                tools = []

            # Create Strands agent
            bedrock_model = BedrockModel(
                model_id=self.config.get("model", "us.anthropic.claude-3-7-sonnet-20250219-v1:0"),
                cache_prompt="default",
                cache_tools="default",
            )

            if tools:
                self.strands_agent = Agent(
                    model=bedrock_model,
                    tools=tools,
                    system_prompt="""You are an expert e-commerce automation assistant with Playwright MCP tools.
                    
                    Use your browser automation tools to:
                    - Navigate to websites and handle dynamic content
                    - Take screenshots to analyze page layouts
                    - Click elements, fill forms, and interact with UI components
                    - Handle JavaScript applications and SPAs
                    
                    For e-commerce automation:
                    1. Navigate to the product URL
                    2. Take screenshots to document progress
                    3. Select product options (size, color, etc.)
                    4. Add items to cart
                    5. Navigate through checkout
                    6. Fill shipping information
                    7. Stop before payment processing
                    
                    Always provide detailed feedback about each step.""",
                )
                self._add_log("INFO", f"Strands agent created with {len(tools)} tools", "agent_setup")
            else:
                self.strands_agent = Agent(
                    model=bedrock_model,
                    system_prompt="You are an e-commerce automation assistant. Provide guidance for automation processes.",
                )
                self._add_log("INFO", "Created Strands agent without tools", "agent_setup")

            self._add_log("INFO", f"Session {session_id} started successfully", "initialization")

            return {
                "session_id": session_id,
                "status": "active",
                "automation_method": "strands_playwright_mcp",
                "created_at": datetime.now().isoformat(),
            }

        except Exception as e:
            error_msg = f"Failed to start session: {e}"
            self._add_log("ERROR", error_msg, "initialization")
            logger.error(error_msg)
            raise

    async def process_order(self, order, progress_callback=None) -> Dict[str, Any]:
        """Process order using Strands + Playwright MCP"""
        if not self.strands_agent:
            raise RuntimeError("Session not started")

        try:
            order_id = order.id
            self._add_log("INFO", f"Starting order processing for {order.product_name}", "order_processing")

            # Create automation prompt
            prompt = f"""
            Task: Navigate and interact with the following e-commerce page to test the ordering flow:
            
            Product Details:
            - URL: {order.product_url}
            - Product: {order.product_name}
            - Size: {order.product_size or 'any available'}
            - Color: {order.product_color or 'any available'}
            
            Shipping Information:
            - Name: {order.shipping_address.get('first_name', '')} {order.shipping_address.get('last_name', '')}
            - Address: {order.shipping_address.get('address_line_1', '')}, {order.shipping_address.get('city', '')}, {order.shipping_address.get('state', '')} {order.shipping_address.get('postal_code', '')}
            
            Steps:
            1. Navigate to the product URL and take a screenshot
            2. Locate the product and select options
            3. Add to cart
            4. Navigate to checkout
            5. Fill shipping information
            6. Stop before payment processing
            
            Report status as SUCCESS, FAILED, or BLOCKED.
            """

            if progress_callback:
                await progress_callback({
                    "order_id": order_id,
                    "status": "processing",
                    "progress": 20,
                    "step": "Executing automation",
                    "automation_method": "strands_playwright_mcp",
                })

            # Execute automation with detailed logging
            self._add_log("INFO", "Starting Strands agent execution", "automation_execution")

            def execute_agent():
                try:
                    # Log the prompt being sent to agent
                    self._add_log("INFO", f"Sending prompt to Strands agent (length: {len(prompt)} chars)", "agent_prompt")
                    
                    # Execute agent
                    if self.mcp_client:
                        with self.mcp_client:
                            response = self.strands_agent(prompt)
                    else:
                        response = self.strands_agent(prompt)
                    
                    # Extract and log the response
                    result_text = self._extract_response_text(response)
                    
                    # Log the response
                    self._add_log("INFO", f"Agent response received (length: {len(result_text)} chars)", "agent_response")
                    
                    # Log response in chunks if it's very long
                    if len(result_text) > 1000:
                        self._add_log("INFO", f"Agent response (first 500 chars): {result_text[:500]}...", "agent_response_detail")
                        self._add_log("INFO", f"Agent response (last 500 chars): ...{result_text[-500:]}", "agent_response_detail")
                    else:
                        self._add_log("INFO", f"Agent response: {result_text}", "agent_response_detail")
                    
                    return result_text
                    
                except Exception as e:
                    error_msg = f"FAILED: Agent execution error: {e}"
                    self._add_log("ERROR", error_msg, "agent_execution_error")
                    return error_msg

            # Execute with timeout
            import concurrent.futures
            loop = asyncio.get_event_loop()
            
            self._add_log("INFO", "Executing agent in thread pool with 5-minute timeout", "execution_start")
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                try:
                    future = loop.run_in_executor(executor, execute_agent)
                    result_text = await asyncio.wait_for(future, timeout=300.0)
                    self._add_log("INFO", "Agent execution completed within timeout", "execution_complete")
                except asyncio.TimeoutError:
                    result_text = "FAILED: Automation timed out after 5 minutes"
                    self._add_log("ERROR", "Agent execution timed out after 5 minutes", "execution_timeout")

            # Analyze result with detailed logging
            result_lower = result_text.lower()
            
            self._add_log("INFO", "Analyzing automation result", "result_analysis")
            
            if "success" in result_lower and "failed" not in result_lower:
                success = True
                status = "completed"
                self._add_log("INFO", "Result analysis: SUCCESS detected in response", "result_analysis")
            elif "blocked" in result_lower or "captcha" in result_lower:
                success = False
                status = "blocked"
                self._add_log("WARNING", "Result analysis: BLOCKED/CAPTCHA detected in response", "result_analysis")
            else:
                success = False
                status = "failed"
                self._add_log("WARNING", "Result analysis: FAILED - no success indicators found", "result_analysis")

            self._add_log("INFO", f"Final order processing result: {status.upper()}", "completion")
            
            # Log key metrics
            if "tool" in result_text.lower():
                tool_count = result_text.lower().count("tool #")
                if tool_count > 0:
                    self._add_log("INFO", f"Agent executed {tool_count} tools during automation", "execution_metrics")

            if progress_callback:
                await progress_callback({
                    "order_id": order_id,
                    "status": status,
                    "progress": 100,
                    "step": f"Automation {status}",
                    "automation_method": "strands_playwright_mcp",
                })

            # Log final result summary
            result_summary = {
                "success": success,
                "status": status,
                "confirmation_number": f"MCP-{order_id[:8]}" if success else None,
                "automation_method": "strands_playwright_mcp",
                "result_length": len(result_text),
            }
            
            self._add_log("INFO", f"Returning result: {result_summary}", "result_return")

            return {
                "success": success,
                "status": status,
                "confirmation_number": f"MCP-{order_id[:8]}" if success else None,
                "automation_method": "strands_playwright_mcp",
                "result": result_text,
            }

        except Exception as e:
            error_msg = f"Order processing failed: {e}"
            self._add_log("ERROR", error_msg, "automation_failure")
            return {
                "success": False,
                "status": "failed",
                "error": str(e),
                "automation_method": "strands_playwright_mcp",
            }

    async def cleanup(self):
        """Clean up resources"""
        try:
            self._add_log("INFO", "Starting cleanup", "cleanup")

            # Clean up Strands agent
            if hasattr(self, 'strands_agent') and self.strands_agent:
                self.strands_agent = None
                self._add_log("INFO", "Strands agent cleaned up", "cleanup")

            # Clean up MCP client
            if hasattr(self, 'mcp_client') and self.mcp_client:
                self.mcp_client = None
                self._add_log("INFO", "MCP client cleaned up", "cleanup")

            self._add_log("INFO", f"Session {self.session_id} cleaned up successfully", "cleanup")

        except Exception as e:
            logger.error(f"Cleanup error: {e}")
            self._add_log("ERROR", f"Cleanup error: {e}", "cleanup")

    def get_presigned_url(self) -> Dict[str, Any]:
        """Get presigned URL for live view - delegated to LiveViewService"""
        try:
            from ..services.live_view_service import get_live_view_service
            
            live_view_service = get_live_view_service(self.config, self.db_manager)
            
            if self.db_manager and self.session_id:
                order = self.db_manager.get_order(self.session_id)
                if order:
                    live_session_id = live_view_service.get_session_for_order(order.id)
                    if not live_session_id:
                        live_session_id = live_view_service.create_live_session(
                            order.id, "strands_playwright_mcp"
                        )
                    
                    if live_session_id:
                        presigned_url = live_view_service.get_presigned_url(live_session_id, expires=300)
                        if presigned_url:
                            return {
                                "url": presigned_url,
                                "session_id": live_session_id,
                                "auth_token": live_session_id,
                                "expires": 300
                            }
            
            return {
                "url": None,
                "session_id": self.session_id,
                "auth_token": None,
                "expires": 0,
                "error": "Could not create live view session"
            }
            
        except Exception as e:
            return {
                "url": None,
                "session_id": self.session_id,
                "auth_token": None,
                "expires": 0,
                "error": str(e)
            }
