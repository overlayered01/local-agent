@echo off
setlocal
set "PYTHONPATH=%~dp0src;%PYTHONPATH%"
py -X utf8 -m local_agent %*
exit /b %ERRORLEVEL%
