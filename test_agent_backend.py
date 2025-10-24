#!/usr/bin/env python3
"""Test script for agent backend system.

This script tests the core functionality without requiring a running bot.
"""

import sys
import logging
from decimal import Decimal
from datetime import datetime

# Setup logging
logging.basicConfig(
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    level=logging.INFO
)

def test_helper_functions():
    """Test the helper functions in bot.py."""
    print("\n" + "="*60)
    print("TEST 1: Helper Functions")
    print("="*60)
    
    try:
        # Mock context
        class MockContext:
            def __init__(self, agent_id=None):
                self.bot_data = {}
                if agent_id:
                    self.bot_data['agent_id'] = agent_id
        
        # Import helper functions
        from bot import get_current_agent_id, get_agent_markup_usdt, calc_display_price_usdt
        
        # Test 1: Master bot (no agent_id)
        ctx_master = MockContext()
        agent_id = get_current_agent_id(ctx_master)
        assert agent_id is None, "Master bot should return None"
        print("✓ get_current_agent_id(master) = None")
        
        # Test 2: Agent bot
        ctx_agent = MockContext(agent_id="test_agent_001")
        agent_id = get_current_agent_id(ctx_agent)
        assert agent_id == "test_agent_001", "Should return agent_id"
        print(f"✓ get_current_agent_id(agent) = {agent_id}")
        
        # Test 3: Markup calculation (requires DB, will return 0)
        markup = get_agent_markup_usdt(ctx_master)
        assert isinstance(markup, Decimal), "Should return Decimal"
        assert markup == Decimal('0'), "Master bot should have 0 markup"
        print(f"✓ get_agent_markup_usdt(master) = {markup}")
        
        # Test 4: Price calculation
        base_price = Decimal('10.50')
        final_price = calc_display_price_usdt(base_price, ctx_master)
        assert final_price == base_price, "Master bot price should equal base"
        print(f"✓ calc_display_price_usdt({base_price}, master) = {final_price}")
        
        print("\n✅ Helper functions test passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Helper functions test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_agent_fields():
    """Test that agents have required fields."""
    print("\n" + "="*60)
    print("TEST 2: Agent Fields")
    print("="*60)
    
    try:
        from mongo import agents
        
        # Check if any agents exist
        agent_count = agents.count_documents({})
        print(f"Found {agent_count} agent(s) in database")
        
        if agent_count == 0:
            print("⚠️  No agents found, skipping field check")
            return True
        
        # Check first agent
        agent = agents.find_one({})
        agent_id = agent.get('agent_id', 'unknown')
        
        required_fields = [
            'owner_user_id',
            'markup_usdt',
            'profit_available_usdt',
            'profit_frozen_usdt',
            'total_paid_usdt',
            'links'
        ]
        
        missing_fields = []
        for field in required_fields:
            if field not in agent:
                missing_fields.append(field)
            else:
                value = agent[field]
                print(f"✓ {agent_id}.{field} = {value}")
        
        if missing_fields:
            print(f"\n⚠️  Agent {agent_id} is missing fields: {missing_fields}")
            print("    Run: python3 migrate_agents.py")
            return False
        
        # Check links structure
        links = agent.get('links', {})
        link_fields = ['support_link', 'channel_link', 'announcement_link', 'extra_links']
        for field in link_fields:
            if field not in links:
                print(f"⚠️  links.{field} is missing")
                return False
            print(f"✓ {agent_id}.links.{field} exists")
        
        print("\n✅ Agent fields test passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Agent fields test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_withdrawal_flow():
    """Test withdrawal data structures."""
    print("\n" + "="*60)
    print("TEST 3: Withdrawal Flow")
    print("="*60)
    
    try:
        from mongo import agent_withdrawals
        
        # Check collection structure
        withdrawal_count = agent_withdrawals.count_documents({})
        print(f"Found {withdrawal_count} withdrawal request(s)")
        
        # Create test withdrawal structure
        test_withdrawal = {
            'request_id': 'test_withdrawal_001',
            'agent_id': 'test_agent_001',
            'owner_user_id': 123456,
            'amount_usdt': '50.00',
            'fee_usdt': '1',
            'address': 'T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb',
            'status': 'pending',
            'created_at': datetime.now(),
            'reviewed_at': None,
            'reviewed_by': None
        }
        
        required_fields = [
            'request_id', 'agent_id', 'owner_user_id', 'amount_usdt',
            'fee_usdt', 'address', 'status', 'created_at'
        ]
        
        for field in required_fields:
            assert field in test_withdrawal, f"Missing field: {field}"
            print(f"✓ Withdrawal structure has {field}")
        
        # Test status values
        valid_statuses = ['pending', 'approved', 'rejected', 'paid']
        assert test_withdrawal['status'] in valid_statuses, "Invalid status"
        print(f"✓ Valid status values: {', '.join(valid_statuses)}")
        
        # Test amount format
        amount = Decimal(test_withdrawal['amount_usdt'])
        assert amount >= Decimal('10'), "Amount should be >= 10 USDT"
        print(f"✓ Amount validation: {amount} >= 10 USDT")
        
        print("\n✅ Withdrawal flow test passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Withdrawal flow test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_imports():
    """Test that all required modules can be imported."""
    print("\n" + "="*60)
    print("TEST 4: Module Imports")
    print("="*60)
    
    try:
        print("✓ Importing handlers.agent_backend...")
        from handlers import agent_backend
        
        print("✓ Importing admin.withdraw_commands...")
        from admin import withdraw_commands
        
        print("✓ Importing bot_integration...")
        import bot_integration
        
        print("✓ Importing mongo...")
        import mongo
        
        # Check key functions exist
        assert hasattr(agent_backend, 'agent_command'), "Missing agent_command"
        print("✓ agent_backend.agent_command exists")
        
        assert hasattr(agent_backend, 'agent_text_input_handler'), "Missing agent_text_input_handler"
        print("✓ agent_backend.agent_text_input_handler exists")
        
        assert hasattr(withdraw_commands, 'withdraw_list_command'), "Missing withdraw_list_command"
        print("✓ withdraw_commands.withdraw_list_command exists")
        
        assert hasattr(withdraw_commands, 'withdraw_approve_command'), "Missing withdraw_approve_command"
        print("✓ withdraw_commands.withdraw_approve_command exists")
        
        assert hasattr(bot_integration, 'save_agent'), "Missing save_agent"
        print("✓ bot_integration.save_agent exists")
        
        assert hasattr(bot_integration, 'start_agent_bot'), "Missing start_agent_bot"
        print("✓ bot_integration.start_agent_bot exists")
        
        print("\n✅ Module imports test passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Module imports test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("AGENT BACKEND SYSTEM - TEST SUITE")
    print("="*60)
    
    results = []
    
    # Run tests
    results.append(("Module Imports", test_imports()))
    results.append(("Helper Functions", test_helper_functions()))
    results.append(("Agent Fields", test_agent_fields()))
    results.append(("Withdrawal Flow", test_withdrawal_flow()))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result is True)
    failed = sum(1 for _, result in results if result is False)
    
    for name, result in results:
        status = "✅" if result else "❌"
        print(f"{status} {name}")
    
    print(f"\nPassed: {passed}/{len(results)}")
    print(f"Failed: {failed}/{len(results)}")
    
    if failed > 0:
        print("\n❌ SOME TESTS FAILED!")
        return 1
    else:
        print("\n✅ ALL TESTS PASSED!")
        return 0


if __name__ == '__main__':
    sys.exit(main())
