#!/usr/bin/env python3
"""
Browser Service
Unified service for managing AgentCore browser sessions, live view, session replay, and browser tools
Handles all non-agentic browser functionality
"""

import os
import logging
import threading
import asyncio
import uuid
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

try:
    from bedrock_agentcore.tools.browser_client import (
        BrowserClient as AgentCoreBrowserClient,
    )
    from bedrock_agentcore._utils.endpoints import get_control_plane_endpoint
    import boto3
except ImportError as e:
    print(f"Warning: Required packages not installed: {e}")
    AgentCoreBrowserClient = None
    get_control_plane_endpoint = None
    boto3 = None

logger = logging.getLogger(__name__)


@dataclass
class BrowserSession:
    """Browser session data"""

    session_id: str
    order_id: str
    browser_id: str
    browser_client: Any
    recording_config: Dict[str, Any]
    status: str  # active, processing, completed, terminated
    created_at: datetime
    last_accessed: datetime
    resolution: Dict[str, int]  # width, height
    manual_control: bool = False
    page: Any = None  # Playwright page object
    current_url: str = "about:blank"

    # Additional Playwright components
    playwright: Any = None
    browser: Any = None
    context: Any = None
    ws_url: str = None
    agentcore_session_id: str = None


class BrowserService:
    """
    Unified Browser Service for managing all browser-related functionality
    - AgentCore browser session management
    - Live view URL generation
    - Session replay configuration
    - Browser resolution and control management
    """

    def __init__(self, config: Dict[str, Any] = None, db_manager=None):
        self.config = config or {}
        self.db_manager = db_manager
        self.active_sessions: Dict[str, BrowserSession] = {}
        self.active_clients: Dict[str, Any] = {}
        self.session_lock = threading.Lock()

        # No cleanup thread - cleanup will be handled manually

        logger.info("BrowserService initialized")

    def create_browser_with_recording_real(self, session_id: str) -> tuple:
        """Create a browser with recording configuration using Control Plane API."""
        try:
            if not boto3 or not get_control_plane_endpoint:
                raise ImportError("Required AWS packages not available")

            logger.info(f"Creating browser with recording for session {session_id}")

            # Create control plane client
            region = self.config.get("agentcore_region", "us-west-2")
            control_plane_url = get_control_plane_endpoint(region)
            control_client = boto3.client(
                "bedrock-agentcore-control",
                region_name=region,
                endpoint_url=control_plane_url,
            )

            # Create browser with recording
            browser_name = f"order_automation_{session_id[:8]}"
            s3_bucket = self.config.get("session_replay_s3_bucket", "sanghwa-oregon")
            s3_prefix = self.config.get(
                "session_replay_s3_prefix", f"session-replays/{session_id}/"
            )
            execution_role_arn = self.config.get("execution_role_arn")

            logger.info(f"Browser name: {browser_name}")
            logger.info(f"S3 location: s3://{s3_bucket}/{s3_prefix}")

            if execution_role_arn:
                response = control_client.create_browser(
                    name=browser_name,
                    executionRoleArn=execution_role_arn,
                    networkConfiguration={"networkMode": "PUBLIC"},
                    recording={
                        "enabled": True,
                        "s3Location": {"bucket": s3_bucket, "prefix": s3_prefix},
                    },
                    browserConfiguration={
                        "args": [
                            "--enable-features=NetworkService,NetworkServiceLogging",
                            "--disable-web-security",
                            "--no-sandbox",
                            "--disable-dev-shm-usage",
                            "--enable-automation",
                            "--ignore-certificate-errors",
                            "--ignore-ssl-errors",
                            "--ignore-certificate-errors-spki-list",
                            "--disable-extensions",
                        ]
                    },
                )
            else:
                response = control_client.create_browser(
                    name=browser_name,
                    networkConfiguration={"networkMode": "PUBLIC"},
                    browserConfiguration={
                        "args": [
                            "--enable-features=NetworkService,NetworkServiceLogging",
                            "--disable-web-security",
                            "--no-sandbox",
                            "--disable-dev-shm-usage",
                            "--enable-automation",
                            "--ignore-certificate-errors",
                            "--ignore-ssl-errors",
                            "--ignore-certificate-errors-spki-list",
                            "--disable-extensions",
                        ]
                    },
                )

            browser_id = response["browserId"]
            recording_config = response.get("recording", {})

            logger.info(f"Browser created: {browser_id}")
            return browser_id, recording_config

        except Exception as e:
            logger.error(f"Failed to create browser with recording: {e}")
            raise e

    async def initialize_browser_session_async(
        self, session_id: str, browser_id: str
    ) -> Dict[str, Any]:
        """Initialize browser session with Playwright connection."""
        try:
            from bedrock_agentcore.tools.browser_client import BrowserClient
            from playwright.async_api import async_playwright

            logger.info(f"Initializing browser session {session_id}")

            # Create BrowserClient from SDK
            browser_client = BrowserClient(
                region=self.config.get("region", "us-west-2")
            )
            browser_client.identifier = browser_id

            # Start a session
            agentcore_session_id = browser_client.start(
                identifier=browser_id,
                name=f"order_session_{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                session_timeout_seconds=self.config.get(
                    "browser_session_timeout", 3600
                ),
            )

            logger.info(f"AgentCore session started: {agentcore_session_id}")

            # Get WebSocket headers
            ws_url, headers = browser_client.generate_ws_headers()
            logger.info(f"WebSocket URL: {ws_url}")

            # Wait for browser initialization
            await asyncio.sleep(10)

            # Initialize Playwright with CDP
            playwright = await async_playwright().start()

            # Connect to the browser via CDP with HTTP/2 support
            browser = await playwright.chromium.connect_over_cdp(
                ws_url,
                headers=headers,
                # Add timeout and other options
                timeout=60000,
            )

            # Get context and page
            context = browser.contexts[0]
            page = context.pages[0]

            logger.info("Playwright connected successfully")

            return {
                "browser_client": browser_client,
                "playwright": playwright,
                "browser": browser,
                "context": context,
                "page": page,
                "ws_url": ws_url,
                "agentcore_session_id": agentcore_session_id,
            }

        except Exception as e:
            logger.error(f"Failed to initialize browser session: {e}")
            raise e

    # Note: Browser management methods removed - using default aws.browser.v1

    def create_browser_with_recording(
        self, session_id: str
    ) -> tuple[str, Dict[str, Any]]:
        """Create a browser with recording configuration using Control Plane API."""
        logger.info(
            f"Creating browser with recording configuration for session: {session_id}"
        )

        try:
            # Create control plane client
            region = self.config.get("agentcore_region", "us-west-2")
            control_plane_url = get_control_plane_endpoint(region)
            control_client = boto3.client(
                "bedrock-agentcore-control",
                region_name=region,
                endpoint_url=control_plane_url,
            )

            # Create browser with recording
            browser_name = f"browser_{uuid.uuid4().hex[:8]}"
            s3_bucket = self.config.get("session_replay_s3_bucket", "sanghwa-oregon")
            s3_prefix = self.config.get(
                "session_replay_s3_prefix", f"session-replays/{session_id}/"
            )
            execution_role_arn = self.config.get("execution_role_arn")

            logger.info(f"Browser name: {browser_name}")
            logger.info(f"S3 location: s3://{s3_bucket}/{s3_prefix}")

            if execution_role_arn:
                # Create browser with recording if role is available
                response = control_client.create_browser(
                    name=browser_name,
                    executionRoleArn=execution_role_arn,
                    networkConfiguration={"networkMode": "PUBLIC"},
                    recording={
                        "enabled": True,
                        "s3Location": {"bucket": s3_bucket, "prefix": s3_prefix},
                    },
                    # Add browser configuration for HTTP/2 support
                    browserConfiguration={
                        "args": [
                            "--enable-features=NetworkService,NetworkServiceLogging",
                            "--disable-web-security",
                            "--no-sandbox",
                            "--disable-dev-shm-usage",
                            "--enable-automation",
                            "--ignore-certificate-errors",
                            "--ignore-ssl-errors",
                            "--ignore-certificate-errors-spki-list",
                            "--disable-extensions",
                        ]
                    },
                )
                logger.info(f"Created browser with recording: {browser_name}")
            else:
                # Create browser without recording if no role is configured
                logger.warning(
                    "No execution role ARN configured, creating browser without recording"
                )
                response = control_client.create_browser(
                    name=browser_name,
                    networkConfiguration={"networkMode": "PUBLIC"},
                    # Add browser configuration for HTTP/2 support
                    browserConfiguration={
                        "args": [
                            "--enable-features=NetworkService,NetworkServiceLogging",
                            "--disable-web-security",
                            "--no-sandbox",
                            "--disable-dev-shm-usage",
                            "--enable-automation",
                            "--ignore-certificate-errors",
                            "--ignore-ssl-errors",
                            "--ignore-certificate-errors-spki-list",
                            "--disable-extensions",
                        ]
                    },
                )
                logger.info(f"Created browser without recording: {browser_name}")

            browser_id = response["browserId"]
            recording_config = response.get("recording", {})

            logger.info(f"Browser created: {browser_id}")
            logger.info(f"Recording to: s3://{s3_bucket}/{s3_prefix}")

            return browser_id, recording_config

        except Exception as e:
            logger.error(f"Failed to create browser with recording: {e}")
            raise

    def create_browser_session(
        self, session_id: str, order_id: str = None
    ) -> Dict[str, Any]:
        """Create a new browser session with AgentCore integration"""
        try:
            with self.session_lock:
                # Check if session already exists
                if session_id in self.active_sessions:
                    logger.warning(f"Session {session_id} already exists")
                    return self.get_session_info(session_id)

                # Try to create real AgentCore browser session
                try:
                    if AgentCoreBrowserClient and boto3:
                        # Create browser with recording
                        browser_id, recording_config = (
                            self.create_browser_with_recording_real(session_id)
                        )

                        # Create browser client
                        region = self.config.get("agentcore_region", "us-west-2")
                        browser_client = AgentCoreBrowserClient(region=region)
                        browser_client.identifier = browser_id

                        # Start session
                        agentcore_session_id = browser_client.start(
                            identifier=browser_id,
                            name=f"order_session_{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                            session_timeout_seconds=self.config.get(
                                "browser_session_timeout", 3600
                            ),
                        )

                        # Get WebSocket URL
                        ws_url, headers = browser_client.generate_ws_headers()

                        # Create session record
                        browser_session = BrowserSession(
                            session_id=session_id,
                            order_id=order_id or session_id,
                            browser_id=browser_id,
                            browser_client=browser_client,
                            recording_config=recording_config,
                            status="active",
                            created_at=datetime.now(timezone.utc),
                            last_accessed=datetime.now(timezone.utc),
                            resolution={"width": 1280, "height": 720},
                            page=None,
                            current_url="about:blank",
                            ws_url=ws_url,
                            agentcore_session_id=agentcore_session_id,
                        )

                        # Store session
                        self.active_sessions[session_id] = browser_session

                        logger.info(
                            f"AgentCore browser session {session_id} created successfully"
                        )

                        return {
                            "session_id": session_id,
                            "browser_id": browser_id,
                            "agentcore_session_id": agentcore_session_id,
                            "status": "active",
                            "recording_enabled": bool(recording_config),
                            "recording_location": f"s3://{recording_config.get('s3Location', {}).get('bucket', '')}/{recording_config.get('s3Location', {}).get('prefix', '')}",
                            "created_at": datetime.now().isoformat(),
                            "ws_url": ws_url,
                            "page_available": False,  # Will be set when Playwright connects
                        }

                except Exception as agentcore_error:
                    logger.warning(
                        f"AgentCore browser creation failed: {agentcore_error}"
                    )
                    # Fall back to simplified session
                    pass

                # Fallback: create simplified session record
                browser_session = BrowserSession(
                    session_id=session_id,
                    order_id=order_id or session_id,
                    browser_id=f"fallback_browser_{session_id[:8]}",
                    browser_client=None,
                    recording_config={},
                    status="active",
                    created_at=datetime.now(timezone.utc),
                    last_accessed=datetime.now(timezone.utc),
                    resolution={"width": 1280, "height": 720},
                    page=None,
                    current_url="about:blank",
                    ws_url=None,
                    agentcore_session_id=session_id,
                )

                # Store session
                self.active_sessions[session_id] = browser_session

                logger.info(f"Fallback browser session {session_id} created")

                return {
                    "session_id": session_id,
                    "browser_id": browser_session.browser_id,
                    "agentcore_session_id": session_id,
                    "status": "active",
                    "recording_enabled": False,
                    "recording_location": "",
                    "created_at": datetime.now().isoformat(),
                    "ws_url": None,
                    "page_available": False,
                }

        except Exception as e:
            logger.error(f"Failed to create browser session {session_id}: {e}")
            raise

    def get_session_info(self, session_id: str) -> Dict[str, Any]:
        """Get session information"""
        try:
            with self.session_lock:
                session = self.active_sessions.get(session_id)
                if not session:
                    return {"exists": False, "status": "not_found"}

                return {
                    "exists": True,
                    "session_id": session_id,
                    "browser_id": session.browser_id,
                    "status": session.status,
                    "created_at": session.created_at.isoformat(),
                    "last_accessed": session.last_accessed.isoformat(),
                    "resolution": session.resolution,
                    "manual_control": session.manual_control,
                    "recording_enabled": True,
                    "recording_location": f"s3://{session.recording_config.get('s3Location', {}).get('bucket', '')}/{session.recording_config.get('s3Location', {}).get('prefix', '')}",
                }

        except Exception as e:
            logger.error(f"Failed to get session info for {session_id}: {e}")
            return {"exists": False, "status": "error", "error": str(e)}

    def get_live_view_url(self, session_id: str, expires: int = 300) -> Dict[str, Any]:
        """Get live view URL for browser session"""
        try:
            with self.session_lock:
                # First check active sessions
                session = self.active_sessions.get(session_id)
                if not session:
                    # Try to find in active clients
                    browser_client = self.active_clients.get(session_id)
                    if not browser_client:
                        return {"url": None, "error": f"Session {session_id} not found"}

                    # Create a temporary session object for the client
                    session = type(
                        "TempSession",
                        (),
                        {
                            "browser_client": browser_client,
                            "manual_control": False,
                            "resolution": {"width": 1280, "height": 720},
                            "current_url": "about:blank",
                        },
                    )()

                # Update last accessed time if it's a real session
                if hasattr(session, "last_accessed"):
                    session.last_accessed = datetime.now(timezone.utc)

                # Try to get live view URL from browser client
                live_view_url = None
                browser_client = session.browser_client

                if browser_client:
                    # Method 1: Try generate_live_view_url with proper error handling
                    if hasattr(browser_client, "generate_live_view_url"):
                        try:
                            live_view_url = browser_client.generate_live_view_url(
                                expires=expires
                            )
                            logger.info(
                                f"Generated live view URL using generate_live_view_url: {session_id}"
                            )
                        except Exception as e:
                            logger.warning(f"generate_live_view_url failed: {e}")

                    # Method 2: Try get_live_view_url (alternative method name)
                    if not live_view_url and hasattr(
                        browser_client, "get_live_view_url"
                    ):
                        try:
                            live_view_url = browser_client.get_live_view_url(
                                expires=expires
                            )
                            logger.info(
                                f"Generated live view URL using get_live_view_url: {session_id}"
                            )
                        except Exception as e:
                            logger.warning(f"get_live_view_url failed: {e}")

                    # Method 3: Try to generate WebSocket headers as fallback
                    if not live_view_url and hasattr(
                        browser_client, "generate_ws_headers"
                    ):
                        try:
                            ws_url, headers = browser_client.generate_ws_headers()
                            # Convert WebSocket URL to live view URL format
                            if ws_url and ws_url.startswith("wss://"):
                                # Replace wss:// with https:// for live view
                                live_view_url = ws_url.replace(
                                    "wss://", "https://"
                                ).replace("/browser", "/live-view")
                            logger.info(
                                f"Generated live view URL from WebSocket: {session_id}"
                            )
                        except Exception as e:
                            logger.warning(f"generate_ws_headers failed: {e}")

                if live_view_url:
                    return {
                        "url": live_view_url,
                        "session_id": session_id,
                        "browser_id": getattr(
                            session, "browser_id", f"browser_{session_id[:8]}"
                        ),
                        "expires": expires,
                        "type": "dcv",
                        "manual_control": getattr(session, "manual_control", False),
                        "resolution": getattr(
                            session, "resolution", {"width": 1280, "height": 720}
                        ),
                        "current_url": getattr(session, "current_url", "about:blank"),
                    }
                else:
                    return {
                        "url": None,
                        "error": "Unable to generate live view URL - AgentCore session not active",
                        "session_id": session_id,
                    }

        except Exception as e:
            logger.error(f"Failed to get live view URL for {session_id}: {e}")
            return {"url": None, "error": str(e)}

    def change_browser_resolution(
        self, session_id: str, width: int, height: int
    ) -> Dict[str, Any]:
        """Change browser resolution"""
        try:
            with self.session_lock:
                session = self.active_sessions.get(session_id)
                if not session:
                    return {
                        "success": False,
                        "error": f"Session {session_id} not found",
                    }

                # Update resolution
                session.resolution = {"width": width, "height": height}
                session.last_accessed = datetime.now(timezone.utc)

                # Try to change resolution via browser client
                try:
                    if hasattr(session.browser_client, "set_viewport_size"):
                        session.browser_client.set_viewport_size(width, height)
                        logger.info(
                            f"Changed browser resolution to {width}x{height} for session {session_id}"
                        )
                    else:
                        logger.warning(
                            f"Browser client does not support resolution change for session {session_id}"
                        )

                    return {
                        "success": True,
                        "message": f"Browser resolution changed to {width}x{height}",
                        "width": width,
                        "height": height,
                    }

                except Exception as resize_error:
                    logger.error(
                        f"Error changing browser resolution for session {session_id}: {resize_error}"
                    )
                    return {
                        "success": False,
                        "error": f"Failed to change browser resolution: {str(resize_error)}",
                    }

        except Exception as e:
            logger.error(f"Failed to change resolution for session {session_id}: {e}")
            return {"success": False, "error": str(e)}

    def enable_manual_control(self, session_id: str) -> Dict[str, Any]:
        """Enable manual control for session"""
        try:
            with self.session_lock:
                session = self.active_sessions.get(session_id)
                if not session:
                    return {
                        "success": False,
                        "error": f"Session {session_id} not found",
                    }

                if hasattr(session.browser_client, "take_control"):
                    session.browser_client.take_control()
                    session.manual_control = True
                    logger.info(f"Manual control enabled for session {session_id}")
                    return {
                        "success": True,
                        "message": "Manual control enabled. You can now interact with the browser directly.",
                    }
                else:
                    return {
                        "success": False,
                        "error": "Manual control not supported by current browser client",
                    }

        except Exception as e:
            logger.error(
                f"Failed to enable manual control for session {session_id}: {e}"
            )
            return {"success": False, "error": str(e)}

    def disable_manual_control(self, session_id: str) -> Dict[str, Any]:
        """Disable manual control for session"""
        try:
            with self.session_lock:
                session = self.active_sessions.get(session_id)
                if not session:
                    return {
                        "success": False,
                        "error": f"Session {session_id} not found",
                    }

                if hasattr(session.browser_client, "release_control"):
                    session.browser_client.release_control()
                    session.manual_control = False
                    logger.info(f"Manual control released for session {session_id}")
                    return {
                        "success": True,
                        "message": "Manual control released. Automation restored.",
                    }
                else:
                    return {
                        "success": False,
                        "error": "Manual control release not supported by current browser client",
                    }

        except Exception as e:
            logger.error(
                f"Failed to disable manual control for session {session_id}: {e}"
            )
            return {"success": False, "error": str(e)}

    def register_session(
        self,
        session_id: str,
        browser_client: Any,
        order_id: str = None,
        metadata: Dict[str, Any] = None,
    ):
        """Register an existing browser session (for agent integration)"""
        try:
            with self.session_lock:
                self.active_clients[session_id] = browser_client

                # Update database if available
                if self.db_manager and order_id:
                    try:
                        self.db_manager.update_order_status(
                            order_id=order_id,
                            status=self.db_manager.get_order(
                                order_id
                            ).status,  # Keep current status
                            session_id=session_id,
                        )
                        logger.info(
                            f"Updated order {order_id} with session_id: {session_id}"
                        )
                    except Exception as db_error:
                        logger.warning(
                            f"Failed to update database with session info: {db_error}"
                        )

                logger.info(
                    f"Registered browser session: {session_id} (order: {order_id})"
                )
        except Exception as e:
            logger.error(f"Failed to register browser session {session_id}: {e}")

    def get_client(self, session_id: str) -> Optional[Any]:
        """Get browser client by session ID"""
        try:
            with self.session_lock:
                client = self.active_clients.get(session_id)
                if client:
                    logger.info(f"Retrieved browser client for session: {session_id}")
                    return client
                else:
                    logger.warning(
                        f"Browser session not found in active clients: {session_id}"
                    )
                    return None
        except Exception as e:
            logger.error(f"Failed to get browser client for session {session_id}: {e}")
            return None

    def get_session_by_order(self, order_id: str) -> Optional[str]:
        """Get session ID by order ID"""
        try:
            # Check database for session_id
            if self.db_manager:
                try:
                    order = self.db_manager.get_order(order_id)
                    if order and hasattr(order, "session_id") and order.session_id:
                        session_id = order.session_id
                        # Check if we have an active client for this session
                        with self.session_lock:
                            if (
                                session_id in self.active_clients
                                or session_id in self.active_sessions
                            ):
                                logger.info(
                                    f"Found session {session_id} for order: {order_id}"
                                )
                                return session_id
                            else:
                                logger.warning(
                                    f"Session {session_id} found in DB but no active client"
                                )
                                return None
                    else:
                        logger.warning(
                            f"No session_id found in database for order: {order_id}"
                        )
                        return None
                except Exception as db_error:
                    logger.error(
                        f"Database error getting session for order {order_id}: {db_error}"
                    )
                    return None
            else:
                logger.warning("No database manager available")
                return None
        except Exception as e:
            logger.error(f"Failed to get session for order {order_id}: {e}")
            return None

    def cleanup_session(self, session_id: str, force: bool = False):
        """Clean up a browser session

        Args:
            session_id: Session ID to cleanup
            force: Force cleanup even if session is protected (requires_human status)
        """
        cleanup_errors = []
        
        try:
            logger.info(f"Starting cleanup for session {session_id} (force={force})")
            
            # Check if session should be protected from cleanup
            if not force and self.db_manager:
                try:
                    order = self.db_manager.get_order(session_id)
                    if order and order.status.value == "requires_human":
                        logger.info(
                            f"Protecting session {session_id} from cleanup - requires human intervention"
                        )
                        return
                except Exception as e:
                    logger.warning(
                        f"Could not check order status for session {session_id}: {e}"
                    )

            # Use timeout for the entire cleanup operation
            try:
                with self.session_lock:
                    # Clean up session
                    if session_id in self.active_sessions:
                        session = self.active_sessions[session_id]
                        logger.debug(f"Found active session {session_id} for cleanup")

                        # Clean up Playwright resources with timeout
                        async def cleanup_playwright():
                            cleanup_tasks = []
                            
                            try:
                                if hasattr(session, "browser") and session.browser:
                                    try:
                                        await asyncio.wait_for(session.browser.close(), timeout=3.0)
                                        logger.info(f"Closed Playwright browser for session {session_id}")
                                    except asyncio.TimeoutError:
                                        logger.warning(f"Browser close timed out for session {session_id}")
                                    except Exception as e:
                                        logger.warning(f"Error closing browser: {e}")
                                        
                                if hasattr(session, "playwright") and session.playwright:
                                    try:
                                        await asyncio.wait_for(session.playwright.stop(), timeout=3.0)
                                        logger.info(f"Stopped Playwright for session {session_id}")
                                    except asyncio.TimeoutError:
                                        logger.warning(f"Playwright stop timed out for session {session_id}")
                                    except Exception as e:
                                        logger.warning(f"Error stopping playwright: {e}")
                                        
                            except Exception as e:
                                logger.warning(f"Error in Playwright cleanup: {e}")

                        # Run Playwright cleanup with timeout
                        try:
                            # Simple approach - just run the cleanup
                            asyncio.run(cleanup_playwright())
                        except Exception as e:
                            cleanup_errors.append(f"Playwright cleanup error: {str(e)}")
                            logger.warning(f"Failed to run Playwright cleanup: {e}")

                        # Clean up browser client with timeout
                        try:
                            if hasattr(session, 'browser_client') and session.browser_client:
                                if hasattr(session.browser_client, "stop"):
                                    session.browser_client.stop()
                                logger.debug(f"Stopped browser client for session {session_id}")
                            session.status = "terminated"
                        except Exception as e:
                            cleanup_errors.append(f"Browser client cleanup: {str(e)}")
                            logger.warning(f"Error stopping browser client for session {session_id}: {e}")

                        # Remove from active sessions
                        try:
                            del self.active_sessions[session_id]
                            logger.info(f"Removed session {session_id} from active_sessions")
                        except KeyError:
                            logger.debug(f"Session {session_id} was not in active_sessions")
                        except Exception as e:
                            cleanup_errors.append(f"Session removal: {str(e)}")
                            logger.warning(f"Error removing session {session_id}: {e}")

                    # Clean up client
                    try:
                        if session_id in self.active_clients:
                            del self.active_clients[session_id]
                            logger.info(f"Cleaned up browser client: {session_id}")
                    except Exception as e:
                        cleanup_errors.append(f"Client cleanup: {str(e)}")
                        logger.warning(f"Error cleaning up client {session_id}: {e}")

            except Exception as lock_error:
                cleanup_errors.append(f"Lock error: {str(lock_error)}")
                logger.error(f"Error during locked cleanup for session {session_id}: {lock_error}")

            # Log cleanup summary
            if cleanup_errors:
                logger.warning(f"Session {session_id} cleanup completed with errors: {cleanup_errors}")
            else:
                logger.info(f"Session {session_id} cleanup completed successfully")

        except Exception as e:
            logger.error(f"Critical error during cleanup of session {session_id}: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            # Don't re-raise - we want cleanup to be as robust as possible

    def list_sessions(self) -> Dict[str, Dict[str, Any]]:
        """List all active sessions"""
        try:
            result = {}

            # Get active sessions from memory
            with self.session_lock:
                for session_id, session in self.active_sessions.items():
                    result[session_id] = {
                        "order_id": session.order_id,
                        "active": True,
                        "created_at": session.created_at.isoformat(),
                        "status": session.status,
                        "browser_id": session.browser_id,
                        "resolution": session.resolution,
                        "manual_control": session.manual_control,
                    }

                # Add any active clients not in sessions
                for session_id in self.active_clients:
                    if session_id not in result:
                        result[session_id] = {
                            "order_id": None,
                            "active": True,
                            "created_at": None,
                            "status": "unknown",
                            "browser_id": None,
                            "resolution": None,
                            "manual_control": False,
                        }

            return result
        except Exception as e:
            logger.error(f"Failed to list browser sessions: {e}")
            return {}

    def cleanup_expired_sessions(self):
        """Manual cleanup of expired sessions (called when needed)"""
        try:
            now = datetime.now(timezone.utc)
            expired_sessions = []

            with self.session_lock:
                for session_id, session in self.active_sessions.items():
                    # Check if session requires human intervention
                    is_protected = False
                    if self.db_manager:
                        try:
                            order = self.db_manager.get_order(session_id)
                            if order and order.status.value == "requires_human":
                                is_protected = True
                                logger.debug(
                                    f"Session {session_id} protected - requires human intervention"
                                )
                        except Exception as e:
                            logger.debug(
                                f"Could not check order status for session {session_id}: {e}"
                            )

                    # Terminate sessions that haven't been accessed in 30 minutes (unless protected)
                    if (
                        not is_protected
                        and (now - session.last_accessed).total_seconds() > 1800
                    ):
                        expired_sessions.append(session_id)

            # Clean up expired sessions
            for session_id in expired_sessions:
                logger.info(f"Cleaning up expired browser session: {session_id}")
                self.cleanup_session(session_id)

            if expired_sessions:
                logger.info(
                    f"Cleaned up {len(expired_sessions)} expired browser sessions"
                )

        except Exception as e:
            logger.error(f"Error in browser cleanup: {e}")

    def cleanup_all_sessions(self):
        """Cleanup all active sessions during shutdown"""
        try:
            with self.session_lock:
                session_ids = list(self.active_sessions.keys())
            
            for session_id in session_ids:
                try:
                    logger.info(f"Cleaning up browser session during shutdown: {session_id}")
                    self.cleanup_session(session_id)
                except Exception as e:
                    logger.error(f"Error cleaning up session {session_id}: {e}")
            
            if session_ids:
                logger.info(f"Cleaned up {len(session_ids)} browser sessions during shutdown")
                
        except Exception as e:
            logger.error(f"Error in shutdown cleanup: {e}")

    def shutdown(self):
        """Shutdown the service and cleanup all sessions"""
        logger.info("Shutting down BrowserService")

        with self.session_lock:
            session_ids = list(self.active_sessions.keys())

        for session_id in session_ids:
            self.cleanup_session(session_id)

        logger.info("BrowserService shutdown complete")

    def take_screenshot(
        self, session_id: str, screenshot_path: str, description: str = ""
    ) -> Dict[str, Any]:
        """Take a screenshot using browser session

        Args:
            session_id: Browser session ID
            screenshot_path: Full path where to save the screenshot
            description: Optional description for annotation

        Returns:
            Dict with success status and error message if failed
        """
        try:
            with self.session_lock:
                session = self.active_sessions.get(session_id)
                if not session:
                    return {
                        "success": False,
                        "error": f"Session {session_id} not found",
                    }

                # Update last accessed time
                session.last_accessed = datetime.now(timezone.utc)

                # Ensure directory exists
                import os

                os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)

                # Try Playwright page screenshot first
                if hasattr(session, "page") and session.page:
                    try:
                        import asyncio

                        async def take_screenshot_async():
                            await session.page.screenshot(
                                path=screenshot_path, full_page=True
                            )
                            return True

                        # Handle async execution properly
                        try:
                            loop = asyncio.get_event_loop()
                            if loop.is_running():
                                # Use thread-safe execution
                                future = asyncio.run_coroutine_threadsafe(
                                    take_screenshot_async(), loop
                                )
                                result = future.result(timeout=30)
                            else:
                                result = asyncio.run(take_screenshot_async())

                            logger.info(
                                f"Playwright screenshot successful: {session_id}"
                            )
                            return {
                                "success": True,
                                "path": screenshot_path,
                                "method": "playwright_page",
                                "message": f"Screenshot saved to {screenshot_path}",
                                "description": description,
                            }
                        except Exception as async_error:
                            logger.error(
                                f"Async screenshot execution failed: {async_error}"
                            )
                            # Fall through to browser client method
                    except Exception as playwright_error:
                        logger.warning(
                            f"Playwright screenshot failed: {playwright_error}"
                        )
                        # Fall through to browser client method

                # Try browser client screenshot as fallback
                if session.browser_client and hasattr(
                    session.browser_client, "take_screenshot"
                ):
                    try:
                        session.browser_client.take_screenshot(screenshot_path)
                        logger.info(
                            f"Browser client screenshot successful: {session_id}"
                        )
                        return {
                            "success": True,
                            "path": screenshot_path,
                            "method": "browser_client",
                            "message": f"Screenshot saved to {screenshot_path}",
                            "description": description,
                        }
                    except Exception as client_error:
                        logger.error(
                            f"Browser client screenshot failed: {client_error}"
                        )

                # No screenshot method available
                return {
                    "success": False,
                    "error": "No screenshot method available - neither Playwright page nor browser client supports screenshots",
                }

        except Exception as e:
            logger.error(f"Failed to take screenshot for session {session_id}: {e}")
            return {"success": False, "error": str(e)}


# Global instance
_browser_service = None


def get_browser_service(
    config: Dict[str, Any] = None, db_manager=None
) -> BrowserService:
    """Get or create global BrowserService instance"""
    global _browser_service

    if _browser_service is None:
        _browser_service = BrowserService(config, db_manager)
    elif config and _browser_service.config != config:
        _browser_service.config.update(config)
    elif db_manager and _browser_service.db_manager is None:
        _browser_service.db_manager = db_manager

    return _browser_service
