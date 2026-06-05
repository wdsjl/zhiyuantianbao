@echo off
cd /d C:\zhiyuantianbao\server
python -m uvicorn main:app --host 127.0.0.1 --port 8001
