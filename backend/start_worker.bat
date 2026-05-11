@echo off
cd /d %~dp0
call .venv\Scripts\activate
celery -A app.tasks.celery_app worker --loglevel=info --pool=solo
