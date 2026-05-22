@echo off
:loop
set WHISPER_MODEL=small
set WHISPER_DEVICE=cuda
set WHISPER_COMPUTE=float16
"%~dp0venv\Scripts\python.exe" "%~dp0transcribe_server.py"
timeout /t 3 /nobreak >nul
goto loop
