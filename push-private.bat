@echo off
:: push-private.bat
:: Push EVERYTHING (including scraper/ and functions/) to the PRIVATE backup repo.
:: Uses a separate .git-private directory so it doesn't interfere with the public repo.

set GIT=git --git-dir=".git-private" --work-tree="."

echo ============================================
echo  PUSHING TO PRIVATE REPO (Full backup)
echo  Includes: scraper/ + functions/ + frontend
echo ============================================

:: Check if private repo is initialized
if not exist ".git-private" (
    echo ERROR: Private repo not set up yet!
    echo Run setup-private-repo.bat first.
    pause
    exit /b 1
)

:: Stage everything including scraper/ and functions/ (force past .gitignore)
%GIT% add -A
%GIT% add -f scraper/ functions/
%GIT% status --short

set /p MSG="Commit message (or press Enter for auto): "
if "%MSG%"=="" (
    for /f "tokens=*" %%i in ('powershell -command "Get-Date -Format \"yyyy-MM-dd HH:mm\""') do set TIMESTAMP=%%i
    set MSG=Backup %TIMESTAMP%
)

%GIT% commit -m "%MSG%"
%GIT% push private master

echo.
echo Done! Full backup pushed to private repo (includes scraper + functions).
pause
