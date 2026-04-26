# test_qwen3_support.py
# Test script to verify Qwen3 via OpenRouter support

import os
import sys
sys.path.insert(0, '/home/robotcad/projects/CADomatic/GenCAD/cadomatic')

# Mock environment to use Qwen3 OpenRouter
os.environ['USE_QWEN3_OPENROUTER'] = 'True'
os.environ['OPENROUTER_API_KEY'] = 'test_key'  # This will fail but will test the code path

print("Testing Qwen3 OpenRouter support...")

try:
    # Import the module to check if it loads correctly with Qwen3 settings
    from src.load_environment import load_env
    print(f"USE_QWEN3_OPENROUTER: {load_env.USE_QWEN3_OPENROUTER}")
    print(f"OPENROUTER_API_KEY: {'Set' if load_env.OPENROUTER_API_KEY else 'Not set'}")
    
    # Check if llm_client can be imported with Qwen3 settings
    import importlib
    import src.llm_client
    importlib.reload(src.llm_client)  # Reload to pick up environment changes
    
    print("✓ Module loaded successfully with Qwen3 settings")
    
    # Test the Qwen3 API function directly
    from src.llm_client import call_qwen3_openrouter_api
    result = call_qwen3_openrouter_api("test prompt", "test context")
    print(f"Qwen3 API call result: {result}")
    
except Exception as e:
    print(f"Expected error during API call (due to missing API key): {type(e).__name__}: {e}")

print("Qwen3 OpenRouter support test completed.")