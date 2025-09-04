#!/usr/bin/env python3
"""
Screenshot Service - Handles screenshot capture and storage
"""

import os
import uuid
import base64
import logging
from typing import Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class ScreenshotService:
    """Service for capturing and managing screenshots"""

    def __init__(self, screenshots_dir: str, db_manager=None):
        self.screenshots_dir = screenshots_dir
        self.db_manager = db_manager
        os.makedirs(screenshots_dir, exist_ok=True)

    def save_screenshot(
        self, 
        screenshot_data: bytes, 
        session_id: str, 
        step_name: str = None,
        description: str = None
    ) -> Optional[str]:
        """Save screenshot data and return URL"""
        try:
            screenshot_id = str(uuid.uuid4())
            screenshot_filename = f"{session_id}_{screenshot_id}.jpg"
            screenshot_path = os.path.join(self.screenshots_dir, screenshot_filename)

            # Handle base64 or binary data
            if isinstance(screenshot_data, str):
                screenshot_bytes = base64.b64decode(screenshot_data)
            else:
                screenshot_bytes = screenshot_data

            with open(screenshot_path, "wb") as f:
                f.write(screenshot_bytes)

            screenshot_url = f"/api/screenshots/{screenshot_filename}"

            # Add screenshot to database
            if self.db_manager and session_id:
                self.db_manager.add_screenshot(
                    session_id,
                    screenshot_url,
                    step_name,
                    description or f"Screenshot captured during {step_name or 'automation'}",
                )

            logger.info(f"Screenshot saved: {screenshot_filename}")
            return screenshot_url

        except Exception as e:
            logger.error(f"Failed to save screenshot: {e}")
            return None

    def save_mcp_screenshot(
        self, 
        screenshot_data: bytes, 
        session_id: str, 
        step_name: str = None
    ) -> Optional[str]:
        """Save screenshot from MCP tools"""
        screenshot_id = str(uuid.uuid4())
        screenshot_filename = f"{session_id}_{screenshot_id}_mcp.jpg"
        
        return self.save_screenshot(
            screenshot_data, 
            session_id, 
            step_name or "mcp_tool",
            f"Screenshot from MCP tool during {step_name or 'automation'}"
        )