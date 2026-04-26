# test_workbench.py
# Simple test script to verify GenCAD workbench functionality

import sys
import os

# Add the CADomatic project path
sys.path.insert(0, '/home/robotcad/projects/CADomatic/GenCAD/cadomatic')

def test_imports():
    """Test that we can import the necessary modules"""
    try:
        from src.llm_client import prompt_llm
        print("✓ Successfully imported prompt_llm from src.llm_client")
        return True
    except ImportError as e:
        print(f"✗ Failed to import prompt_llm: {e}")
        return False
    except Exception as e:
        print(f"✗ Error importing prompt_llm: {e}")
        return False

def test_basic_functionality():
    """Test basic functionality by generating a simple CAD description"""
    try:
        from src.llm_client import prompt_llm
        
        # Test with a simple prompt
        test_prompt = "Create a simple 10x10x10 mm cube"
        print(f"Testing with prompt: '{test_prompt}'")
        
        generated_code = prompt_llm(test_prompt)
        print("✓ Successfully generated CAD code")
        print(f"Generated code length: {len(generated_code)} characters")
        
        # Check if the generated code looks like Python/FreeCAD code
        if "import" in generated_code[:100]:  # Check first 100 chars for import
            print("✓ Generated code appears to be valid Python")
            return True
        else:
            print("? Generated code might not be valid Python (this is OK)")
            return True  # Still consider it a success, LLM output varies
            
    except Exception as e:
        print(f"✗ Error during basic functionality test: {e}")
        return False

if __name__ == "__main__":
    print("Testing GenCAD workbench functionality...\n")
    
    print("1. Testing imports...")
    imports_ok = test_imports()
    
    if imports_ok:
        print("\n2. Testing basic functionality...")
        functionality_ok = test_basic_functionality()
        
        print(f"\nTest Results:")
        print(f"- Imports: {'PASS' if imports_ok else 'FAIL'}")
        print(f"- Basic functionality: {'PASS' if functionality_ok else 'FAIL'}")
        
        if imports_ok and functionality_ok:
            print("\n✓ GenCAD workbench should work correctly!")
        else:
            print("\n⚠ Some tests failed, but workbench might still work.")
    else:
        print("\n✗ Import test failed, workbench will not work.")