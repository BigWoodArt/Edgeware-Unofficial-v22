@echo off

reg Query "HKLM\Hardware\Description\System\CentralProcessor\0" | find /i "x86" > NUL && set OS=32BIT || set OS=64BIT

:: cd to script's directory in case Windows sets the working directory to something else
cd /D "%~dp0"

echo +==============[ Welcome to Edgeware++ Setup~ ]==============+
echo Looking for Python 3.12 or newer...

:: Every candidate is actually run, so a broken entry (for example an uninstalled
:: Python that the "py" launcher still lists) is skipped instead of stopping setup.
set PY=
set PYW=
call :tryPython "py -3.12"
if not defined PY call :tryPython "py"
if not defined PY call :tryPython "python"
if defined PY goto havePython

echo No working Python 3.12 or newer was found.
echo Downloading the Python 3.12 installer from python.org, please wait...
if %OS%==32BIT powershell -Command "Invoke-WebRequest https://www.python.org/ftp/python/3.12.6/python-3.12.6.exe -OutFile pyinstaller.exe"
if %OS%==64BIT powershell -Command "Invoke-WebRequest https://www.python.org/ftp/python/3.12.6/python-3.12.6-amd64.exe -OutFile pyinstaller.exe"
if not exist pyinstaller.exe goto pythonFailed
echo Installing Python 3.12 for your user account. This takes a minute...
start /wait "" "%CD%\pyinstaller.exe" /passive InstallAllUsers=0 PrependPath=1 Include_launcher=1
del pyinstaller.exe
call :tryPython "py -3.12"
:: A fresh per-user install is not on this window's PATH yet, so also try its usual location
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" call :tryPythonExe "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PY goto pythonFailed

:havePython
if "%PY%"=="py -3.12" set PYW=pyw -3.12
echo Using: %PY%
%PY% --version
echo:
goto pipCheck

:tryPython
%~1 -c "import sys; exit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>&1
if %errorlevel%==0 set PY=%~1
goto :eof

:tryPythonExe
"%~1" -c "import sys; exit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>&1
if %errorlevel%==0 set PY="%~1"
if %errorlevel%==0 set PYW="%~dp1pythonw.exe"
goto :eof

:pythonFailed
echo Could not set up Python 3.12.
powershell -Command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show('Edgeware++ could not find or install Python 3.12. Please install Python 3.12 from python.org (tick Add Python to PATH), then run this installer again. If Python was installed before, it may be broken: uninstall it from Windows Settings > Apps first.', 'Edgeware++ Setup - Python Not Found', 'OK', 'Error')"
pause
exit

:pipCheck
echo pip version:
%PY% -m pip --version
if not %errorlevel%==0 (
  echo Could not find pip.
  echo Installing pip with ensurepip...
  %PY% -m ensurepip --upgrade

  %PY% -m pip --version
  if not %errorlevel%==0 (
    echo pip still could not be found.
    pause
    exit
  )
)

echo Installing requirements...
%PY% -m pip install -r requirements.txt
if %errorlevel%==0 goto requirementsDone

:: Some packages (the winrt-* ones from desktop-notifier) have no prebuilt files
:: for very new Python versions and fail to build. Retry with Python 3.12.
echo:
echo Install failed on this Python. Trying Python 3.12 instead...
if "%PY%"=="py -3.12" goto requirementsFailed
set PY=
set PYW=
call :tryPython "py -3.12"
if defined PY goto have312
echo Python 3.12 not found. Downloading it, please wait...
if %OS%==32BIT powershell -Command "Invoke-WebRequest https://www.python.org/ftp/python/3.12.6/python-3.12.6.exe -OutFile py312.exe"
if %OS%==64BIT powershell -Command "Invoke-WebRequest https://www.python.org/ftp/python/3.12.6/python-3.12.6-amd64.exe -OutFile py312.exe"
if exist py312.exe start /wait "" "%CD%\py312.exe" /passive InstallAllUsers=0 PrependPath=1 Include_launcher=1
call :tryPython "py -3.12"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" call :tryPythonExe "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PY goto requirementsFailed

:have312
%PY% -m pip install -r requirements.txt
if not %errorlevel%==0 goto requirementsFailed
if "%PY%"=="py -3.12" set PYW=pyw -3.12
goto requirementsDone

:requirementsFailed
echo Failed to install requirements.
powershell -Command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show('Installing Edgeware++''s required Python packages failed. Check the command window for the actual pip error above. If you use a very new Python (3.13 or newer), install Python 3.12 from python.org and run this installer again.', 'Edgeware++ Setup - Install Failed', 'OK', 'Error')"
pause
exit

:requirementsDone
if exist py312.exe del py312.exe

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
if defined PYW (
  start "Edgeware++ Config" %PYW% "%CD%/config.pyw"
) else (
  start "Edgeware++ Config" "%CD%/config.pyw"
)
exit
