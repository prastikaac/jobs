@echo off
:: clean-private-repo-history.bat
:: ======================================================================
:: ONE-TIME FIX: removes 197 MB log/data objects from .git-private history
:: that caused GitHub to reject pushes with "exceeds 100 MB file size limit".
::
:: What this does:
::   1. Gets the private remote URL from the existing .git-private config
::   2. Removes the .git-private bare repo entirely (drops bloated history)
::   3. Re-initialises a fresh bare repo with no history
::   4. Adds current files (excluding logs) as a single "fresh start" commit
::   5. Force-pushes to GitHub (--force overwrites the remote history)
::
:: SAFE TO RUN: your actual source files are untouched. Only git history is reset.
:: ======================================================================

set REPO=.
set PRIV=.git-private
set GIT=git --git-dir="%PRIV%" --work-tree="%REPO%"

echo ============================================================
echo  CLEAN PRIVATE REPO HISTORY (one-time large-file purge)
echo ============================================================

:: ── 1. Grab the remote URL before we delete anything ─────────────────────────
for /f "tokens=*" %%U in ('git --git-dir="%PRIV%" remote get-url private 2^>nul') do set REMOTE_URL=%%U
if "%REMOTE_URL%"=="" (
    echo ERROR: Could not read remote URL from .git-private.
    echo Make sure .git-private exists and has a "private" remote configured.
    pause
    exit /b 1
)
echo Remote URL: %REMOTE_URL%

:: ── 2. Confirm ───────────────────────────────────────────────────────────────
echo.
echo This will RESET the private repo history (force-push a single clean commit).
echo The remote history on GitHub will be overwritten. Your FILES are safe.
echo.
set /p CONFIRM="Type YES to continue, anything else to cancel: "
if /i NOT "%CONFIRM%"=="YES" (
    echo Cancelled.
    pause
    exit /b 0
)

:: ── 3. Remove old bare repo ───────────────────────────────────────────────────
echo.
echo [1/5] Removing old .git-private directory...
rmdir /s /q "%PRIV%"
if exist "%PRIV%" (
    echo ERROR: Could not remove .git-private. Close any programs using it and try again.
    pause
    exit /b 1
)
echo       Done.

:: ── 4. Re-initialise a fresh bare repo ───────────────────────────────────────
echo [2/5] Initialising fresh .git-private...
git init --bare "%PRIV%"
git --git-dir="%PRIV%" remote add private "%REMOTE_URL%"
git --git-dir="%PRIV%" config core.compression 9
git --git-dir="%PRIV%" config http.postBuffer 524288000
git --git-dir="%PRIV%" config http.lowSpeedLimit 1000
git --git-dir="%PRIV%" config http.lowSpeedTime 300
echo       Done.

:: ── 5. Copy exclude rules ─────────────────────────────────────────────────────
echo [3/5] Restoring info/exclude rules...
copy /y "%~dp0.git-private-exclude-backup.txt" "%PRIV%\info\exclude" >nul 2>&1
:: If no backup exists, write the rules directly
if not exist "%PRIV%\info\exclude" (
    (
        echo # Node.js dependencies
        echo node_modules/
        echo functions/node_modules/
        echo scraper/node_modules/
        echo **/node_modules/
        echo # Python caches
        echo __pycache__/
        echo **/__pycache__/
        echo *.pyc
        echo # Log files - can grow to 100s of MB
        echo *.log
        echo pipeline.log
        echo pipeline-errors.txt
        echo scraper/pipeline.log
        echo scraper/scraper.log
        echo scraper/category_checker.log
    ) > "%PRIV%\info\exclude"
)
echo       Done.

:: ── 6. Stage and commit current state (no logs, no secrets) ──────────────────
echo [4/5] Staging current files for fresh commit...
%GIT% add -A
%GIT% add -f scraper/ functions/

:: In a fresh repo, 'reset HEAD' doesn't work (no prior commit).
:: Use 'rm --cached' instead to un-stage unwanted files from the index.
for %%F in (
    scraper\serviceAccountKey.json
    pipeline.log
    pipeline-errors.txt
    scraper\pipeline.log
    scraper\scraper.log
    scraper\category_checker.log
) do %GIT% rm --cached "%%F" 2>nul
%GIT% rm -r --cached scraper/__pycache__/ 2>nul
%GIT% rm -r --cached functions/node_modules/ 2>nul
%GIT% rm -r --cached scraper/node_modules/ 2>nul

for /f "tokens=*" %%i in ('powershell -command "Get-Date -Format \"yyyy-MM-dd HH:mm\""') do set TIMESTAMP=%%i
%GIT% commit -m "Fresh backup - history reset to purge large objects [%TIMESTAMP%]"
if errorlevel 1 (
    echo ERROR: Commit failed. Check status above.
    pause
    exit /b 1
)
echo       Done.

:: ── 7. Force-push to GitHub ───────────────────────────────────────────────────
echo [5/5] Force-pushing to GitHub (this overwrites remote history)...
%GIT% push private main --force
if errorlevel 1 (
    echo ERROR: Push failed. Check credentials and try running push-private.bat.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  SUCCESS! Private repo history has been reset.
echo  Large objects (197 MB logs) have been purged.
echo  Future pushes will be fast and within GitHub limits.
echo ============================================================
pause

