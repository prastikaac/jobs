# remove_ads.ps1 — Remove all Google AdSense, Ezoic, and anti-adblock scripts from HTML files
# Run from project root:  powershell -ExecutionPolicy Bypass -File scraper\remove_ads.ps1

$root = Split-Path $PSScriptRoot -Parent
$htmlFiles = Get-ChildItem $root -Filter "*.html" -Recurse | Where-Object { $_.FullName -notmatch "\\scraper\\" }

$totalFiles = 0
$totalCleaned = 0

foreach ($file in $htmlFiles) {
    $content = Get-Content $file.FullName -Raw -Encoding UTF8
    $original = $content

    # ── Pattern 1: AdSense script tag (1 or 2 lines) ──────────────────────────
    # <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-..."
    #   crossorigin="anonymous"></script>
    $content = $content -replace '(?s)\s*<script[^>]*src="https://pagead2\.googlesyndication\.com/pagead/js/adsbygoogle\.js\?client=[^"]*"[^>]*>\s*</script>\s*', "`n"

    # ── Pattern 2: Empty ad placeholder script ─────────────────────────────────
    # <script async src=""></script>
    $content = $content -replace '\s*<script\s+async\s+src=""\s*>\s*</script>\s*', "`n"

    # ── Pattern 3: Ezoic placeholder div + ezstandalone script ─────────────────
    # <div id="ezoic-pub-ad-placeholder-101">
    #   <script>
    #     ezstandalone.cmd.push(function () {
    #       ezstandalone.showAds(101);
    #     });
    #   </script>
    # </div>
    $content = $content -replace '(?s)\s*<div\s+id="ezoic-pub-ad-placeholder-\d+">\s*<script>\s*ezstandalone\.cmd\.push\(function\s*\(\)\s*\{[^}]*\}\);\s*</script>\s*</div>\s*', "`n"

    # ── Pattern 4: Obfuscated anti-adblock eval block (CDATA wrapped) ──────────
    # These are the large eval(function(p,l,u,s,f,d){...}) blocks wrapped in CDATA
    # They appear as: <script> /* or /*<![CDATA[*/ eval(function... </script>
    $content = $content -replace '(?s)\s*<script[^>]*>\s*/\*\s*<!\[CDATA\[\*/\s*eval\(function\s*\(p,\s*l,\s*u,\s*s,\s*f,\s*d\)\s*\{.*?\}\s*\)\s*;?\s*/\*\]\]>\*/\s*</script>\s*', "`n"

    # ── Pattern 5: Anti-adblock click tracker block (the antiBombSet block) ────
    # <script> /*<![CDATA[*/ !function(){ ... antiBombSet ... }() /*]]>*/ </script>
    $content = $content -replace '(?s)\s*<script[^>]*>\s*/\*\s*<!\[CDATA\[\*/\s*!\s*function\s*\(\)\s*\{[^}]*antiBombSet[^}]*\}[^<]*</script>\s*', "`n"

    # ── Pattern 6: adsenseAds config object inside larger scripts ───────────────
    # adsenseAds: { ... },  (multi-line object inside a larger script)
    $content = $content -replace '(?s)\s*adsenseAds:\s*\{[^}]*\},?\s*', "`n"

    # ── Pattern 7: Standalone ezoic/ezstandalone references ────────────────────
    $content = $content -replace '(?s)\s*<script[^>]*>\s*var\s+ezstandalone[^<]*</script>\s*', "`n"

    # Clean up excessive blank lines (more than 2 consecutive)
    $content = $content -replace '(\r?\n){4,}', "`n`n`n"

    if ($content -ne $original) {
        Set-Content -Path $file.FullName -Value $content -Encoding UTF8 -NoNewline
        $totalCleaned++
        Write-Host "  Cleaned: $($file.FullName -replace [regex]::Escape($root), '')"
    }
    $totalFiles++
}

Write-Host ""
Write-Host "Done! Scanned $totalFiles files, cleaned $totalCleaned files."
