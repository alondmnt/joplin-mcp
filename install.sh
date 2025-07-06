#!/bin/bash

# Joplin MCP Server Installation Script (Unix/Linux/macOS)
# This script helps users install and configure the Joplin MCP server

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Function to print colored output
print_colored() {
    echo -e "${2}${1}${NC}"
}

print_header() {
    echo
    print_colored "============================================================" "$CYAN"
    print_colored "  $1" "$CYAN$BOLD"
    print_colored "============================================================" "$CYAN"
}

print_step() {
    echo
    print_colored "🔧 $1" "$BLUE$BOLD"
}

print_success() {
    print_colored "✅ $1" "$GREEN"
}

print_error() {
    print_colored "❌ $1" "$RED"
}

print_warning() {
    print_colored "⚠️  $1" "$YELLOW"
}

print_info() {
    print_colored "ℹ️  $1" "$BLUE"
}

# Check if we're in the right directory
if [ ! -f "install.py" ]; then
    print_error "install.py not found. Please run this script from the joplin-mcp directory."
    exit 1
fi

print_header "Joplin MCP Server Installation"

# Check Python availability
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    print_error "Python 3 is required but not found in PATH."
    print_info "Please install Python 3 and try again."
    exit 1
fi

print_info "Using Python: $(which $PYTHON_CMD)"

# Check if this is a development install or pip install
if [ -f "pyproject.toml" ] || [ -f "setup.py" ]; then
    print_step "Installing package"
    
    # Check if virtual environment exists
    if [ ! -d "venv" ] && [ -z "$VIRTUAL_ENV" ]; then
        print_warning "No virtual environment detected."
        print_info "It's recommended to use a virtual environment to avoid conflicts."
        
        read -p "Create a virtual environment? (y/n) [recommended]: " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_step "Creating virtual environment"
            $PYTHON_CMD -m venv venv
            source venv/bin/activate
            print_success "Virtual environment created and activated"
        fi
    fi
    
    # Install the package in development mode
    print_info "Installing joplin-mcp package..."
    $PYTHON_CMD -m pip install -e .
    print_success "Package installed"
else
    print_info "For pip install: pip install joplin-mcp"
    print_info "Then run: python -m joplin_mcp.install"
fi

# Run the main installation script
print_step "Running installation script"
$PYTHON_CMD install.py

print_success "Installation script completed!"
print_info "If you encounter any issues, please check the troubleshooting guide." 