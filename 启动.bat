@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem Requires pythonw on PATH (tick "Add python to PATH" when installing Python).
rem If not found, replace "pythonw" on the next line with the full path to pythonw.exe.
start "" pythonw main.py
