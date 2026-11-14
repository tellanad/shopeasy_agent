@echo off
REM One-time setup for Windows. Run it from this folder:   setup.bat
REM It works whatever Python your computer has: uv downloads Python 3.12 just for this project.

cd /d "%~dp0"

echo 1/4  Getting uv (a fast Python installer)...
where uv >nul 2>nul
if errorlevel 1 if not exist "%USERPROFILE%\.local\bin\uv.exe" powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
set "UV=uv"
where uv >nul 2>nul
if errorlevel 1 set "UV=%USERPROFILE%\.local\bin\uv.exe"

echo 2/4  Creating .venv with Python 3.12...
"%UV%" venv --clear --python 3.12 .venv || goto :failed

echo 3/4  Installing the packages (a few minutes)...
"%UV%" pip install --python .venv\Scripts\python.exe -r requirements.txt || goto :failed

echo 4/4  Creating .env...
if not exist .env copy .env.example .env >nul

echo.
echo Setup done. Last step: open .env and paste your Groq key after GROQ_API_KEY=
echo Then run:   .venv\Scripts\python database.py   and   .venv\Scripts\python chat.py
goto :eof

:failed
echo Setup failed. Read the error above.
