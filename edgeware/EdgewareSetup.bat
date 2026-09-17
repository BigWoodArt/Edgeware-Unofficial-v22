@echo off

reg Query "HKLM\Hardware\Description\System\CentralProcessor\0" | find /i "x86" > NUL && set OS=32BIT || set OS=64BIT

:: cd to script's directory in case Windows sets the working directory to something else
cd /D "%~dp0"

echo +==============[ Welcome to Edgeware++ Setup~ ]==============+
echo Python version:
py --version
echo:
echo NOTE: Python versions older than 3.12 might have compatability issues.
echo If you are on one of these versions and experience issues with Edgeware++, try uninstalling them
echo and running this installer again. (or download it yourself if you know what you're doing!)
echo:

if not %errorlevel%==0 (
  echo Could not find Python.
  echo Downloading installer from python.org, please wait...

  if %OS%==32BIT powershell -Command "Invoke-WebRequest https://www.python.org/ftp/python/3.12.6/python-3.12.6.exe -OutFile pyinstaller.exe"
  if %OS%==64BIT powershell -Command "Invoke-WebRequest https://www.python.org/ftp/python/3.12.6/python-3.12.6-amd64.exe -OutFile pyinstaller.exe"

  echo Done downloading executable.
  echo Please complete installation through the installer before continuing, make sure "Add Python to PATH" is checked.
  start "Python Installer" "%CD%\pyinstaller.exe"
  pause

  py --version
  if not %errorlevel%==0 (
    echo Python still could not be found.
    pause
    exit
  )
)

:: Checked via Python's own sys.version_info tuple comparison rather than
:: parsing "Python X.Y.Z" text out of "py --version" - comparing a tuple of
:: ints is exact, where string-parsing version numbers in batch is fragile
:: (e.g. breaks across two-vs-three-digit minor versions).
py -c "import sys; exit(0 if sys.version_info >= (3, 12) else 1)"
if not %errorlevel%==0 (
  echo:
  echo ============================================================
  echo  WARNING: Your Python version is older than 3.12.
  echo  Edgeware++ may not work correctly on this version.
  echo ============================================================
  echo:
  powershell -Command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show('Your installed Python version is older than 3.12, which Edgeware++ may not work correctly on. You can continue anyway, but if you run into problems, consider uninstalling your current Python version and running this installer again to get a supported one.', 'Edgeware++ Setup - Python Version Warning', 'OK', 'Warning')"
)

echo pip version:
py -m pip --version
if not %errorlevel%==0 (
  echo Could not find pip.
  echo Installing pip with ensurepip...
  py -m ensurepip --upgrade

  py -m pip --version
  if not %errorlevel%==0 (
    echo pip still could not be found.
    pause
    exit
  )
)

echo Installing requirements...
py -m pip install -r requirements.txt
if not %errorlevel%==0 (
  echo Failed to install requirements.
  powershell -Command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show('Installing Edgeware++''s required Python packages failed. Check the command window for the actual pip error above, then try running this installer again.', 'Edgeware++ Setup - Install Failed', 'OK', 'Error')"
  pause
  exit
)

if not exist data\libmpv-2.dll (
  echo Installing libmpv...
  if not exist data mkdir data
  if not exist data\7z.exe powershell -Command "Invoke-WebRequest https://7-zip.org/a/7zr.exe -OutFile data\7z.exe"
  if not exist data\mpv.7z (
    if %OS%==32BIT powershell -Command "Invoke-WebRequest https://sourceforge.net/projects/mpv-player-windows/files/libmpv/mpv-dev-i686-20250420-git-3600c71.7z/download -UserAgent 'Wget' -OutFile data\mpv.7z"
    if %OS%==64BIT powershell -Command "Invoke-WebRequest https://sourceforge.net/projects/mpv-player-windows/files/libmpv/mpv-dev-x86_64-20250420-git-3600c71.7z/download -UserAgent 'Wget' -OutFile data\mpv.7z"
  )
  data\7z.exe e data\mpv.7z -odata libmpv-2.dll

  if not exist data\libmpv-2.dll (
    echo Failed to install libmpv.
    powershell -Command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show('Downloading or extracting libmpv (needed for video/audio playback) failed. Check the command window above for details, then try running this installer again.', 'Edgeware++ Setup - Install Failed', 'OK', 'Error')"
    pause
    exit
  )
)

call :makePyw "CONFIG" "config"
call :makePyw "MAIN" "edgeware"
call :makePyw "PANIC" "panic"
goto run

:makePyw
if exist %~2.pyw goto :eof
(
  @echo import subprocess
  @echo import sys
  @echo from src.paths import Process
  @echo subprocess.run^([sys.executable, Process.%~1]^)
) > %~2.pyw
goto :eof

:run
echo Edgeware++ is ready, and will now start the config file for you.
echo:
echo For first time users, here are the files you'll want to run to use Edgeware++ in the future:
echo config.pyw: runs the config window which allows changing Edgeware++ settings
echo edgeware.pyw: starts Edgeware++ with the config settings you have saved
echo panic.pyw: kills Edgeware++ and all currently spawned popups
pause
start "Edgeware++ Config" "%CD%/config.pyw"
exit
