@echo off
cd /d "%~dp0"

echo ============================================================
echo  Job Scheduler — Mon-Fri at 10:00, 13:30, 17:00
echo  Sat/Sun: Off
echo  If previous run is still active, next run is queued
echo ============================================================
echo.

python schedule_jobs.py

echo.
echo Scheduler exited.
pause
