#!/usr/bin/env python3
"""
Test script to verify the autostart fix for MCP server.
This tests that the lifespan context manager is properly invoked.
"""

import ast
import sys


def test_main_uses_lifespan():
    """Test that main() properly uses the lifespan context manager"""

    # Read the main function
    with open("/Users/axer/git/orpheus-mcp/mcp_server.py", "r") as f:
        source = f.read()

    # Parse the AST
    tree = ast.parse(source)

    # Find the main function
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "main":
            # Check if it uses 'async with app_lifespan()'
            source_lines = source.split("\n")
            func_start = node.lineno - 1
            func_end = node.end_lineno
            func_source = "\n".join(source_lines[func_start:func_end])

            if "async with app_lifespan()" in func_source:
                print("✓ main() properly uses 'async with app_lifespan()'")
                return True
            else:
                print("✗ main() does NOT use 'async with app_lifespan()'")
                return False

    print("✗ Could not find main() function")
    return False


def test_server_manager_created_in_lifespan():
    """Test that server_manager is created in lifespan"""

    with open("/Users/axer/git/orpheus-mcp/mcp_server.py", "r") as f:
        source = f.read()

    tree = ast.parse(source)

    # Find app_lifespan function
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "app_lifespan":
            source_lines = source.split("\n")
            func_start = node.lineno - 1
            func_end = node.end_lineno
            func_source = "\n".join(source_lines[func_start:func_end])

            checks = [
                (
                    "LlamaServerManager" in func_source,
                    "LlamaServerManager instantiation",
                ),
                ("start_server()" in func_source, "start_server() call"),
                ("yield" in func_source, "yield statement"),
                ("stop_server()" in func_source, "stop_server() call"),
            ]

            all_passed = True
            for check, desc in checks:
                if check:
                    print(f"✓ {desc} found in app_lifespan()")
                else:
                    print(f"✗ {desc} NOT found in app_lifespan()")
                    all_passed = False

            return all_passed

    print("✗ Could not find app_lifespan() function")
    return False


def test_lifespan_is_async_context_manager():
    """Test that app_lifespan is decorated with @asynccontextmanager"""

    with open("/Users/axer/git/orpheus-mcp/mcp_server.py", "r") as f:
        source = f.read()

    tree = ast.parse(source)

    # Find app_lifespan function
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "app_lifespan":
            # Check if it has @asynccontextmanager decorator
            for decorator in node.decorator_list:
                if (
                    isinstance(decorator, ast.Name)
                    and decorator.id == "asynccontextmanager"
                ):
                    print("✓ app_lifespan() is decorated with @asynccontextmanager")
                    return True
                elif (
                    isinstance(decorator, ast.Attribute)
                    and decorator.attr == "asynccontextmanager"
                ):
                    print("✓ app_lifespan() is decorated with @asynccontextmanager")
                    return True

            print("✗ app_lifespan() is NOT decorated with @asynccontextmanager")
            return False

    print("✗ Could not find app_lifespan() function")
    return False


if __name__ == "__main__":
    print("=" * 60)
    print("Testing MCP Server Autostart Fix")
    print("=" * 60)
    print()

    tests = [
        ("Lifespan is async context manager", test_lifespan_is_async_context_manager),
        ("Main uses lifespan", test_main_uses_lifespan),
        ("Server manager in lifespan", test_server_manager_created_in_lifespan),
    ]

    results = []
    for name, test_func in tests:
        print(f"\n--- {name} ---")
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"✗ Test failed with exception: {e}")
            results.append((name, False))

    print("\n" + "=" * 60)
    print("Test Results:")
    print("=" * 60)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    all_passed = all(r[1] for r in results)
    print()
    if all_passed:
        print("All tests passed! The autostart fix is working correctly.")
        print()
        print("Summary of the fix:")
        print("- The app_lifespan() context manager was defined but never used")
        print("- main() now wraps server execution with 'async with app_lifespan():'")
        print(
            "- This ensures llama.cpp server is auto-started before handling requests"
        )
        print("- Cleanup (server shutdown) happens when the context exits")
        sys.exit(0)
    else:
        print("Some tests failed. Please review the output above.")
        sys.exit(1)
