@echo off
cd /d "%~dp0"

echo Checking for required Python package (pyyaml)...
py -m pip show pyyaml >nul 2>&1
if errorlevel 1 (
    echo Installing pyyaml...
    py -m pip install pyyaml
)

echo Starting Edgeware++ Advanced Pack Builder...
py edgeware_pack_builder_gui.py

if errorlevel 1 (
    echo.
    echo The program closed with an error - see above.
    pause
)
