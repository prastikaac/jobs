@echo off
cd /d "%~dp0"

echo ============================================================
echo  Job Scheduler — Mon-Fri at 10:15, 13:30, 17:00
echo  Sat/Sun: Off
echo  If previous run is still active at next slot, waits for it
echo ============================================================
echo.

python schedule_jobs.py

echo.
echo Scheduler exited.
pause
