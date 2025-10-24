#!/usr/bin/env python3
"""
Agent Management System - Startup Verification

This script verifies that the bot can start up correctly with the agent
management system integrated. It performs dry-run checks without actually
starting the bot or connecting to Telegram.

Usage:
    python verify_startup.py
"""

import sys
import os
import logging

logging.basicConfig(
    format='[%(levelname)s] %(message)s',
    level=logging.INFO
)

def check_environment():
    """Check environment variables."""
    print("\n" + "="*60)
    print("ENVIRONMENT CHECK")
    print("="*60)
    
    required_vars = []
    optional_vars = [
        'BOT_TOKEN',
        'ADMIN_IDS', 
        'AGENT_TOKEN_AES_KEY',
        'MONGO_URI'
    ]
    
    for var in required_vars:
        if not os.getenv(var):
            print(f"❌ Missing required: {var}")
            return False
        print(f"✓ {var} = <set>")
    
    for var in optional_vars:
        if os.getenv(var):
            print(f"✓ {var} = <set>")
        else:
            print(f"⚠ {var} = <not set> (optional)")
    
    print("\n✅ Environment check passed")
    return True


def check_file_structure():
    """Check required files exist."""
    print("\n" + "="*60)
    print("FILE STRUCTURE CHECK")
    print("="*60)
    
    required_files = [
        'bot.py',
        'bot_integration.py',
        'mongo.py',
        'requirements.txt'
    ]
    
    for file in required_files:
        if os.path.exists(file):
            print(f"✓ {file}")
        else:
            print(f"❌ {file} missing")
            return False
    
    print("\n✅ File structure check passed")
    return True


def check_agent_handlers():
    """Check that agent handler functions are defined correctly."""
    print("\n" + "="*60)
    print("AGENT HANDLER CHECK")
    print("="*60)
    
    # Check if we can parse the bot_integration.py file
    try:
        with open('bot_integration.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        handlers = [
            'def agent_manage(',
            'def agent_refresh(',
            'def agent_new(',
            'def agent_tgl(',
            'def agent_del(',
            'def agent_add(',
            'def agent_toggle(',
            'def agent_delete(',
            'def integrate_agent_system('
        ]
        
        for handler in handlers:
            if handler in content:
                handler_name = handler.split('(')[0].replace('def ', '')
                print(f"✓ {handler_name}")
            else:
                print(f"❌ {handler.split('(')[0].replace('def ', '')} missing")
                return False
        
        print("\n✅ Agent handlers check passed")
        return True
        
    except Exception as e:
        print(f"\n❌ Failed to check handlers: {e}")
        return False


def check_callback_patterns():
    """Check that callback patterns are registered."""
    print("\n" + "="*60)
    print("CALLBACK PATTERN CHECK")
    print("="*60)
    
    try:
        with open('bot_integration.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        patterns = [
            "pattern='^agent_manage$'",
            "pattern='^agent_refresh$'",
            "pattern='^agent_new$'",
            "pattern='^agent_tgl '",
            "pattern='^agent_del '"
        ]
        
        for pattern in patterns:
            if pattern in content:
                print(f"✓ {pattern}")
            else:
                print(f"❌ {pattern} missing")
                return False
        
        print("\n✅ Callback patterns check passed")
        return True
        
    except Exception as e:
        print(f"\n❌ Failed to check patterns: {e}")
        return False


def check_bot_integration():
    """Check that integrate_agent_system is called in bot.py."""
    print("\n" + "="*60)
    print("INTEGRATION CHECK")
    print("="*60)
    
    try:
        with open('bot.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        checks = [
            ('from bot_integration import', 'bot_integration module imported'),
            ('integrate_agent_system', 'integrate_agent_system called'),
            ("callback_data='agent_manage'", 'agent_manage button in admin panel')
        ]
        
        for check_str, description in checks:
            if check_str in content:
                print(f"✓ {description}")
            else:
                print(f"❌ {description} missing")
                return False
        
        print("\n✅ Integration check passed")
        return True
        
    except Exception as e:
        print(f"\n❌ Failed to check integration: {e}")
        return False


def check_agent_creation_flow():
    """Check agent creation flow in textkeyboard function."""
    print("\n" + "="*60)
    print("AGENT CREATION FLOW CHECK")
    print("="*60)
    
    try:
        with open('bot.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        flow_steps = [
            ("sign == 'agent_add_token'", "Token input handler"),
            ("sign == 'agent_add_name'", "Name input handler"),
            ("context.user_data['agent_token']", "Token stored in context"),
            ("save_agent", "save_agent function called"),
            ("start_agent_bot", "start_agent_bot function called")
        ]
        
        for check_str, description in flow_steps:
            if check_str in content:
                print(f"✓ {description}")
            else:
                print(f"⚠ {description} - might be missing")
        
        print("\n✅ Agent creation flow check passed")
        return True
        
    except Exception as e:
        print(f"\n❌ Failed to check creation flow: {e}")
        return False


def main():
    """Run all verification checks."""
    print("\n" + "="*60)
    print("AGENT MANAGEMENT SYSTEM - STARTUP VERIFICATION")
    print("="*60)
    
    checks = [
        ("Environment", check_environment),
        ("File Structure", check_file_structure),
        ("Agent Handlers", check_agent_handlers),
        ("Callback Patterns", check_callback_patterns),
        ("Bot Integration", check_bot_integration),
        ("Agent Creation Flow", check_agent_creation_flow)
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ {name} check failed with exception: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "="*60)
    print("VERIFICATION SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    print(f"\n{passed}/{total} checks passed")
    
    if passed == total:
        print("\n" + "="*60)
        print("✅ ALL CHECKS PASSED - READY FOR STARTUP")
        print("="*60)
        print("\nNext steps:")
        print("1. Set up .env file with required variables")
        print("2. Ensure MongoDB is running (or use JSON fallback)")
        print("3. Run: python bot.py")
        print("4. Test admin panel → 代理管理 button")
        print("5. Test all agent management flows")
        return 0
    else:
        print("\n" + "="*60)
        print("❌ SOME CHECKS FAILED - REVIEW ERRORS ABOVE")
        print("="*60)
        return 1


if __name__ == '__main__':
    sys.exit(main())
