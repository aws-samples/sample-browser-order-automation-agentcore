#!/usr/bin/env python3
"""
AgentCore Manager - Global registry for managing AgentCore browser sessions
Allows sharing browser sessions between Agents and Live View Service
"""

import logging
import threading
from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


class AgentCoreManager:
    """
    Global manager for AgentCore browser sessions.
    Allows Agents to register their browser sessions and Live View to reuse them.
    Uses database for persistence and memory cache for active clients.
    """
    
    def __init__(self, db_manager=None):
        # Memory cache for active AgentCore clients (these can't be serialized to DB)
        self.active_clients: Dict[str, Any] = {}
        self.lock = threading.Lock()
        self.db_manager = db_manager
        
    def register_session(self, session_id: str, agentcore_client: Any, order_id: str = None, metadata: Dict[str, Any] = None):
        """
        Register an AgentCore browser session for sharing.
        
        Args:
            session_id: Unique session identifier
            agentcore_client: The AgentCore browser client
            order_id: Associated order ID (optional)
            metadata: Additional metadata (optional)
        """
        try:
            with self.lock:
                # Store the active client in memory (can't be serialized)
                self.active_clients[session_id] = agentcore_client
                
                # Store session info in database if available
                if self.db_manager and order_id:
                    try:
                        # Update the order with session_id
                        self.db_manager.update_order(
                            order_id=order_id,
                            session_id=session_id,
                            automation_metadata=metadata or {}
                        )
                        logger.info(f"Updated order {order_id} with session_id: {session_id}")
                    except Exception as db_error:
                        logger.warning(f"Failed to update database with session info: {db_error}")
                
                logger.info(f"Registered AgentCore session: {session_id} (order: {order_id})")
        except Exception as e:
            logger.error(f"Failed to register AgentCore session {session_id}: {e}")
    
    def get_client(self, session_id: str) -> Optional[Any]:
        """
        Get AgentCore client by session ID.
        
        Args:
            session_id: Session identifier
            
        Returns:
            AgentCore client if found, None otherwise
        """
        try:
            with self.lock:
                # Check memory cache for active client
                client = self.active_clients.get(session_id)
                if client:
                    logger.info(f"Retrieved AgentCore client for session: {session_id}")
                    return client
                else:
                    logger.warning(f"AgentCore session not found in active clients: {session_id}")
                    return None
        except Exception as e:
            logger.error(f"Failed to get AgentCore client for session {session_id}: {e}")
            return None
    
    def get_session_by_order(self, order_id: str) -> Optional[str]:
        """
        Get session ID by order ID.
        
        Args:
            order_id: Order identifier
            
        Returns:
            Session ID if found, None otherwise
        """
        try:
            # First check database for session_id
            if self.db_manager:
                try:
                    order = self.db_manager.get_order(order_id)
                    if order and hasattr(order, 'session_id') and order.session_id:
                        session_id = order.session_id
                        # Check if we have an active client for this session
                        with self.lock:
                            if session_id in self.active_clients:
                                logger.info(f"Found session {session_id} for order: {order_id}")
                                return session_id
                            else:
                                logger.warning(f"Session {session_id} found in DB but no active client")
                                return None
                    else:
                        logger.warning(f"No session_id found in database for order: {order_id}")
                        return None
                except Exception as db_error:
                    logger.error(f"Database error getting session for order {order_id}: {db_error}")
                    return None
            else:
                logger.warning("No database manager available")
                return None
        except Exception as e:
            logger.error(f"Failed to get session for order {order_id}: {e}")
            return None
    
    def unregister_session(self, session_id: str):
        """
        Unregister an AgentCore browser session.
        
        Args:
            session_id: Session identifier
        """
        try:
            with self.lock:
                if session_id in self.active_clients:
                    del self.active_clients[session_id]
                    logger.info(f"Unregistered AgentCore session: {session_id}")
                else:
                    logger.warning(f"AgentCore session not found for unregistration: {session_id}")
        except Exception as e:
            logger.error(f"Failed to unregister AgentCore session {session_id}: {e}")
    
    def list_sessions(self) -> Dict[str, Dict[str, Any]]:
        """
        List all registered sessions.
        
        Returns:
            Dictionary of session information
        """
        try:
            result = {}
            
            # Get active sessions from memory
            with self.lock:
                active_session_ids = list(self.active_clients.keys())
            
            # Get session info from database if available
            if self.db_manager:
                try:
                    # Get all orders with session_ids
                    orders = self.db_manager.get_all_orders(limit=100)
                    for order in orders:
                        if hasattr(order, 'session_id') and order.session_id:
                            session_id = order.session_id
                            result[session_id] = {
                                'order_id': order.id,
                                'active': session_id in active_session_ids,
                                'created_at': order.created_at,
                                'status': order.status,
                                'automation_method': order.automation_method
                            }
                except Exception as db_error:
                    logger.error(f"Database error listing sessions: {db_error}")
            
            # Add any active sessions not in database
            with self.lock:
                for session_id in active_session_ids:
                    if session_id not in result:
                        result[session_id] = {
                            'order_id': None,
                            'active': True,
                            'created_at': None,
                            'status': 'unknown',
                            'automation_method': 'unknown'
                        }
            
            return result
        except Exception as e:
            logger.error(f"Failed to list AgentCore sessions: {e}")
            return {}
    
    def cleanup_old_sessions(self, max_age_hours: int = 24):
        """
        Clean up old sessions that haven't been accessed recently.
        
        Args:
            max_age_hours: Maximum age in hours before cleanup
        """
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
            sessions_to_remove = []
            
            # Clean up old sessions from database
            if self.db_manager:
                try:
                    orders = self.db_manager.get_all_orders(limit=1000)
                    for order in orders:
                        if (hasattr(order, 'session_id') and order.session_id and 
                            hasattr(order, 'updated_at') and order.updated_at and
                            order.updated_at < cutoff_time):
                            
                            session_id = order.session_id
                            # Remove from active clients if present
                            with self.lock:
                                if session_id in self.active_clients:
                                    del self.active_clients[session_id]
                                    sessions_to_remove.append(session_id)
                                    
                except Exception as db_error:
                    logger.error(f"Database error during cleanup: {db_error}")
                    
            if sessions_to_remove:
                logger.info(f"Cleaned up {len(sessions_to_remove)} old AgentCore sessions")
                
        except Exception as e:
            logger.error(f"Failed to cleanup old AgentCore sessions: {e}")


# Global instance - will be initialized with database manager
agentcore_manager = None

def get_agentcore_manager(db_manager=None):
    """Get or create global AgentCore Manager instance"""
    global agentcore_manager
    if agentcore_manager is None:
        agentcore_manager = AgentCoreManager(db_manager)
    elif db_manager and agentcore_manager.db_manager is None:
        agentcore_manager.db_manager = db_manager
    return agentcore_manager