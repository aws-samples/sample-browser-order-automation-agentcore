#!/usr/bin/env python3
"""
Test script for Strands Playwright MCP Agent
"""

import asyncio
import sys
import os
from datetime import datetime

# Add backend to path
sys.path.append(os.path.dirname(__file__))

from agents.strands_playwright_mcp_agent import StrandsPlaywrightMCPAgent


class MockOrder:
    """Mock order for testing"""
    def __init__(self):
        self.id = "test-order-123"
        self.product_name = "Gucci GG Marmont Small Matelassé Shoulder Bag"
        self.product_url = "https://www.farfetch.com/shopping/women/gucci-gg-marmont-small-matelass-shoulder-bag-item-12345.aspx"
        self.product_size = "One Size"
        self.product_color = "Black"
        self.shipping_address = {
            "first_name": "Jane",
            "last_name": "Doe",
            "address_line_1": "123 Test Street",
            "city": "New York",
            "state": "NY",
            "postal_code": "10001"
        }


async def test_strands_mcp_agent():
    """Test the Strands Playwright MCP Agent"""
    print("🧪 Testing Strands Playwright MCP Agent")
    
    # Configuration
    config = {
        "agentcore_region": "us-west-2",
        "model": "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
    }
    
    retailer_config = {
        "name": "farfetch",
        "base_url": "https://www.farfetch.com"
    }
    
    # Create agent
    agent = StrandsPlaywrightMCPAgent(config, retailer_config)
    
    try:
        # Start session
        print("🚀 Starting session...")
        session_info = await agent.start_session("test-session-123")
        print(f"✅ Session started: {session_info}")
        
        # Create mock order
        order = MockOrder()
        
        # Process order
        print("📦 Processing order...")
        
        async def progress_callback(progress):
            print(f"📊 Progress: {progress}")
        
        result = await agent.process_order(order, progress_callback)
        print(f"🎯 Order result: {result}")
        
        # Get live view URL if available
        try:
            live_url = agent.get_live_view_url()
            print(f"👀 Live view URL: {live_url}")
        except Exception as live_error:
            print(f"⚠️ Live view not available: {live_error}")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Cleanup
        print("🧹 Cleaning up...")
        await agent.cleanup()
        print("✅ Test completed")


if __name__ == "__main__":
    asyncio.run(test_strands_mcp_agent())