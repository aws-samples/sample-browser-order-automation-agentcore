#!/usr/bin/env python3
"""
AgentCore Service - Handles AgentCore browser session management
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

try:
    from bedrock_agentcore.tools.browser_client import browser_session
except ImportError:
    browser_session = None

logger = logging.getLogger(__name__)


class AgentCoreService:
    """Service for managing AgentCore browser sessions"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.region = config.get("agentcore_region", "us-west-2")
        self.session = None
        self.client = None

    def start_session(self) -> bool:
        """Start AgentCore browser session"""
        try:
            if not browser_session:
                logger.error("AgentCore browser_session not available")
                return False

            logger.info(f"Starting AgentCore session in region: {self.region}")
            
            self.session = browser_session(self.region)
            self.client = self.session.__enter__()
            
            if not self.client:
                raise Exception("AgentCore client is None after initialization")
            
            logger.info("AgentCore session started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start AgentCore session: {e}")
            self.cleanup()
            return False

    def get_cdp_endpoint(self) -> tuple[Optional[str], Optional[Dict[str, str]]]:
        """Get CDP WebSocket endpoint and headers"""
        try:
            if not self.client:
                return None, None
                
            ws_url, headers = self.client.generate_ws_headers()
            return ws_url, headers
            
        except Exception as e:
            logger.error(f"Failed to get CDP endpoint: {e}")
            return None, None

    def capture_screenshot(self) -> Optional[bytes]:
        """Capture screenshot from browser"""
        try:
            if not self.client:
                return None
                
            return self.client.capture_screenshot()
            
        except Exception as e:
            logger.error(f"Failed to capture screenshot: {e}")
            return None

    def get_presigned_url(self, expires: int = 300) -> Optional[str]:
        """Get presigned URL for live viewing"""
        try:
            if not self.client:
                return None
                
            # Try different methods to get presigned URL
            if hasattr(self.client, "get_presigned_url"):
                return self.client.get_presigned_url(expires=expires)
            elif hasattr(self.client, "generate_presigned_url"):
                return self.client.generate_presigned_url(expires=expires)
            elif hasattr(self.client, "get_dcv_presigned_url"):
                return self.client.get_dcv_presigned_url(expires=expires)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get presigned URL: {e}")
            return None

    def cleanup(self):
        """Cleanup AgentCore session"""
        try:
            if self.session:
                self.session.__exit__(None, None, None)
                logger.info("AgentCore session cleaned up")
        except Exception as e:
            logger.warning(f"AgentCore cleanup error: {e}")
        finally:
            self.session = None
            self.client = None

    def is_active(self) -> bool:
        """Check if session is active"""
        return self.client is not None