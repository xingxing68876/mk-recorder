@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem 默认用 PATH 里的 pythonw(装 Python 时勾选 Add to PATH 即可)。
rem 若提示找不到 pythonw,把下行的 pythonw 换成 pythonw.exe 的完整路径,例如:
rem start "" "<Python安装目录>\pythonw.exe" main.py
start "" pythonw main.py
