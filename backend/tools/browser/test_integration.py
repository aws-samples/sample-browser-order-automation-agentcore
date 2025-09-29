#!/usr/bin/env python3
"""Integration test for browser tools with Strands agent."""

import sys
import os
sys.path.append('..')

from strands import Agent
from browser_tools import (
    browser_install,
    browser_navigate,
    browser_click,
    browser_type,
    browser_take_screenshot,
    browser_snapshot,
    browser_close
)

def test_strands_integration():
    """Test Strands agent with our browser tools."""
    print("Testing Strands integration with custom browser tools...")
    
    try:
        # Create a simple agent with our browser tools
        agent = Agent(
            tools=[
                browser_install,
                browser_navigate,
                browser_take_screenshot,
                browser_snapshot,
                browser_close
            ],
            system_prompt="""You are a browser automation agent. 
            
Use the browser tools to:
1. Install browser and get session ID
2. Navigate to example.com
3. Take a screenshot
4. Get page snapshot
5. Close the browser

Always use the session_id returned from browser_install for all subsequent operations.
"""
        )
        
        # Test the agent
        print("\nRunning agent automation...")
        response = agent("Please automate a simple browser task: visit example.com, take a screenshot, and close the browser.")
        
        print(f"\nAgent response: {response}")
        print("\nIntegration test completed!")
        return True
        
    except Exception as e:
        print(f"Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_strands_integration()