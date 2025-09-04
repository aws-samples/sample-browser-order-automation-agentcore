#!/usr/bin/env python3
"""
Configuration manager for order automation system
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class RetailerConfig:
    """Configuration for supported retailers"""
    
    SUPPORTED_RETAILERS = {
        "gucci": {
            "name": "Gucci",
            "base_url": "https://www.gucci.com",
            "description": "Luxury fashion items from Gucci official store"
        },
        "bergdorf_goodman": {
            "name": "Bergdorf Goodman",
            "base_url": "https://www.bergdorfgoodman.com",
            "description": "High-end luxury department store with designer collections"
        },
        "bloomingdales": {
            "name": "Bloomingdales",
            "base_url": "https://www.bloomingdales.com",
            "description": "Premium department store with contemporary and designer brands"
        },
        "farfetch": {
            "name": "Farfetch",
            "base_url": "https://www.farfetch.com",
            "description": "Global luxury fashion marketplace with boutique brands"
        },
        "free_people": {
            "name": "Free People",
            "base_url": "https://www.freepeople.com",
            "description": "Bohemian and contemporary women's clothing and accessories"
        },
        "moda_operandi": {
            "name": "Moda Operandi",
            "base_url": "https://www.modaoperandi.com",
            "description": "Runway fashion and pre-order luxury designer pieces"
        },
        "mytheresa": {
            "name": "Mytheresa",
            "base_url": "https://www.mytheresa.com",
            "description": "Curated luxury fashion from top international designers"
        },
        "neiman_marcus": {
            "name": "Neiman Marcus",
            "base_url": "https://www.neimanmarcus.com",
            "description": "Luxury department store specializing in designer fashion"
        },
        "net_a_porter": {
            "name": "Net-A-Porter",
            "base_url": "https://www.net-a-porter.com",
            "description": "Premier online luxury fashion destination for women"
        },
        "revolve": {
            "name": "Revolve",
            "base_url": "https://www.revolve.com",
            "description": "Trendy contemporary fashion for young women"
        },
        "ssense": {
            "name": "Ssense",
            "base_url": "https://www.ssense.com",
            "description": "Avant-garde and streetwear fashion from emerging designers"
        },
        "valentino": {
            "name": "Valentino",
            "base_url": "https://www.valentino.com",
            "description": "Italian luxury fashion house with haute couture and ready-to-wear"
        }
    }


class SystemConfig:
    """System-wide configuration"""
    
    DEFAULT_CONFIG = {
        "nova_act_api_key": "",
        "agentcore_region": "us-west-2",
        "default_model": "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
    }


class AutomationConfig:
    """Configuration for automation methods"""
    
    NOVA_ACT_CONFIG = {
        "name": "Nova Act",
        "description": "AI-powered browser automation using Nova Act",
        "timeout_seconds": 300,
        "max_retries": 3
    }
    
    STRANDS_BROWSER_CONFIG = {
        "name": "Strands + Browser Tools",
        "description": "AI-powered browser automation using Strands with browser tools and AgentCore Browser",
        "timeout_seconds": 600,
        "max_retries": 3
    }
    
    STRANDS_PLAYWRIGHT_MCP_CONFIG = {
        "name": "Strands + Playwright MCP",
        "description": "Structured browser automation with Strands, Playwright MCP, and AgentCore Browser",
        "timeout_seconds": 600,
        "max_retries": 2
    }





class ConfigManager:
    """Centralized configuration manager"""
    
    def __init__(self, db_manager=None):
        self.db_manager = db_manager
        self._config_cache = {}
        self._load_configs()
    
    def _load_configs(self):
        """Load configurations from database or initialize with defaults"""
        try:
            if self.db_manager:
                self._load_from_database()
            else:
                self._load_default_configs()
                
            logger.info("Configuration loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load configurations: {e}")
            self._load_default_configs()
    
    def _load_from_database(self):
        """Load configurations from database"""
        try:
            # Get existing configurations from database
            retailers_config = self.db_manager.get_setting("retailers_config")
            system_config = self.db_manager.get_setting("system_config")
            automation_config = self.db_manager.get_setting("automation_config")
            
            # If no config exists in database, initialize with defaults
            if not retailers_config:
                retailers_config = RetailerConfig.SUPPORTED_RETAILERS
                self.db_manager.set_setting("retailers_config", retailers_config)
                logger.info("Initialized retailers config in database")
            
            if not system_config:
                system_config = SystemConfig.DEFAULT_CONFIG
                self.db_manager.set_setting("system_config", system_config)
                logger.info("Initialized system config in database")
            
            if not automation_config:
                automation_config = {
                    "nova_act": AutomationConfig.NOVA_ACT_CONFIG,
                    "strands_browser": AutomationConfig.STRANDS_BROWSER_CONFIG,
                    "strands_playwright_mcp": AutomationConfig.STRANDS_PLAYWRIGHT_MCP_CONFIG
                }
                self.db_manager.set_setting("automation_config", automation_config)
                logger.info("Initialized automation config in database")
            
            # Load into cache
            self._config_cache = {
                "retailers": retailers_config,
                "system": system_config,
                "automation": automation_config
            }
            
        except Exception as e:
            logger.error(f"Failed to load from database: {e}")
            raise
    
    def _load_default_configs(self):
        """Load default configurations (fallback)"""
        self._config_cache = {
            "retailers": RetailerConfig.SUPPORTED_RETAILERS,
            "system": SystemConfig.DEFAULT_CONFIG
        }
    
    def get_retailer_config(self, retailer: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific retailer"""
        return self._config_cache.get("retailers", {}).get(retailer.lower())
    
    def get_supported_retailers(self) -> List[str]:
        """Get list of supported retailers"""
        return list(self._config_cache.get("retailers", {}).keys())
    
    def get_system_config(self, key: str = None) -> Any:
        """Get system configuration"""
        system_config = self._config_cache.get("system", {})
        if key:
            return system_config.get(key)
        return system_config
    
    def update_system_config(self, key: str, value: Any):
        """Update system configuration"""
        try:
            if "system" not in self._config_cache:
                self._config_cache["system"] = {}
            
            self._config_cache["system"][key] = value
            
            # Persist to database if available
            if self.db_manager:
                self.db_manager.set_setting("system_config", self._config_cache["system"])
            
            logger.info(f"Updated system config: {key}")
            
        except Exception as e:
            logger.error(f"Failed to update system config: {e}")
            raise
    
    def is_retailer_supported(self, retailer: str) -> bool:
        """Check if retailer is supported"""
        return retailer.lower() in self._config_cache.get("retailers", {})
    
    def validate_order_config(self, retailer: str, automation_method: str) -> bool:
        """Validate if retailer supports the automation method"""
        if not self.is_retailer_supported(retailer):
            return False
        
        # For now, all retailers support all automation methods
        supported_methods = ["nova_act", "strands_browser", "strands_playwright_mcp"]
        return automation_method.lower() in supported_methods
    
    def get_automation_config(self, automation_method: str) -> Dict[str, Any]:
        """Get configuration for specific automation method"""
        method_configs = {
            "nova_act": AutomationConfig.NOVA_ACT_CONFIG,
            "strands_browser": AutomationConfig.STRANDS_BROWSER_CONFIG,
            "strands_playwright_mcp": AutomationConfig.STRANDS_PLAYWRIGHT_MCP_CONFIG
        }
        
        return method_configs.get(automation_method, {})
    
    def get_default_browser_config(self) -> Dict[str, Any]:
        """Get default browser configuration"""
        return {
            "browser_timeout": 30000,
            "page_timeout": 10000,
            "navigation_timeout": 30000,
            "headless": False,
            "viewport": {"width": 1920, "height": 1080},
            "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
    
    def get_queue_settings(self) -> Dict[str, Any]:
        """Get queue configuration settings"""
        return self._config_cache.get("queue_settings", {
            "max_concurrent_orders": 5,
            "order_timeout_minutes": 30,
            "retry_attempts": 3,
            "retry_delay_seconds": 60
        })
    
    def get_all_configs(self) -> Dict[str, Any]:
        """Get all configurations for API responses"""
        return {
            "retailers": self._config_cache.get("retailers", {}),
            "system": self._config_cache.get("system", {}),
            "queue_settings": self.get_queue_settings(),
            "supported_retailers": self.get_supported_retailers()
        }


# Global config manager instance will be initialized in app.py with database connection
config_manager = None