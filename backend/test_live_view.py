#!/usr/bin/env python3
"""
Test script for LiveViewService
"""

import asyncio
import logging
from services.live_view_service import LiveViewService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_live_view_service():
    """Test LiveViewService functionality"""
    
    # Test configuration
    config = {
        "agentcore_region": "us-west-2"
    }
    
    # Create LiveViewService
    live_view_service = LiveViewService(config, db_manager=None)
    
    try:
        # Test creating a live session
        logger.info("Testing live session creation...")
        session_id = live_view_service.create_live_session(
            order_id="test-order-123",
            automation_method="strands_playwright_mcp"
        )
        
        if session_id:
            logger.info(f"✅ Live session created: {session_id}")
            
            # Test getting presigned URL
            logger.info("Testing presigned URL generation...")
            presigned_url = live_view_service.get_presigned_url(session_id, expires=300)
            
            if presigned_url:
                logger.info(f"✅ Presigned URL generated: {presigned_url[:100]}...")
            else:
                logger.error("❌ Failed to generate presigned URL")
            
            # Test session status
            status = live_view_service.get_session_status(session_id)
            logger.info(f"Session status: {status}")
            
            # Cleanup
            live_view_service.terminate_session(session_id)
            logger.info("✅ Session terminated")
            
        else:
            logger.error("❌ Failed to create live session")
            
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Shutdown service
        live_view_service.shutdown()

if __name__ == "__main__":
    asyncio.run(test_live_view_service())