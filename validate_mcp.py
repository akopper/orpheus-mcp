#!/usr/bin/env python3
"""
Simple syntax and structure validation for MCP server
Does not require dependencies to be installed
"""

import ast
import sys
from pathlib import Path


def validate_python_syntax(filepath):
    """Validate Python file syntax"""
    try:
        with open(filepath, "r") as f:
            source = f.read()
        ast.parse(source)
        print(f"✓ {filepath} - Syntax valid")
        return True
    except SyntaxError as e:
        print(f"✗ {filepath} - Syntax error: {e}")
        return False


def check_imports(filepath, required_imports):
    """Check if required imports are present"""
    with open(filepath, "r") as f:
        source = f.read()

    tree = ast.parse(source)
    imports = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module)

    missing = []
    for imp in required_imports:
        if imp not in imports:
            missing.append(imp)

    if missing:
        print(f"⚠ {filepath} - Missing imports: {', '.join(missing)}")
        return False
    else:
        print(f"✓ {filepath} - All required imports present")
        return True


def check_function_definitions(filepath, required_functions):
    """Check if required functions are defined"""
    with open(filepath, "r") as f:
        source = f.read()

    tree = ast.parse(source)
    functions = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            functions.add(node.name)
        elif isinstance(node, ast.AsyncFunctionDef):
            functions.add(node.name)

    missing = []
    for func in required_functions:
        if func not in functions:
            missing.append(func)

    if missing:
        print(f"⚠ {filepath} - Missing functions: {', '.join(missing)}")
        return False
    else:
        print(f"✓ {filepath} - All required functions present")
        return True


def main():
    print("\n" + "=" * 60)
    print("Orpheus MCP Server Validation")
    print("=" * 60 + "\n")

    # Files to validate
    files = [
        "mcp_server.py",
        "test_mcp_server.py",
    ]

    all_passed = True

    for filepath in files:
        if not Path(filepath).exists():
            print(f"✗ {filepath} - File not found")
            all_passed = False
            continue

        # Syntax validation
        if not validate_python_syntax(filepath):
            all_passed = False
            continue

    print("\n" + "-" * 60)
    print("MCP Server Structure Check")
    print("-" * 60)

    # Check mcp_server.py structure
    mcp_functions = [
        "get_config",
        "estimate_tokens",
        "handle_generate_speech",
        "handle_list_voices",
        "handle_get_voice_info",
        "handle_estimate_tokens",
        "list_tools",
        "main",
    ]

    if not check_function_definitions("mcp_server.py", mcp_functions):
        all_passed = False

    # Check classes
    with open("mcp_server.py", "r") as f:
        source = f.read()
    tree = ast.parse(source)
    classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]

    required_classes = ["ServerConfig", "LlamaServerManager"]
    for cls in required_classes:
        if cls in classes:
            print(f"✓ Class {cls} defined")
        else:
            print(f"✗ Class {cls} not found")
            all_passed = False

    print("\n" + "-" * 60)
    print("Test File Structure Check")
    print("-" * 60)

    # Check test file structure
    test_classes = [
        "TestServerConfig",
        "TestEstimateTokens",
        "TestLlamaServerManager",
        "TestToolHandlers",
        "TestToolDefinitions",
        "TestIntegration",
    ]

    with open("test_mcp_server.py", "r") as f:
        source = f.read()
    tree = ast.parse(source)
    defined_classes = [
        node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
    ]

    for cls in test_classes:
        if cls in defined_classes:
            print(f"✓ Test class {cls} defined")
        else:
            print(f"✗ Test class {cls} not found")
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("✓ All validation checks passed!")
        print("=" * 60 + "\n")
        return 0
    else:
        print("✗ Some validation checks failed")
        print("=" * 60 + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
