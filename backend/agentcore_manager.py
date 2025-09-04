#!/usr/bin/env python3
"""
AgentCore Browser Session Manager
Uses AWS managed AgentCore Browser Tool (aws.browser.v1)
"""

import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

try:
    from bedrock_agentcore.tools.browser_client import browser_session
    AGENTCORE_AVAILABLE = True
except ImportError:
    print("Warning: bedrock-agentcore not installed. Please install with: pip install bedrock-agentcore")
    browser_session = None
    AGENTCORE_AVAILABLE = False

logger = logging.getLogger(__name__)


class AgentCoreBrowserManager:
    """Manager for AWS AgentCore Browser Tool (aws.browser.v1)"""
    
    def __init__(self):
        self.active_sessions: Dict[str, Any] = {}
        self.default_region = "us-west-2"
        self.default_browser_arn = "arn:aws:bedrock-agentcore:us-west-2:aws:browser/aws.browser.v1"
        self.default_browser_id = "aws.browser.v1"
    
    async def get_browsers(self, region: str = None) -> List[Dict[str, Any]]:
        """Get available AgentCore Browsers (returns AWS managed browser)"""
        try:
            region = region or self.default_region
            
            # Return AWS managed browser
            browsers = [
                {
                    "browser_id": self.default_browser_id,
                    "name": "AgentCore Browser Tool",
                    "description": "AWS built-in browser sandbox for secure web browsing",
                    "status": "READY",
                    "network_mode": "PUBLIC",
                    "recording_enabled": False,  # AWS managed
                    "arn": self.default_browser_arn,
                    "region": region,
                    "managed_by": "AWS",
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
            ]
            
            logger.info(f"Retrieved {len(browsers)} browsers from region {region}")
            return browsers
            
        except Exception as e:
            logger.error(f"Failed to get browsers: {e}")
            raise
    
    async def create_browser(self, **kwargs) -> Dict[str, Any]:
        """AWS managed browser cannot be created - return existing one"""
        logger.info("AWS AgentCore Browser Tool is managed by AWS and cannot be created")
        browsers = await self.get_browsers(kwargs.get('region'))
        return browsers[0] if browsers else {}
    
    async def get_browser(self, browser_id: str, region: str = None) -> Optional[Dict[str, Any]]:
        """Get AWS managed browser details"""
        try:
            if browser_id == self.default_browser_id:
                browsers = await self.get_browsers(region)
                return browsers[0] if browsers else None
            return None
            
        except Exception as e:
            logger.error(f"Failed to get browser {browser_id}: {e}")
            raise
    
    async def delete_browser(self, browser_id: str, region: str = None) -> bool:
        """AWS managed browser cannot be deleted"""
        logger.warning("AWS AgentCore Browser Tool is managed by AWS and cannot be deleted")
        return False
    
    async def get_browser_sessions(self, browser_id: str, region: str = None) -> List[Dict[str, Any]]:
        """Get active sessions (from local tracking)"""
        try:
            # Return sessions from local tracking
            sessions = []
            for session_id, session_info in self.active_sessions.items():
                if session_info.get('browser_id') == browser_id:
                    sessions.append({
                        "session_id": session_id,
                        "browser_id": browser_id,
                        "status": session_info.get("status", "ACTIVE"),
                        "created_at": session_info.get("created_at"),
                        "region": region or self.default_region
                    })
            
            logger.info(f"Retrieved {len(sessions)} sessions for browser {browser_id}")
            return sessions
            
        except Exception as e:
            logger.error(f"Failed to get browser sessions for {browser_id}: {e}")
            raise
    
    async def spawn_agent_session(
        self, 
        browser_id: str = None,
        agent_name: str = None,
        region: str = None
    ) -> Dict[str, Any]:
        """Spawn a new agent session using bedrock-agentcore"""
        try:
            if not AGENTCORE_AVAILABLE:
                raise Exception("bedrock-agentcore not available. Please install with: pip install bedrock-agentcore")
            
            region = region or self.default_region
            browser_id = browser_id or self.default_browser_id
            agent_name = agent_name or f"agent-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # Create browser session using bedrock-agentcore
            client = browser_session(region)
            client.__enter__()
            
            # Get WebSocket URL and headers
            ws_url, headers = client.generate_ws_headers()
            
            session_id = f"session-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            session_info = {
                "session_id": session_id,
                "browser_id": browser_id,
                "agent_name": agent_name,
                "status": "ACTIVE",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "ws_url": ws_url,
                "headers": headers,
                "client": client,
                "region": region
            }
            
            # Store session for tracking
            self.active_sessions[session_id] = session_info
            
            logger.info(f"Spawned agent session {session_id} for agent {agent_name}")
            
            return {
                "session_id": session_id,
                "browser_id": browser_id,
                "agent_name": agent_name,
                "status": "ACTIVE",
                "created_at": session_info["created_at"],
                "ws_url": ws_url,
                "headers": headers,
                "region": region
            }
            
        except Exception as e:
            logger.error(f"Failed to spawn agent session: {e}")
            raise
    
    async def create_session(self, browser_id: str, region: str = None) -> Dict[str, Any]:
        """Create session (compatibility method)"""
        return await self.spawn_agent_session(browser_id, region=region)
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete/cleanup a session"""
        try:
            session_info = self.active_sessions.get(session_id)
            if not session_info:
                logger.warning(f"Session {session_id} not found")
                return False
            
            # Clean up AgentCore client
            client = session_info.get("client")
            if client and hasattr(client, '__exit__'):
                try:
                    client.__exit__(None, None, None)
                    logger.info(f"Cleaned up AgentCore client for session {session_id}")
                except Exception as e:
                    logger.warning(f"Error cleaning up AgentCore client: {e}")
            
            # Remove from tracking
            del self.active_sessions[session_id]
            
            logger.info(f"Deleted session: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            raise
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session details"""
        try:
            session_info = self.active_sessions.get(session_id)
            if not session_info:
                return None
            
            return {
                "session_id": session_id,
                "browser_id": session_info.get("browser_id"),
                "agent_name": session_info.get("agent_name"),
                "status": session_info.get("status"),
                "created_at": session_info.get("created_at"),
                "ws_url": session_info.get("ws_url"),
                "region": session_info.get("region")
            }
            
        except Exception as e:
            logger.error(f"Failed to get session {session_id}: {e}")
            raise
    
    async def get_session_connection_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get WebSocket connection info for session"""
        try:
            session_info = self.active_sessions.get(session_id)
            if not session_info:
                return None
            
            return {
                "session_id": session_id,
                "ws_url": session_info.get("ws_url"),
                "headers": session_info.get("headers", {})
            }
            
        except Exception as e:
            logger.error(f"Failed to get connection info for session {session_id}: {e}")
            raise
    
    async def cleanup_all_sessions(self):
        """Clean up all active sessions"""
        try:
            session_ids = list(self.active_sessions.keys())
            for session_id in session_ids:
                await self.delete_session(session_id)
            
            logger.info("Cleaned up all browser sessions")
            
        except Exception as e:
            logger.error(f"Failed to cleanup all sessions: {e}")


# Global instance
agentcore_manager = AgentCoreBrowserManager()