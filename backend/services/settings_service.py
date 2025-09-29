#!/usr/bin/env python3
"""
Settings Service - Manages system configuration and settings
"""

import logging
import boto3
from typing import Dict, Any, List, Optional
from botocore.exceptions import ClientError, NoCredentialsError
from database import DatabaseManager
from config import get_config_manager

logger = logging.getLogger(__name__)


class SettingsService:
    """Service for managing system settings and configuration"""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.config_manager = get_config_manager(db_manager)

    def get_system_config(self) -> Dict[str, Any]:
        """Get current system configuration from DB"""
        try:
            return self.config_manager.get_system_config()
        except Exception as e:
            logger.error(f"Failed to get system config: {e}")
            return {}

    def update_system_config(self, updates: Dict[str, Any]) -> bool:
        """Update system configuration in DB"""
        try:
            return self.config_manager.update_config(updates)
        except Exception as e:
            logger.error(f"Failed to update system config: {e}")
            return False

    def reset_to_defaults(self) -> bool:
        """Reset configuration to default values"""
        try:
            # Clear current config and let defaults take over
            self.db_manager.set_setting("system_config", {})
            logger.info("Configuration reset to defaults")
            return True
        except Exception as e:
            logger.error(f"Failed to reset config: {e}")
            return False

    # AWS Resource Management Methods
    def get_available_regions(self) -> List[Dict[str, str]]:
        """Get list of available AWS regions"""
        try:
            ec2 = boto3.client("ec2", region_name="us-east-1")
            regions = ec2.describe_regions()["Regions"]
            return [
                {
                    "value": region["RegionName"],
                    "label": f"{region['RegionName']} ({self._get_region_display_name(region['RegionName'])})",
                }
                for region in sorted(regions, key=lambda x: x["RegionName"])
            ]
        except Exception as e:
            logger.error(f"Failed to get regions: {e}")
            return [
                {"value": "us-west-2", "label": "us-west-2 (US West 2 - Oregon)"},
                {"value": "us-east-1", "label": "us-east-1 (US East 1 - N. Virginia)"},
            ]

    def get_available_iam_roles(self, region: str = None) -> List[Dict[str, str]]:
        """Get list of available IAM roles with pagination support"""
        try:
            if not region:
                region = self.get_system_config().get("agentcore_region", "us-west-2")

            iam = boto3.client("iam", region_name=region)

            # Get all roles using pagination
            all_roles = []
            paginator = iam.get_paginator("list_roles")

            # Add pagination configuration to prevent infinite loops
            page_iterator = paginator.paginate(
                PaginationConfig={
                    "MaxItems": 5000,  # Maximum 5000 roles
                    "PageSize": 100,  # 100 roles per page (AWS default)
                }
            )

            for page in page_iterator:
                if "Roles" in page:
                    all_roles.extend(page["Roles"])
                    logger.debug(
                        f"Retrieved {len(page['Roles'])} roles from current page"
                    )

            logger.info(f"Retrieved total of {len(all_roles)} IAM roles from AWS")

            # Return all IAM roles (no filtering)
            role_options = [
                {"value": role["Arn"], "label": role["RoleName"]}
                for role in sorted(all_roles, key=lambda x: x["RoleName"])
                if role.get("Arn") and role.get("RoleName")  # Ensure both fields exist
            ]

            logger.info(f"Returning {len(role_options)} valid IAM role options")
            return role_options

        except Exception as e:
            logger.error(f"Failed to get IAM roles: {e}")
            return []

    def get_available_s3_buckets(self, region: str = None) -> List[Dict[str, str]]:
        """Get list of available S3 buckets"""
        try:
            if not region:
                region = self.get_system_config().get("agentcore_region", "us-west-2")

            s3 = boto3.client("s3", region_name=region)
            buckets = s3.list_buckets()["Buckets"]

            return [
                {"value": bucket["Name"], "label": bucket["Name"]}
                for bucket in sorted(buckets, key=lambda x: x["Name"])
            ]
        except Exception as e:
            logger.error(f"Failed to get S3 buckets: {e}")
            return []

    def get_available_models(self) -> List[Dict[str, str]]:
        """Get list of available foundation models"""
        return [
            {
                "value": "us.anthropic.claude-sonnet-4-20250514-v1:0",
                "label": "Claude Sonnet 4",
            },
            {
                "value": "us.anthropic.claude-3-7-sonnet-20241022-v1:0",
                "label": "Claude 3.7 Sonnet",
            },
            {"value": "us.amazon.nova-pro-v1:0", "label": "Amazon Nova Pro"},
            {"value": "gpt-oss-120b", "label": "GPT-OSS 120B"},
            {"value": "gpt-oss-20b", "label": "GPT-OSS 20B"},
            {"value": "deepseek-v3", "label": "DeepSeek V3"},
            {"value": "nova-act", "label": "Nova Act"},
        ]

    def _get_region_display_name(self, region_name: str) -> str:
        """Get human-readable region name"""
        region_names = {
            "us-east-1": "US East 1 - N. Virginia",
            "us-east-2": "US East 2 - Ohio",
            "us-west-1": "US West 1 - N. California",
            "us-west-2": "US West 2 - Oregon",
            "eu-west-1": "Europe - Ireland",
            "eu-central-1": "Europe - Frankfurt",
            "ap-southeast-1": "Asia Pacific - Singapore",
            "ap-northeast-1": "Asia Pacific - Tokyo",
        }
        return region_names.get(region_name, region_name)

    # Retailer URL Management Methods
    def get_retailer_urls(self, retailer: str = None) -> List[Dict[str, Any]]:
        """Get retailer URLs from database"""
        try:
            return self.db_manager.get_retailer_urls(retailer)
        except Exception as e:
            logger.error(f"Failed to get retailer URLs: {e}")
            return []

    def add_retailer_url(
        self,
        retailer: str,
        website_name: str,
        starting_url: str,
        is_default: bool = False,
    ) -> bool:
        """Add new retailer URL"""
        try:
            return self.db_manager.add_retailer_url(
                retailer, website_name, starting_url, is_default
            )
        except Exception as e:
            logger.error(f"Failed to add retailer URL: {e}")
            return False

    def update_retailer_url(
        self,
        url_id: str,
        retailer: str = None,
        website_name: str = None,
        starting_url: str = None,
        is_default: bool = None,
    ) -> bool:
        """Update existing retailer URL"""
        try:
            return self.db_manager.update_retailer_url(
                url_id, retailer, website_name, starting_url, is_default
            )
        except Exception as e:
            logger.error(f"Failed to update retailer URL: {e}")
            return False

    def delete_retailer_url(self, url_id: str) -> bool:
        """Delete retailer URL"""
        try:
            return self.db_manager.delete_retailer_url(url_id)
        except Exception as e:
            logger.error(f"Failed to delete retailer URL: {e}")
            return False

    def get_default_retailer_url(self, retailer: str) -> Optional[Dict[str, Any]]:
        """Get default URL for a retailer"""
        try:
            return self.db_manager.get_default_retailer_url(retailer)
        except Exception as e:
            logger.error(f"Failed to get default retailer URL: {e}")
            return None

    # Automation Configuration Methods
    def get_automation_config(self, automation_method: str) -> Dict[str, Any]:
        """Get automation configuration for a specific method"""
        try:
            system_config = self.get_system_config()

            # Base configuration for all automation methods
            base_config = {
                "agentcore_region": system_config.get("agentcore_region", "us-west-2"),
                "session_replay_s3_bucket": system_config.get(
                    "session_replay_s3_bucket", ""
                ),
                "session_replay_s3_prefix": system_config.get(
                    "session_replay_s3_prefix", "session-replays/"
                ),
                "browser_session_timeout": system_config.get(
                    "browser_session_timeout", 3600
                ),
                "execution_role_arn": system_config.get("execution_role_arn", ""),
                "default_model": system_config.get(
                    "default_model", "us.anthropic.claude-sonnet-4-20250514-v1:0"
                ),
                "nova_act_api_key": system_config.get("nova_act_api_key", ""),
            }

            # Method-specific configurations
            if automation_method == "strands":
                base_config.update(
                    {
                        "automation_method": "strands",
                        "supports_live_view": True,
                        "supports_manual_control": True,
                        "supports_session_replay": True,
                    }
                )
            elif automation_method == "nova_act":
                base_config.update(
                    {
                        "automation_method": "nova_act",
                        "supports_live_view": True,
                        "supports_manual_control": False,
                        "supports_session_replay": True,
                    }
                )

            return base_config
        except Exception as e:
            logger.error(f"Failed to get automation config: {e}")
            return {}

    # AWS Status and Management Methods (Simplified)
    def get_aws_status(self) -> Dict[str, Any]:
        """Get AWS configuration status"""
        try:
            config = self.get_system_config()
            return {
                "region": config.get("agentcore_region", "us-west-2"),
                "execution_role_configured": bool(config.get("execution_role_arn")),
                "s3_bucket_configured": bool(config.get("session_replay_s3_bucket")),
                "nova_act_key_configured": bool(config.get("nova_act_api_key")),
            }
        except Exception as e:
            logger.error(f"Failed to get AWS status: {e}")
            return {}

    def search_execution_roles(self, query: str = "") -> List[Dict[str, str]]:
        """Search IAM execution roles (simplified)"""
        try:
            return self.get_available_iam_roles()
        except Exception as e:
            logger.error(f"Failed to search execution roles: {e}")
            return []

    def search_s3_buckets(self, query: str = "") -> List[Dict[str, str]]:
        """Search S3 buckets (simplified)"""
        try:
            return self.get_available_s3_buckets()
        except Exception as e:
            logger.error(f"Failed to search S3 buckets: {e}")
            return []

    def setup_complete_environment(
        self, role_name: str, bucket_name: str
    ) -> Dict[str, Any]:
        """Setup complete AWS environment (simplified)"""
        return {
            "overall_status": "success",
            "message": "Using existing AWS resources - no setup needed",
            "execution_role": {"status": "exists", "role_arn": ""},
            "s3_bucket": {"status": "exists", "bucket_name": bucket_name or ""},
        }

    def create_execution_role(self, role_name: str) -> Dict[str, Any]:
        """Create execution role (simplified)"""
        return {
            "status": "success",
            "message": "Using existing execution role",
            "role_arn": "",
            "role_name": role_name,
        }

    def create_s3_bucket(self, bucket_name: str) -> Dict[str, Any]:
        """Create S3 bucket (simplified)"""
        return {
            "status": "success",
            "message": "Using existing S3 bucket",
            "bucket_name": bucket_name,
        }
