@echo off
cd /d "%~dp0"

py -c "import yaml, PIL, filetype, voluptuous, pyffmpeg" >nul 2>&1
if errorlevel 1 (
    echo Installing required Python packages - first run only, may take a minute...
    py -m pip install -r requirements.txt
)

echo Starting Edgeware++ Advanced Pack Builder...
REM pyw = windowless; startup errors go to startup_error.log.
start "" pyw edgeware_pack_builder_gui.pyw 2>"%~dp0startup_error.log"
