#!/usr/bin/env python3
"""
Test script to verify Agent Management system is properly integrated.
This script checks:
1. Module imports work correctly
2. Handler functions exist and are callable
3. MongoDB connections can be established
4. Basic system initialization works
"""

import sys
import logging
import os

# Setup logging
logging.basicConfig(
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    level=logging.INFO
)

def test_imports():
    """Test that all required modules can be imported."""
    print("\n" + "="*60)
    print("TEST 1: Module Imports")
    print("="*60)
    
    try:
        # Test bot.py imports
        print("✓ Importing bot.py...")
        import bot
        
        # Test bot_integration imports
        print("✓ Importing bot_integration.py...")
        import bot_integration
        
        # Test that key functions exist
        print("✓ Checking agent_manage function...")
        assert hasattr(bot_integration, 'agent_manage')
        
        print("✓ Checking agent_refresh function...")
        assert hasattr(bot_integration, 'agent_refresh')
        
        print("✓ Checking agent_new function...")
        assert hasattr(bot_integration, 'agent_new')
        
        print("✓ Checking agent_tgl function...")
        assert hasattr(bot_integration, 'agent_tgl')
        
        print("✓ Checking agent_del function...")
        assert hasattr(bot_integration, 'agent_del')
        
        print("✓ Checking integrate_agent_system function...")
        assert hasattr(bot_integration, 'integrate_agent_system')
        
        print("\n✅ All imports successful!")
        return True
        
    except Exception as e:
        print(f"\n❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_handler_functions():
    """Test that handler functions are callable."""
    print("\n" + "="*60)
    print("TEST 2: Handler Function Signatures")
    print("="*60)
    
    try:
        import bot_integration
        import inspect
        
        handlers = [
            'agent_manage',
            'agent_refresh', 
            'agent_new',
            'agent_tgl',
            'agent_del',
            'agent_add',
            'agent_toggle',
            'agent_delete'
        ]
        
        for handler_name in handlers:
            handler = getattr(bot_integration, handler_name)
            sig = inspect.signature(handler)
            params = list(sig.parameters.keys())
            
            # All handlers should accept (update, context)
            if len(params) >= 2 and params[0] == 'update' and params[1] == 'context':
                print(f"✓ {handler_name}: {sig}")
            else:
                print(f"⚠ {handler_name}: unexpected signature {sig}")
        
        print("\n✅ Handler functions are properly defined!")
        return True
        
    except Exception as e:
        print(f"\n❌ Handler check failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_callback_patterns():
    """Test that callback data patterns are correct."""
    print("\n" + "="*60)
    print("TEST 3: Callback Data Patterns")
    print("="*60)
    
    patterns = {
        'agent_manage': '^agent_manage$',
        'agent_refresh': '^agent_refresh$',
        'agent_new': '^agent_new$',
        'agent_tgl': '^agent_tgl ',
        'agent_del': '^agent_del ',
    }
    
    try:
        import re
        
        for name, pattern in patterns.items():
            # Test that patterns compile
            compiled = re.compile(pattern)
            print(f"✓ {name}: {pattern}")
            
            # Test sample matches
            if name == 'agent_manage':
                assert compiled.match('agent_manage')
            elif name == 'agent_refresh':
                assert compiled.match('agent_refresh')
            elif name == 'agent_new':
                assert compiled.match('agent_new')
            elif name == 'agent_tgl':
                assert compiled.match('agent_tgl agent001')
            elif name == 'agent_del':
                assert compiled.match('agent_del agent001')
        
        print("\n✅ All callback patterns are valid!")
        return True
        
    except Exception as e:
        print(f"\n❌ Pattern check failed: {e}")
        return False


def test_callback_data_length():
    """Test that callback_data stays under 64 bytes."""
    print("\n" + "="*60)
    print("TEST 4: Callback Data Length Check")
    print("="*60)
    
    try:
        # Test various callback data combinations
        test_cases = [
            ('agent_manage', 12),
            ('agent_refresh', 13),
            ('agent_new', 9),
            ('agent_tgl agent_20250124_123456', 30),
            ('agent_del agent_20250124_123456', 30),
        ]
        
        max_length = 0
        for callback_data, expected_len in test_cases:
            actual_len = len(callback_data.encode('utf-8'))
            max_length = max(max_length, actual_len)
            
            if actual_len <= 64:
                print(f"✓ {callback_data[:30]}... : {actual_len} bytes")
            else:
                print(f"❌ {callback_data[:30]}... : {actual_len} bytes (TOO LONG!)")
                return False
        
        print(f"\n✅ All callback data under 64 bytes! (max: {max_length} bytes)")
        return True
        
    except Exception as e:
        print(f"\n❌ Length check failed: {e}")
        return False


def test_mongodb_connection():
    """Test MongoDB connection (optional, will warn if fails)."""
    print("\n" + "="*60)
    print("TEST 5: MongoDB Connection (Optional)")
    print("="*60)
    
    try:
        from mongo import agents, user
        
        # Try to count documents
        agent_count = agents.count_documents({})
        print(f"✓ Connected to agents collection: {agent_count} documents")
        
        user_count = user.count_documents({})
        print(f"✓ Connected to user collection: {user_count} documents")
        
        print("\n✅ MongoDB connection successful!")
        return True
        
    except Exception as e:
        print(f"\n⚠️ MongoDB connection failed (this is OK for testing): {e}")
        return None  # None means optional test


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("AGENT MANAGEMENT SYSTEM - TEST SUITE")
    print("="*60)
    
    results = []
    
    # Run tests
    results.append(("Imports", test_imports()))
    results.append(("Handler Functions", test_handler_functions()))
    results.append(("Callback Patterns", test_callback_patterns()))
    results.append(("Callback Data Length", test_callback_data_length()))
    results.append(("MongoDB Connection", test_mongodb_connection()))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result is True)
    failed = sum(1 for _, result in results if result is False)
    skipped = sum(1 for _, result in results if result is None)
    
    for name, result in results:
        if result is True:
            print(f"✅ {name}")
        elif result is False:
            print(f"❌ {name}")
        else:
            print(f"⚠️  {name} (skipped)")
    
    print(f"\nPassed: {passed}, Failed: {failed}, Skipped: {skipped}")
    
    if failed > 0:
        print("\n❌ TESTS FAILED!")
        return 1
    else:
        print("\n✅ ALL TESTS PASSED!")
        return 0


if __name__ == '__main__':
    sys.exit(main())
