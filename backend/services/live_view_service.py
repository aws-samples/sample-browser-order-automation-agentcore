#!/usr/bin/env python3
"""
Live View Service - Separate component for managing AgentCore browser sessions
and providing live view functionality independent of agent automation logic.
"""

import os
import logging
import threading
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from dataclasses import dataclass

try:
    from bedrock_agentcore.tools.browser_client import browser_session
except ImportError:
    browser_session = None

logger = logging.getLogger(__name__)


@dataclass
class LiveViewSession:
    """Live view session data"""
    session_id: str
    order_id: str
    automation_method: str
    agentcore_client: Any
    agentcore_session: Any
    status: str  # active, terminated, error
    created_at: datetime
    last_accessed: datetime
    error_message: Optional[str] = None


class LiveViewService:
    """
    Service for managing live browser view sessions separate from agent automation.
    Handles AgentCore session lifecycle and provides presigned URLs for live viewing.
    """

    def __init__(self, config: Dict[str, Any], db_manager=None):
        self.config = config
        self.db_manager = db_manager
        self.active_sessions: Dict[str, LiveViewSession] = {}
        self.session_lock = threading.Lock()
        
        # Start cleanup thread
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()
        
        logger.info("LiveViewService initialized")

    def create_live_session(self, order_id: str, automation_method: str) -> Optional[str]:
        """
        Create a new live view session for an order.
        Returns session_id if successful, None if failed.
        """
        try:
            # Check if session already exists for this order
            with self.session_lock:
                existing_session = self._find_session_by_order(order_id)
                if existing_session and existing_session.status == "active":
                    logger.info(f"Reusing existing live session for order {order_id}: {existing_session.session_id}")
                    existing_session.last_accessed = datetime.now(timezone.utc)
                    return existing_session.session_id

            # Create new AgentCore session
            session_id = f"live_{order_id}_{int(datetime.now().timestamp())}"
            
            logger.info(f"Creating new live view session {session_id} for order {order_id}")
            
            # Initialize AgentCore browser session
            region = self.config.get("agentcore_region", "us-west-2")
            
            try:
                agentcore_session = browser_session(region)
                agentcore_client = agentcore_session.__enter__()
                
                if not agentcore_client:
                    raise Exception("AgentCore client is None after initialization")
                
                # Create live session record
                live_session = LiveViewSession(
                    session_id=session_id,
                    order_id=order_id,
                    automation_method=automation_method,
                    agentcore_client=agentcore_client,
                    agentcore_session=agentcore_session,
                    status="active",
                    created_at=datetime.now(timezone.utc),
                    last_accessed=datetime.now(timezone.utc)
                )
                
                with self.session_lock:
                    self.active_sessions[session_id] = live_session
                
                # Update database with session info
                if self.db_manager:
                    try:
                        # Get current order to preserve status
                        order = self.db_manager.get_order(order_id)
                        if order:
                            self.db_manager.update_order_status(
                                order_id=order_id,
                                status=order.status,  # Keep current status
                                session_id=session_id
                            )
                    except Exception as db_error:
                        logger.warning(f"Failed to update order with session_id: {db_error}")
                
                logger.info(f"Successfully created live view session {session_id}")
                return session_id
                
            except Exception as agentcore_error:
                logger.error(f"Failed to initialize AgentCore session: {agentcore_error}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to create live session for order {order_id}: {e}")
            return None

    def get_presigned_url(self, session_id: str, expires: int = 300) -> Optional[str]:
        """
        Get presigned URL for live view session.
        """
        try:
            with self.session_lock:
                live_session = self.active_sessions.get(session_id)
                
                if not live_session:
                    logger.warning(f"Live session {session_id} not found")
                    return None
                
                if live_session.status != "active":
                    logger.warning(f"Live session {session_id} is not active (status: {live_session.status})")
                    return None
                
                # Update last accessed time
                live_session.last_accessed = datetime.now(timezone.utc)
            
            # Generate presigned URL using AgentCore client
            try:
                # Based on the sample code, use generate_live_view_url method
                if hasattr(live_session.agentcore_client, "generate_live_view_url"):
                    presigned_url = live_session.agentcore_client.generate_live_view_url(expires=expires)
                    logger.info(f"Generated live view URL for session {session_id} (expires in {expires}s)")
                    return presigned_url
                else:
                    # List available methods for debugging
                    available_methods = [method for method in dir(live_session.agentcore_client) 
                                       if not method.startswith('_') and ('url' in method.lower() or 'view' in method.lower())]
                    logger.error(f"generate_live_view_url method not found. Available methods: {available_methods}")
                    return None
                
            except Exception as url_error:
                logger.error(f"Failed to generate presigned URL for session {session_id}: {url_error}")
                # Mark session as error
                with self.session_lock:
                    if session_id in self.active_sessions:
                        self.active_sessions[session_id].status = "error"
                        self.active_sessions[session_id].error_message = str(url_error)
                return None
                
        except Exception as e:
            logger.error(f"Error getting presigned URL for session {session_id}: {e}")
            return None

    def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """
        Get status information for a live view session.
        """
        try:
            with self.session_lock:
                live_session = self.active_sessions.get(session_id)
                
                if not live_session:
                    return {
                        "exists": False,
                        "status": "not_found",
                        "message": f"Session {session_id} not found"
                    }
                
                return {
                    "exists": True,
                    "status": live_session.status,
                    "order_id": live_session.order_id,
                    "automation_method": live_session.automation_method,
                    "created_at": live_session.created_at.isoformat(),
                    "last_accessed": live_session.last_accessed.isoformat(),
                    "error_message": live_session.error_message
                }
                
        except Exception as e:
            logger.error(f"Error getting session status for {session_id}: {e}")
            return {
                "exists": False,
                "status": "error",
                "message": str(e)
            }

    def terminate_session(self, session_id: str) -> bool:
        """
        Terminate a live view session and cleanup resources.
        """
        try:
            with self.session_lock:
                live_session = self.active_sessions.get(session_id)
                
                if not live_session:
                    logger.warning(f"Session {session_id} not found for termination")
                    return False
                
                # Mark as terminated
                live_session.status = "terminated"
                
                # Cleanup AgentCore session
                try:
                    if live_session.agentcore_session:
                        live_session.agentcore_session.__exit__(None, None, None)
                        logger.info(f"AgentCore session cleaned up for {session_id}")
                except Exception as cleanup_error:
                    logger.warning(f"Error cleaning up AgentCore session {session_id}: {cleanup_error}")
                
                # Remove from active sessions
                del self.active_sessions[session_id]
            
            logger.info(f"Successfully terminated live view session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error terminating session {session_id}: {e}")
            return False

    def get_session_for_order(self, order_id: str) -> Optional[str]:
        """
        Get active session ID for an order, if exists.
        """
        try:
            with self.session_lock:
                live_session = self._find_session_by_order(order_id)
                if live_session and live_session.status == "active":
                    live_session.last_accessed = datetime.now(timezone.utc)
                    return live_session.session_id
                return None
                
        except Exception as e:
            logger.error(f"Error getting session for order {order_id}: {e}")
            return None

    def list_active_sessions(self) -> Dict[str, Dict[str, Any]]:
        """
        List all active live view sessions.
        """
        try:
            with self.session_lock:
                result = {}
                for session_id, live_session in self.active_sessions.items():
                    result[session_id] = {
                        "order_id": live_session.order_id,
                        "automation_method": live_session.automation_method,
                        "status": live_session.status,
                        "created_at": live_session.created_at.isoformat(),
                        "last_accessed": live_session.last_accessed.isoformat(),
                        "error_message": live_session.error_message
                    }
                return result
                
        except Exception as e:
            logger.error(f"Error listing active sessions: {e}")
            return {}

    def _find_session_by_order(self, order_id: str) -> Optional[LiveViewSession]:
        """Find active session by order ID (must be called with session_lock held)"""
        for live_session in self.active_sessions.values():
            if live_session.order_id == order_id:
                return live_session
        return None

    def _cleanup_loop(self):
        """Background cleanup loop for expired sessions"""
        while True:
            try:
                # Sleep for 5 minutes between cleanup cycles
                threading.Event().wait(300)
                
                now = datetime.now(timezone.utc)
                expired_sessions = []
                
                with self.session_lock:
                    for session_id, live_session in self.active_sessions.items():
                        # Terminate sessions that haven't been accessed in 30 minutes
                        if (now - live_session.last_accessed).total_seconds() > 1800:
                            expired_sessions.append(session_id)
                        # Also terminate error sessions older than 5 minutes
                        elif (live_session.status == "error" and 
                              (now - live_session.created_at).total_seconds() > 300):
                            expired_sessions.append(session_id)
                
                # Terminate expired sessions
                for session_id in expired_sessions:
                    logger.info(f"Cleaning up expired live view session: {session_id}")
                    self.terminate_session(session_id)
                
                if expired_sessions:
                    logger.info(f"Cleaned up {len(expired_sessions)} expired live view sessions")
                    
            except Exception as e:
                logger.error(f"Error in live view cleanup loop: {e}")

    def shutdown(self):
        """Shutdown the service and cleanup all sessions"""
        logger.info("Shutting down LiveViewService")
        
        with self.session_lock:
            session_ids = list(self.active_sessions.keys())
        
        for session_id in session_ids:
            self.terminate_session(session_id)
        
        logger.info("LiveViewService shutdown complete")


# Global instance
_live_view_service = None


def get_live_view_service(config: Dict[str, Any] = None, db_manager=None) -> LiveViewService:
    """Get or create global LiveViewService instance"""
    global _live_view_service
    
    if _live_view_service is None:
        if config is None:
            raise ValueError("Config required for first initialization of LiveViewService")
        _live_view_service = LiveViewService(config, db_manager)
    
    return _live_view_service