@echo off
cd /d "%~dp0"
python -m streamlit run "%~dp0app\main.py" --server.port 8511 --server.baseUrlPath rework-dashboard --server.headless false
pause
