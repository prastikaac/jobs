# add-notification-system-parallel.ps1
# Injects notification popup CSS, header bell icon, popup HTML, and JS into all HTML files in parallel.
# Excludes: index.html, 404.html, jobs_table.html, translator.html,
#           App\nointernet.html, scraper\category_debug.html, scraper\offline_manual_category_changer.html
# Skips hidden/system directories (.git, .github, .vscode, etc.)

$root = "c:\Users\Ac\Documents\Programming\HTML CSS JS\JobsInFinland"

# Excluded files (relative paths from root, using backslash)
$excludeList = @(
    "index.html",
    "404.html",
    "jobs_table.html",
    "translator.html",
    "App\nointernet.html",
    "scraper\category_debug.html",
    "scraper\offline_manual_category_changer.html"
)

# ── CSS link to inject into <head> ──
$cssLink = '<link href="/css/notification-popup.css" rel="stylesheet"/>'

# ── Header notification icon HTML (bell + count badge) ──
$headerNotifIcon = @'

                  <li>
<div id="notification-icon" style=" margin-right: 35px;">
<svg class="bi bi-bell" fill="currentColor" height="16" viewbox="0 0 16 16" width="16" xmlns="http://www.w3.org/2000/svg">
<path d="M8 16a2 2 0 0 0 2-2H6a2 2 0 0 0 2 2M8 1.918l-.797.161A4 4 0 0 0 4 6c0 .628-.134 2.197-.459 3.742-.16.767-.376 1.566-.663 2.258h10.244c-.287-.692-.502-1.49-.663-2.258C12.134 8.197 12 6.628 12 6a4 4 0 0 0-3.203-3.92zM14.22 12c.223.447.481.801.78 1H1c.299-.199.557-.553.78-1C2.68 10.2 3 6.88 3 6c0-2.42 1.72-4.44 4.005-4.901a1 1 0 1 1 1.99 0A5 5 0 0 1 13 6c0 .88.32 4.2 1.22 6">
</path>
</svg>
<span id="notification-count">
                        0
                      </span>
</div>
<div class="notification-outer-div" id="notifications-outer-div">
</div>
<div id="notifications-container">
</div>
</li>
'@

# ── Notification popup HTML containers ──
$popupHtml = @'
<!-- ═══ Notification Popup System (containers only — content injected by JS) ═══ -->
<div id="np-overlay"></div>
<div aria-label="Notifications" id="np-popup" role="dialog">
<div id="np-header">
<div id="np-header-left">
<h2>Notifications</h2>
<span id="np-badge">0</span>
</div>
<button aria-label="Close notifications" id="np-close-btn">✕</button>
</div>
<div id="np-list">
<!-- Notification items injected by notification-popup.js -->
</div>
</div>
<div aria-label="Notification detail" id="np-detail" role="dialog">
<div id="nd-header">
<button aria-label="Back to notifications" id="nd-back-btn">←</button>
<p id="nd-header-title">Notification</p>
<button aria-label="Close" id="nd-close-btn">✕</button>
</div>
<div id="nd-body">
<div id="nd-img-large"><img alt="" id="nd-img" src=""/></div>
<h3 id="nd-title"></h3>
<p id="nd-date"></p>
<hr id="nd-divider"/>
<p id="nd-full-desc"></p>
<a href="#" id="nd-apply-btn" rel="noopener noreferrer" target="_blank">
<svg fill="none" height="16" stroke="currentColor" stroke-width="2.5" viewbox="0 0 24 24" width="16" xmlns="http://www.w3.org/2000/svg"><path d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" stroke-linecap="round" stroke-linejoin="round"></path></svg>
        Apply Now
      </a>
</div>
</div>
<!-- ═══ End Notification Popup System ═══ -->
'@

# ── JS script tag ──
$jsScript = '<script src="/js/notification-popup.js" type="module"></script>'

# Helper to check if a path should be skipped
function ShouldSkipDirectory($dirName) {
    return $dirName.StartsWith(".") -or $dirName -eq "__pycache__" -or $dirName.StartsWith("xQ7m")
}

