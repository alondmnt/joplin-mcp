@echo off
REM Joplin MCP Server Installation Script (Windows)
REM This script helps users install and configure the Joplin MCP server

setlocal enabledelayedexpansion

REM Color codes aren't easily supported in batch, so we'll use plain text
echo.
echo ============================================================
echo   Joplin MCP Server Installation (Windows)
echo ============================================================
echo.

REM Check if we're in the right directory
if not exist "install.py" (
    echo ERROR: install.py not found. Please run this script from the joplin-mcp directory.
    pause
    exit /b 1
)

REM Check Python availability
set "PYTHON_CMD="
where python >nul 2>&1
if %errorlevel% == 0 (
    set "PYTHON_CMD=python"
) else (
    where python3 >nul 2>&1
    if %errorlevel% == 0 (
        set "PYTHON_CMD=python3"
    ) else (
        echo ERROR: Python 3 is required but not found in PATH.
        echo Please install Python 3 from https://python.org and try again.
        pause
        exit /b 1
    )
)

echo INFO: Using Python: %PYTHON_CMD%

REM Check if this is a development install or pip install
if exist "pyproject.toml" (
    echo Installing package...
    
    REM Check if virtual environment exists
    if not exist "venv" (
        if "%VIRTUAL_ENV%" == "" (
            echo WARNING: No virtual environment detected.
            echo It's recommended to use a virtual environment to avoid conflicts.
            echo.
            set /p "CREATE_VENV=Create a virtual environment? (y/n) [recommended]: "
            if /i "!CREATE_VENV!" == "y" (
                echo Creating virtual environment...
                %PYTHON_CMD% -m venv venv
                call venv\Scripts\activate.bat
                echo SUCCESS: Virtual environment created and activated
            )
        )
    )
    
    REM Install the package in development mode
    echo Installing joplin-mcp package...
    %PYTHON_CMD% -m pip install -e .
    echo SUCCESS: Package installed
) else (
    echo For pip install: pip install joplin-mcp
    echo Then run: python -m joplin_mcp.install
)

REM Run the main installation script
echo.
echo Running installation script...
%PYTHON_CMD% install.py

echo.
echo Installation script completed!
echo If you encounter any issues, please check the troubleshooting guide.
pause 