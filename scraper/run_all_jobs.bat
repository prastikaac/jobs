@echo off
cd /d "%~dp0"

echo [%DATE% %TIME%] Starting Job Scraper...
python run_scraper.py
if %ERRORLEVEL% NEQ 0 (
    echo [%DATE% %TIME%] Scraper failed! Aborting.
    exit /b %ERRORLEVEL%
)

echo [%DATE% %TIME%] Starting AI Pipeline and HTML Generation...
python run_pipeline.py
if %ERRORLEVEL% NEQ 0 (
    echo [%DATE% %TIME%] Pipeline failed! Aborting.
    exit /b %ERRORLEVEL%
)

echo [%DATE% %TIME%] All Scraping ^& Processing Complete.

REM ── Git: final catch-all commit + push (pipeline commits every 5 jobs already) ─
echo [%DATE% %TIME%] Final catch-all commit and push to GitHub...
cd /d "%~dp0.."

git add scraper/data/jobs.json scraper/data/rawjobs.json scraper/data/formatted_jobs_flat.json scraper/data/processing_state.json jobs/ sitemap-jobs.xml sitemap.xml
git commit -m "Auto-update jobs [final] [%DATE% %TIME%]"
if %ERRORLEVEL% NEQ 0 (
    echo [%DATE% %TIME%] Git commit: nothing new to commit (batched commits already pushed everything).
    exit /b 0
)

git push origin main
if %ERRORLEVEL% NEQ 0 (
    echo [%DATE% %TIME%] Git push failed! Check your connection or credentials.
    exit /b %ERRORLEVEL%
)

echo [%DATE% %TIME%] Successfully pushed to GitHub. Done!