# Recursively get all HTML files, skipping ignored directories
function Get-HtmlFiles($dir) {
    $files = [System.IO.Directory]::GetFiles($dir, "*.html")
    foreach ($file in $files) {
        $file
    }
    
    $subdirs = [System.IO.Directory]::GetDirectories($dir)
    foreach ($subdir in $subdirs) {
        $dirName = [System.IO.Path]::GetFileName($subdir)
        if (-not (ShouldSkipDirectory $dirName)) {
            Get-HtmlFiles $subdir
        }
    }
}

Write-Host "Scanning directory structure..."
$allHtmlFiles = @(Get-HtmlFiles $root)

# Filter exclusions
$filteredFiles = New-Object System.Collections.Generic.List[string]
$skippedExcluded = 0

foreach ($filePath in $allHtmlFiles) {
    $relativePath = $filePath.Substring($root.Length + 1)
    $isExcluded = $false
    foreach ($exc in $excludeList) {
        if ($relativePath -eq $exc) {
            $isExcluded = $true
            break
        }
    }
    if ($isExcluded) {
        $skippedExcluded++
    } else {
        $filteredFiles.Add($filePath)
    }
}

$filesArray = $filteredFiles.ToArray()
$totalFiles = $filesArray.Length
Write-Host "Found $totalFiles HTML files to process (excluded $skippedExcluded files)."

# Compile the C# helper class
$csharpCode = @'
using System;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using System.Collections.Concurrent;

public class NotificationInjector {
    public static int ModifiedCount = 0;
    public static int ErrorCount = 0;
    public static ConcurrentBag<string> Errors = new ConcurrentBag<string>();

    public static void Inject(string[] files, string cssLink, string bellIcon, string jsScript, string popupHtml) {
        ModifiedCount = 0;
        ErrorCount = 0;
        Errors = new ConcurrentBag<string>();

        Parallel.ForEach(files, filePath => {
            try {
                string content = File.ReadAllText(filePath);
                bool modified = false;

                // 1. Check CSS link
                if (!content.Contains("notification-popup.css")) {
                    if (content.Contains("</head>")) {
                        content = content.Replace("</head>", "  " + cssLink + "\r\n</head>");
                        modified = true;
                    }
                }

                // 2. Check notification bell icon
                if (!content.Contains("notification-icon")) {
                    if (content.Contains("<ul class=\"headIc\">")) {
                        content = content.Replace("<ul class=\"headIc\">", "<ul class=\"headIc\">" + bellIcon);
                        modified = true;
                    }
                }

                // 3. Check JS and Popup HTML
                if (!content.Contains("notification-popup.js")) {
                    if (content.Contains("</body>")) {
                        string insertBlock = jsScript + "\r\n" + popupHtml + "\r\n";
                        content = content.Replace("</body>", insertBlock + "</body>");
                        modified = true;
                    }
                }

                if (modified) {
                    File.WriteAllText(filePath, content);
                    Interlocked.Increment(ref ModifiedCount);
                }
            } catch (Exception ex) {
                Interlocked.Increment(ref ErrorCount);
                Errors.Add(filePath + " : " + ex.Message);
            }
        });
    }
}
'@

Write-Host "Compiling fast parallel injector..."
Add-Type -TypeDefinition $csharpCode

Write-Host "Executing injection on $totalFiles files in parallel..."
$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

[NotificationInjector]::Inject($filesArray, $cssLink, $headerNotifIcon, $jsScript, $popupHtml)

$stopwatch.Stop()
$elapsed = $stopwatch.Elapsed.TotalSeconds

$modified = [NotificationInjector]::ModifiedCount
$errorsCount = [NotificationInjector]::ErrorCount

Write-Host ""
Write-Host "=== NOTIFICATION SYSTEM INJECTION COMPLETE ==="
Write-Host "Total files scanned:    $totalFiles"
Write-Host "Files modified:         $modified"
Write-Host "Errors encountered:     $errorsCount"
Write-Host "Execution time:         $([Math]::Round($elapsed, 2)) seconds"

if ($errorsCount -gt 0) {
    Write-Host ""
    Write-Host "=== ERRORS ==="
    foreach ($err in [NotificationInjector]::Errors) {
        Write-Host "  $err"
    }
}
