#!/usr/bin/env python3
"""
Agent Factory for Order Automation System
Creates and manages different automation agents based on method selection
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class AgentFactory:
    """
    Factory class for creating automation agents
    
    Simplified factory that creates the appropriate agent based on automation method.
    Each agent is now self-contained and handles its own processing logic.
    """
    
    @staticmethod
    async def create_agent(automation_method: str, config: Dict[str, Any], retailer_config: Dict[str, Any]):
        """
        Create an agent instance based on automation method
        
        Args:
            automation_method: Either 'strands_agent' or 'playwright_mcp'
            config: System configuration (merged with global config)
            retailer_config: Retailer-specific configuration
            
        Returns:
            Agent instance ready for processing orders
        """
        try:
            logger.info(f"Creating agent for automation method: {automation_method}")
            logger.debug(f"Config: {config}")
            logger.debug(f"Retailer config: {retailer_config}")
            
            # Merge with global configuration
            from config_manager import config_manager
            if config_manager is not None:
                global_config = config_manager.get_default_browser_config()
                merged_config = {**config, **global_config}
                logger.debug(f"Merged config: {merged_config}")
            else:
                logger.warning("config_manager is None, using default browser config")
                # Provide default browser config directly
                default_browser_config = {
                    "browser_timeout": 30000,
                    "page_timeout": 10000,
                    "navigation_timeout": 30000,
                    "headless": False,
                    "viewport": {"width": 1920, "height": 1080},
                    "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                }
                merged_config = {**config, **default_browser_config}
                logger.debug(f"Using default merged config: {merged_config}")
            
            if automation_method == "nova_act":
                logger.info("Importing NovaActAgent...")
                try:
                    from .nova_act_agent import NovaActAgent
                    logger.info("NovaActAgent imported successfully")
                except ImportError as ie:
                    logger.error(f"Failed to import NovaActAgent: {ie}")
                    raise
                
                logger.info("Creating NovaActAgent instance...")
                # Get db_manager from config if available
                db_manager = merged_config.get('db_manager')
                agent = NovaActAgent(merged_config, retailer_config, db_manager=db_manager)
                logger.info(f"Created Nova Act + AgentCore Browser agent successfully")
                return agent
                
            elif automation_method == "strands_browser":
                logger.info("Importing StrandsBrowserAgent...")
                try:
                    from .strands_browser_agent import StrandsBrowserAgent
                    logger.info("StrandsBrowserAgent imported successfully")
                except ImportError as ie:
                    logger.error(f"Failed to import StrandsBrowserAgent: {ie}")
                    raise
                
                logger.info("Creating StrandsBrowserAgent instance...")
                # Get db_manager from config if available
                db_manager = merged_config.get('db_manager')
                agent = StrandsBrowserAgent(merged_config, retailer_config, db_manager=db_manager)
                logger.info(f"Created Strands + Browser Tools + AgentCore Browser agent successfully")
                return agent
                
            elif automation_method == "strands_playwright_mcp":
                logger.info("Importing StrandsPlaywrightMCPAgent...")
                try:
                    from .strands_playwright_mcp_agent import StrandsPlaywrightMCPAgent
                    logger.info("StrandsPlaywrightMCPAgent imported successfully")
                except ImportError as ie:
                    logger.error(f"Failed to import StrandsPlaywrightMCPAgent: {ie}")
                    raise
                
                logger.info("Creating StrandsPlaywrightMCPAgent instance...")
                # Get db_manager from config if available
                db_manager = merged_config.get('db_manager')
                agent = StrandsPlaywrightMCPAgent(merged_config, retailer_config, db_manager=db_manager)
                logger.info(f"Created Strands + Playwright MCP + AgentCore Browser agent successfully")
                return agent
                
            else:
                error_msg = f"Unknown automation method: {automation_method}. Available methods: nova_act, strands_browser, strands_playwright_mcp"
                logger.error(error_msg)
                raise ValueError(error_msg)
                
        except Exception as e:
            logger.error(f"Failed to create agent for {automation_method}: {str(e)}", exc_info=True)
            raise
    
    @staticmethod
    def get_available_methods() -> Dict[str, Dict[str, Any]]:
        """Get information about available automation methods"""
        return {
            "nova_act": {
                "name": "Nova Act + AgentCore Browser",
                "description": "AI-powered browser automation using Nova Act with AgentCore Browser",
                "requirements": ["nova-act", "bedrock-agentcore"]
            },
            "strands_browser": {
                "name": "Strands + Browser Tools + AgentCore Browser", 
                "description": "Strands agent with browser tools and AgentCore Browser",
                "requirements": ["strands", "strands-tools", "bedrock-agentcore"]
            },
            "strands_playwright_mcp": {
                "name": "Strands + Playwright MCP + AgentCore Browser",
                "description": "Strands agent with Playwright MCP tools and AgentCore Browser",
                "requirements": ["strands", "mcp", "playwright", "bedrock-agentcore"]
            }
        }
    
    @staticmethod
    def validate_method_requirements(automation_method: str) -> Dict[str, Any]:
        """Validate that required dependencies are available for the automation method"""
        validation_result = {
            "method": automation_method,
            "valid": True,
            "missing_requirements": [],
            "warnings": []
        }
        
        try:
            if automation_method == "nova_act":
                # Check Nova SDK
                try:
                    from nova_act import NovaAct
                except ImportError:
                    validation_result["valid"] = False
                    validation_result["missing_requirements"].append("nova-act")
                
                # Check AgentCore
                try:
                    from bedrock_agentcore.tools.browser_client import browser_session
                except ImportError:
                    validation_result["valid"] = False
                    validation_result["missing_requirements"].append("bedrock-agentcore")
                
            elif automation_method == "playwright_mcp":
                # Check MCP
                try:
                    from mcp import stdio_client
                except ImportError:
                    validation_result["valid"] = False
                    validation_result["missing_requirements"].append("mcp")
                
                # Check Playwright
                try:
                    from playwright.async_api import async_playwright
                except ImportError:
                    validation_result["valid"] = False
                    validation_result["missing_requirements"].append("playwright")
                
                # Check AgentCore
                try:
                    from bedrock_agentcore.tools.browser_client import browser_session
                except ImportError:
                    validation_result["valid"] = False
                    validation_result["missing_requirements"].append("bedrock-agentcore")
                
                # Check Boto3 (optional)
                try:
                    import boto3
                except ImportError:
                    validation_result["warnings"].append("boto3 not available - LLM analysis will use fallback logic")
            
            else:
                validation_result["valid"] = False
                validation_result["missing_requirements"].append(f"Unknown method: {automation_method}")
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Failed to validate requirements for {automation_method}: {e}")
            return {
                "method": automation_method,
                "valid": False,
                "error": str(e),
                "missing_requirements": [],
                "warnings": []
            }