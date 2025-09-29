"""Browser session manager for AgentCore browser automation."""

from bedrock_agentcore.tools.browser_client import BrowserClient as AgentCoreBrowserClient
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
import asyncio
import logging
import os
import time
from typing import Dict, Optional, Any
import nest_asyncio

logger = logging.getLogger(__name__)


class BrowserSession:
    """Represents a browser session with context and pages."""
    
    def __init__(self, session_id: str, browser: Browser, context: BrowserContext, page: Page, agentcore_client=None):
        self.session_id = session_id
        self.browser = browser
        self.context = context
        self.pages = {"main": page}
        self.active_page_id = "main"
        self.agentcore_client = agentcore_client  # Store AgentCore client for session management
        
    def get_active_page(self) -> Optional[Page]:
        """Get the currently active page."""
        return self.pages.get(self.active_page_id)
    
    def add_page(self, page_id: str, page: Page):
        """Add a new page to the session."""
        self.pages[page_id] = page
        self.active_page_id = page_id
    
    def switch_page(self, page_id: str) -> bool:
        """Switch to a different page."""
        if page_id in self.pages:
            self.active_page_id = page_id
            return True
        return False
    
    def remove_page(self, page_id: str):
        """Remove a page from the session."""
        if page_id in self.pages:
            del self.pages[page_id]
            if self.active_page_id == page_id and self.pages:
                self.active_page_id = next(iter(self.pages.keys()))
    
    async def close(self):
        """Close the browser session."""
        try:
            # Close pages first
            for page in self.pages.values():
                try:
                    await page.close()
                except Exception as e:
                    logger.warning(f"Error closing page: {e}")
            
            # Close context and browser
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
                
            # Stop AgentCore client and delete browser instance
            if self.agentcore_client:
                try:
                    # Stop the session
                    self.agentcore_client.stop()
                    logger.info(f"Stopped AgentCore client for session {self.session_id}")
                    
                    # Delete the browser instance
                    try:
                        from bedrock_agentcore._utils.endpoints import get_control_plane_endpoint
                        import boto3
                        
                        control_plane_url = get_control_plane_endpoint(self.agentcore_client.region)
                        control_client = boto3.client(
                            "bedrock-agentcore-control",
                            region_name=self.agentcore_client.region,
                            endpoint_url=control_plane_url
                        )
                        
                        if hasattr(self.agentcore_client, 'identifier'):
                            control_client.delete_browser(browserId=self.agentcore_client.identifier)
                            logger.info(f"Deleted AgentCore browser instance: {self.agentcore_client.identifier}")
                    except Exception as e:
                        logger.warning(f"Error deleting browser instance: {e}")
                        
                except Exception as e:
                    logger.warning(f"Error stopping AgentCore client: {e}")
                    
        except Exception as e:
            logger.error(f"Error closing session {self.session_id}: {e}")


class BrowserManager:
    """Manages browser sessions using AgentCore remote browser."""
    
    def __init__(self, region: str = "us-east-1"):
        self.sessions: Dict[str, BrowserSession] = {}
        self.playwright = None
        self._loop = None
        self._nest_asyncio_applied = False
        self.region = region
    
    def _ensure_event_loop(self):
        """Ensure we have an event loop and nest_asyncio is applied."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                raise RuntimeError("Event loop is closed")
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Only apply nest_asyncio if not using uvloop
        if not self._nest_asyncio_applied:
            try:
                current_loop = asyncio.get_running_loop()
                loop_type = str(type(current_loop))
                if 'uvloop' not in loop_type:
                    nest_asyncio.apply()
                    self._nest_asyncio_applied = True
                else:
                    logger.info("Detected uvloop, skipping nest_asyncio.apply()")
            except RuntimeError:
                # No running loop, safe to apply
                try:
                    nest_asyncio.apply()
                    self._nest_asyncio_applied = True
                except ValueError as e:
                    if "Can't patch loop" in str(e):
                        logger.warning(f"Skipping nest_asyncio due to loop patching issue: {e}")
                    else:
                        raise
        
        self._loop = loop
    

    
    async def _async_initialize(self):
        """Initialize Playwright for AgentCore browser connections."""
        if self.playwright is None:
            self.playwright = await async_playwright().start()
            logger.info("Browser manager initialized with AgentCore support")
    
    async def _async_create_session(self, session_id: str = None) -> str:
        """Create a new AgentCore browser session."""
        if self.playwright is None:
            await self._async_initialize()
        
        if session_id is None:
            session_id = f"session_{int(time.time())}"
        
        if session_id in self.sessions:
            raise ValueError(f"Session {session_id} already exists")
        
        # First create the browser instance (like Nova Act does)
        try:
            from bedrock_agentcore._utils.endpoints import get_control_plane_endpoint
            import boto3
            
            # Create control plane client
            control_plane_url = get_control_plane_endpoint(self.region)
            control_client = boto3.client(
                "bedrock-agentcore-control",
                region_name=self.region,
                endpoint_url=control_plane_url
            )

            # Create browser instance first
            # Clean session_id to match pattern [a-zA-Z][a-zA-Z0-9_]{0,47}
            clean_session_id = session_id.replace('-', '_')[:40]  # Limit length and replace hyphens
            browser_name = f"browser_tools_{clean_session_id}"
            response = control_client.create_browser(
                name=browser_name,
                networkConfiguration={"networkMode": "PUBLIC"}
            )

            browser_id = response["browserId"]
            logger.info(f"Created AgentCore browser instance: {browser_id}")

            # Now create browser client and start session
            agentcore_client = AgentCoreBrowserClient(region=self.region)
            agentcore_client.identifier = browser_id
            
            agentcore_session_id = agentcore_client.start(
                identifier=browser_id,
                name=f"session_{session_id}",
                session_timeout_seconds=3600
            )
            
            # Get CDP connection details
            cdp_url, cdp_headers = agentcore_client.generate_ws_headers()
            
            # Connect to AgentCore browser over CDP
            browser = await self.playwright.chromium.connect_over_cdp(
                endpoint_url=cdp_url, 
                headers=cdp_headers
            )
            
            # Get the default context and create a new page
            contexts = browser.contexts
            if contexts:
                context = contexts[0]
            else:
                context = await browser.new_context()
            
            page = await context.new_page()
            
            session = BrowserSession(session_id, browser, context, page, agentcore_client)
            self.sessions[session_id] = session
            
            logger.info(f"Created AgentCore browser session: {session_id} (AgentCore session: {agentcore_session_id})")
            return session_id
            
        except Exception as e:
            logger.error(f"Failed to create AgentCore browser session: {e}")
            raise
    

    
    def get_session(self, session_id: str) -> Optional[BrowserSession]:
        """Get a browser session by ID."""
        return self.sessions.get(session_id)
    
    def list_sessions(self) -> Dict[str, Dict[str, Any]]:
        """List all active sessions."""
        return {
            session_id: {
                "session_id": session_id,
                "pages": list(session.pages.keys()),
                "active_page": session.active_page_id
            }
            for session_id, session in self.sessions.items()
        }
    
    async def _async_close_session(self, session_id: str):
        """Close a browser session."""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            await session.close()
            del self.sessions[session_id]
            logger.info(f"Closed browser session: {session_id}")
    

    
    async def _async_cleanup(self):
        """Clean up all sessions and playwright."""
        for session_id in list(self.sessions.keys()):
            await self._async_close_session(session_id)
        
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None
        
        logger.info("Browser manager cleaned up")
    



