@echo off
:: setup-private-repo.bat
:: Run this ONCE to connect your private GitHub repo for full backup.
::
:: BEFORE RUNNING:
:: 1. Go to github.com → New Repository
:: 2. Name it: jobs-finland-private  (set to PRIVATE)
:: 3. Do NOT initialize with README
:: 4. Copy the repo URL (e.g. https://github.com/prastikaac/jobs-finland-private.git)
:: 5. Run this script and paste the URL when prompted

echo ============================================
echo  SETUP: Private Backup Repo (Run Once)
echo ============================================
echo.
echo You need a PRIVATE GitHub repo URL.
echo Example: https://github.com/prastikaac/jobs-finland-private.git
echo.
set /p REPO_URL="Paste your private GitHub repo URL: "

if "%REPO_URL%"=="" (
    echo ERROR: No URL provided. Exiting.
    pause
    exit /b 1
)

set GIT=git --git-dir=".git-private" --work-tree="."

echo.
echo Initializing private git directory...
%GIT% init
%GIT% remote add private %REPO_URL%

echo.
echo Staging all files (including scraper/ and functions/)...
%GIT% add -A
%GIT% add -f scraper/ functions/

echo.
echo Making initial commit...
%GIT% commit -m "Initial full backup (scraper + functions + frontend)"

echo.
echo Pushing to private repo...
%GIT% push -u private main

echo.
echo ============================================
echo  Setup complete!
echo  From now on, use:
echo    push-private.bat  → full backup (scraper + functions)
echo    push-public.bat   → frontend only (safe for public)
echo ============================================
pause
