@echo off
:: push-public.bat
:: Push frontend-only changes to the PUBLIC GitHub repo (github.com/prastikaac/jobs)
:: scraper/ and functions/ are excluded via .gitignore automatically.

echo ============================================
echo  PUSHING TO PUBLIC REPO (Frontend only)
echo  github.com/prastikaac/jobs
echo ============================================

git add -A
git status --short

set /p MSG="Commit message: "
if "%MSG%"=="" set MSG=Update frontend

git commit -m "%MSG%"
git push origin main

echo.
echo Done! Public repo updated.
pause
