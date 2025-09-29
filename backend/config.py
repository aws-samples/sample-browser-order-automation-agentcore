#!/usr/bin/env python3
"""
Configuration Manager - Single Source of Truth
Manages all system configuration with DB integration
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Agent configuration data class"""

    default_model: str
    agentcore_region: str
    session_replay_s3_bucket: str
    session_replay_s3_prefix: str
    browser_session_timeout: int
    max_concurrent_orders: int
    processing_timeout: int
    execution_role_arn: str
    nova_act_api_key: str = ""


class ConfigManager:
    """Centralized configuration manager with DB integration"""

    # Default configuration values
    DEFAULT_CONFIG = {
        "agentcore_region": "us-west-2",
        "session_replay_s3_bucket": "",
        "session_replay_s3_prefix": "session-replays/",
        "browser_session_timeout": 3600,
        "max_concurrent_orders": 5,
        "default_model": "us.anthropic.claude-sonnet-4-20250514-v1:0",
        "nova_act_api_key": os.getenv("NOVA_ACT_API_KEY", ""),
        "execution_role_arn": "",
        "processing_timeout": 1800,
    }

    def __init__(self, db_manager=None):
        self.db_manager = db_manager
        self._config_cache = None
        self._cache_timestamp = 0

    def get_system_config(self) -> Dict[str, Any]:
        """Get current system configuration from DB with fallback to defaults"""
        try:
            if self.db_manager:
                # Load from database
                stored_config = self.db_manager.get_setting("system_config") or {}
                # Merge with defaults, ensuring all required keys exist
                config = self.DEFAULT_CONFIG.copy()
                config.update(stored_config)

                # Ensure all required keys are present
                for key in self.DEFAULT_CONFIG:
                    if key not in config:
                        config[key] = self.DEFAULT_CONFIG[key]

                # Update cache
                self._config_cache = config
                self._cache_timestamp = (
                    os.path.getmtime(__file__) if os.path.exists(__file__) else 0
                )

                return config
            else:
                # Return defaults if no database
                return self.DEFAULT_CONFIG.copy()
        except Exception as e:
            logger.error(f"Failed to get system config: {e}")
            return self.DEFAULT_CONFIG.copy()

    def get_agent_config(self, agent_type: str = "strands") -> AgentConfig:
        """Get configuration for specific agent type"""
        config = self.get_system_config()

        if agent_type == "nova_act":
            return AgentConfig(
                default_model=config.get(
                    "default_model", self.DEFAULT_CONFIG["default_model"]
                ),
                agentcore_region=config.get(
                    "agentcore_region", self.DEFAULT_CONFIG["agentcore_region"]
                ),
                session_replay_s3_bucket=config.get(
                    "session_replay_s3_bucket",
                    self.DEFAULT_CONFIG["session_replay_s3_bucket"],
                ),
                session_replay_s3_prefix=config.get(
                    "session_replay_s3_prefix",
                    self.DEFAULT_CONFIG["session_replay_s3_prefix"],
                ),
                browser_session_timeout=config.get(
                    "browser_session_timeout",
                    self.DEFAULT_CONFIG["browser_session_timeout"],
                ),
                max_concurrent_orders=config.get(
                    "max_concurrent_orders",
                    self.DEFAULT_CONFIG["max_concurrent_orders"],
                ),
                processing_timeout=config.get(
                    "processing_timeout", self.DEFAULT_CONFIG["processing_timeout"]
                ),
                execution_role_arn=config.get(
                    "execution_role_arn", self.DEFAULT_CONFIG["execution_role_arn"]
                ),
                nova_act_api_key=config.get(
                    "nova_act_api_key", self.DEFAULT_CONFIG["nova_act_api_key"]
                ),
            )
        else:  # strands
            return AgentConfig(
                default_model=config.get(
                    "default_model", self.DEFAULT_CONFIG["default_model"]
                ),
                agentcore_region=config.get(
                    "agentcore_region", self.DEFAULT_CONFIG["agentcore_region"]
                ),
                session_replay_s3_bucket=config.get(
                    "session_replay_s3_bucket",
                    self.DEFAULT_CONFIG["session_replay_s3_bucket"],
                ),
                session_replay_s3_prefix=config.get(
                    "session_replay_s3_prefix",
                    self.DEFAULT_CONFIG["session_replay_s3_prefix"],
                ),
                browser_session_timeout=config.get(
                    "browser_session_timeout",
                    self.DEFAULT_CONFIG["browser_session_timeout"],
                ),
                max_concurrent_orders=config.get(
                    "max_concurrent_orders",
                    self.DEFAULT_CONFIG["max_concurrent_orders"],
                ),
                processing_timeout=config.get(
                    "processing_timeout", self.DEFAULT_CONFIG["processing_timeout"]
                ),
                execution_role_arn=config.get(
                    "execution_role_arn", self.DEFAULT_CONFIG["execution_role_arn"]
                ),
                nova_act_api_key="",  # Strands doesn't use Nova Act API key
            )

    def update_config(self, updates: Dict[str, Any]) -> bool:
        """Update system configuration in DB"""
        try:
            if not self.db_manager:
                logger.warning("No database manager available for config update")
                return False

            # Get current config
            current_config = self.db_manager.get_setting("system_config") or {}
            # Update with new values
            current_config.update(updates)
            # Save back to database
            self.db_manager.set_setting("system_config", current_config)

            # Update legacy agent_config.json for backward compatibility
            self._update_agent_config_file(current_config)

            # Clear cache
            self._config_cache = None

            logger.info(f"Updated system config with keys: {list(updates.keys())}")
            return True

        except Exception as e:
            logger.error(f"Failed to update system config: {e}")
            return False

    def _update_agent_config_file(self, config: Dict[str, Any]):
        """Legacy method - no longer creates files, all config is DB-based"""
        # All configuration is now stored in database only
        # This method is kept for backward compatibility but does nothing
        logger.info("Configuration updated in database - no file generation needed")


