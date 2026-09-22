@echo off
setlocal
cd /d "%~dp0"
python scripts\stage3_binding_review_tool.py
if errorlevel 1 pause
