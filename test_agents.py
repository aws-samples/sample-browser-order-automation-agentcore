#!/usr/bin/env python3
"""
Test script for the updated agent system
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.append('backend')

from backend.agents.main_agent import AgentFactory


async def test_agent_factory():
    """Test the agent factory functionality"""
    print("🧪 Testing Agent Factory...")
    
    # Test available methods
    methods = AgentFactory.get_available_methods()
    print(f"✅ Available methods: {list(methods.keys())}")
    
    for method_name, method_info in methods.items():
        print(f"\n📋 {method_name}:")
        print(f"   Name: {method_info['name']}")
        print(f"   Description: {method_info['description']}")
        print(f"   Requirements: {method_info['requirements']}")
        
        # Validate requirements
        validation = AgentFactory.validate_method_requirements(method_name)
        print(f"   Valid: {validation['valid']}")
        if validation['missing_requirements']:
            print(f"   Missing: {validation['missing_requirements']}")
        if validation['warnings']:
            print(f"   Warnings: {validation['warnings']}")


async def test_agent_creation():
    """Test creating agents"""
    print("\n🏗️  Testing Agent Creation...")
    
    config = {
        "bedrock_region": "us-west-2",
        "bedrock_model": "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
    }
    
    retailer_config = {
        "name": "Test Retailer",
        "base_url": "https://test.com",
        "automation_methods": ["strands_agent", "playwright_mcp"],
        "preferred_method": "strands_agent"
    }
    
    # Test Strands Agent creation
    try:
        print("Creating Strands Agent...")
        strands_agent = await AgentFactory.create_agent("strands_agent", config, retailer_config)
        print("✅ Strands Agent created successfully")
        
        # Test session start
        session_result = await strands_agent.start_session("test-session-001")
        print(f"✅ Session started: {session_result['session_id']}")
        print(f"   Tools loaded: {session_result.get('tools_loaded', 0)}")
        
        # Test cleanup
        await strands_agent.cleanup()
        print("✅ Strands Agent cleaned up")
        
    except Exception as e:
        print(f"❌ Strands Agent test failed: {e}")
    
    # Test Playwright MCP Agent creation
    try:
        print("\nCreating Playwright MCP Agent...")
        mcp_agent = await AgentFactory.create_agent("playwright_mcp", config, retailer_config)
        print("✅ Playwright MCP Agent created successfully")
        
        # Test session start
        session_result = await mcp_agent.start_session("test-session-002")
        print(f"✅ Session started: {session_result['session_id']}")
        
        # Test cleanup
        await mcp_agent.cleanup()
        print("✅ Playwright MCP Agent cleaned up")
        
    except Exception as e:
        print(f"❌ Playwright MCP Agent test failed: {e}")


async def main():
    """Main test function"""
    print("🚀 Starting Agent System Tests\n")
    
    await test_agent_factory()
    await test_agent_creation()
    
    print("\n✨ Tests completed!")


if __name__ == "__main__":
    asyncio.run(main())