# Global config manager instance
_config_manager = None


def get_config_manager(db_manager=None) -> ConfigManager:
    """Get global config manager instance"""
    global _config_manager
    if _config_manager is None or (
        _config_manager.db_manager is None and db_manager is not None
    ):
        _config_manager = ConfigManager(db_manager)
    return _config_manager


# Convenience functions for backward compatibility
def load_agent_config(agent_type: str = "strands", db_manager=None) -> Dict[str, Any]:
    """Load configuration for specific agent type"""
    config_manager = get_config_manager(db_manager)
    agent_config = config_manager.get_agent_config(agent_type)
    return {
        "default_model": agent_config.default_model,
        "agentcore_region": agent_config.agentcore_region,
        "session_replay_s3_bucket": agent_config.session_replay_s3_bucket,
        "session_replay_s3_prefix": agent_config.session_replay_s3_prefix,
        "browser_session_timeout": agent_config.browser_session_timeout,
        "max_concurrent_orders": agent_config.max_concurrent_orders,
        "processing_timeout": agent_config.processing_timeout,
        "execution_role_arn": agent_config.execution_role_arn,
        "nova_act_api_key": agent_config.nova_act_api_key,
    }


def get_default_model(agent_type: str = "strands", db_manager=None) -> str:
    """Get default model for agent type"""
    config_manager = get_config_manager(db_manager)
    agent_config = config_manager.get_agent_config(agent_type)
    return agent_config.default_model


def get_processing_timeout(agent_type: str = "strands", db_manager=None) -> int:
    """Get processing timeout for agent type"""
    config_manager = get_config_manager(db_manager)
    agent_config = config_manager.get_agent_config(agent_type)
    return agent_config.processing_timeout


def get_browser_session_timeout(agent_type: str = "strands", db_manager=None) -> int:
    """Get browser session timeout for agent type"""
    config_manager = get_config_manager(db_manager)
    agent_config = config_manager.get_agent_config(agent_type)
    return agent_config.browser_session_timeout


def get_agentcore_region(agent_type: str = "strands", db_manager=None) -> str:
    """Get AgentCore region for agent type"""
    config_manager = get_config_manager(db_manager)
    agent_config = config_manager.get_agent_config(agent_type)
    return agent_config.agentcore_region


def get_execution_role_arn(agent_type: str = "strands", db_manager=None) -> str:
    """Get execution role ARN for agent type"""
    config_manager = get_config_manager(db_manager)
    agent_config = config_manager.get_agent_config(agent_type)
    return agent_config.execution_role_arn


def get_s3_config(agent_type: str = "strands", db_manager=None) -> Dict[str, str]:
    """Get S3 configuration for agent type"""
    config_manager = get_config_manager(db_manager)
    agent_config = config_manager.get_agent_config(agent_type)
    return {
        "bucket": agent_config.session_replay_s3_bucket,
        "prefix": agent_config.session_replay_s3_prefix,
    }


def get_nova_act_api_key(db_manager=None) -> str:
    """Get Nova Act API key"""
    config_manager = get_config_manager(db_manager)
    agent_config = config_manager.get_agent_config("nova_act")
    return agent_config.nova_act_api_key
