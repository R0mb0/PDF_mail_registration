@echo off
setlocal
REM Builds a standalone Windows .exe with PyInstaller -- runs on any Windows
REM PC with no Python installation required on the target machine.
REM
REM Run this from the app\ folder, inside the same virtual environment used
REM for `pip install -r requirements.txt` (see README.md "Setup"). PyInstaller
REM inspects the environment's own installed packages to decide what to
REM bundle, so it must run from that same venv, not a bare system Python.

echo Using interpreter:
where python
echo.

pip install -r requirements-build.txt
if errorlevel 1 (
    echo.
    echo ERROR: pip install failed -- see above. Aborting.
    exit /b 1
)

REM "python -m PyInstaller" instead of the bare "pyinstaller" command: pip
REM installs the pyinstaller.exe launcher into that interpreter's own
REM Scripts folder, which is only automatically on PATH inside an activated
REM venv -- if you're on a system/user Python instead, that folder is
REM usually NOT on PATH and the bare command fails with "not recognized".
REM Invoking it as a module sidesteps that entirely: it always runs through
REM whichever "python" pip just installed into, regardless of PATH.
python -m PyInstaller --noconfirm --clean --windowed --onefile ^
  --name RegistrationManager ^
  --icon Logo.ico ^
  --add-data "Logo.ico;." ^
  --add-data "translations;translations" ^
  main.py
if errorlevel 1 (
    echo.
    echo ERROR: PyInstaller build failed -- see above. dist\RegistrationManager.exe was NOT created.
    exit /b 1
)

echo.
echo Done. Executable: dist\RegistrationManager.exe
echo Copy that single file anywhere and run it -- Python is not required on
echo the machine that runs it.
