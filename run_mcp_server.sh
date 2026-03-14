#!/bin/bash
# Orpheus MCP Server Wrapper
# Automatically activates virtual environment, installs dependencies if needed, and runs MCP server

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Path to virtual environment
VENV_PATH="${SCRIPT_DIR}/.venv"

# Function to check if requirements are installed
check_requirements() {
    local python_cmd="$1"
    local missing=0
    
    # Check for critical packages
    if ! $python_cmd -c "import mcp" 2>/dev/null; then
        missing=1
    fi
    if ! $python_cmd -c "import fastapi" 2>/dev/null; then
        missing=1
    fi
    if ! $python_cmd -c "import torch" 2>/dev/null; then
        missing=1
    fi
    if ! $python_cmd -c "import numpy" 2>/dev/null; then
        missing=1
    fi
    
    return $missing
}

# Check if virtual environment exists
if [ ! -d "$VENV_PATH" ]; then
    echo "Virtual environment not found. Creating one with Python 3.11..."
    
    # Try to find Python 3.11
    PYTHON_CMD=""
    if command -v python3.11 &> /dev/null; then
        PYTHON_CMD="python3.11"
    elif command -v python3 &> /dev/null && python3 --version | grep -q "3.11"; then
        PYTHON_CMD="python3"
    else
        echo "Error: Python 3.11 not found. Please install Python 3.11." >&2
        echo "On macOS: brew install python@3.11" >&2
        exit 1
    fi
    
    # Create virtual environment
    $PYTHON_CMD -m venv "$VENV_PATH"
    if [ $? -ne 0 ]; then
        echo "Error: Failed to create virtual environment" >&2
        exit 1
    fi
    echo "✓ Virtual environment created"
fi

# Activate virtual environment
source "${VENV_PATH}/bin/activate"

# Check if activation succeeded
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Error: Failed to activate virtual environment" >&2
    exit 1
fi

# Check if requirements need to be installed
if ! check_requirements "${VENV_PATH}/bin/python"; then
    echo "Installing/updating requirements..."
    
    # Upgrade pip and install build tools first
    pip install --upgrade pip setuptools wheel
    
    # Install requirements
    if [ -f "${SCRIPT_DIR}/requirements.txt" ]; then
        pip install -r "${SCRIPT_DIR}/requirements.txt"
        if [ $? -ne 0 ]; then
            echo "Error: Failed to install requirements" >&2
            exit 1
        fi
        echo "✓ Requirements installed"
    else
        echo "Error: requirements.txt not found" >&2
        exit 1
    fi
else
    echo "✓ Requirements already satisfied"
fi

# Run the MCP server with all arguments passed through
exec python "${SCRIPT_DIR}/mcp_server.py" "$@"
