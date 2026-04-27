# Android App Features

This document outlines the custom native features currently implemented in the **Jobs In Finland** Android app (built with Capacitor).

## 1. Core Web Integration
*   **Capacitor Wrapped**: Acts as a native shell around the live website (`https://findjobsinfinland.fi/`).
*   **Immersive Display**: Handles system window insets to draw edge-to-edge, utilizing the full screen while respecting status and navigation bars.
*   **Splash Screen Management**: Automatically and instantly hides the native splash screen only after the web content has fully loaded to ensure a seamless transition without flashes.

## 2. Advanced Offline & Error Handling
*   **Pre-flight Network Checks**: Intercepts requests before they are sent; if offline, it instantly serves a local offline page instead of showing the default Chromium "no internet" dinosaur screen.
*   **Custom Error Pages**: Catches HTTP errors, DNS failures, and SSL errors, routing users to a friendly local `error.html` asset.
*   **Auto-Recovery Polling**: When on the offline page, the app natively polls the network every 3 seconds. It performs a silent background ping (`HEAD` request) to verify true connectivity and automatically reloads the last visited page when the connection is restored.
*   **Smart History Traversal**: Intervenes in the WebView history stack so the native hardware "Back" button skips over error pages and correctly returns the user to their last *successful* page, preventing them from getting stuck in an error loop.

## 3. Link Handling & Social Deep Linking
*   **In-App Browser**: External links are intercepted via injected JavaScript and opened in a native in-app browser (Custom Tabs) in fullscreen mode, keeping the user inside the app environment.
*   **Native Social Apps**: Specifically detects links to **LinkedIn**, **Facebook**, and **Instagram**. It uses native Android Intents to attempt opening these links directly in their respective native apps. If the app isn't installed, it falls back to the browser gracefully.

## 4. UI & UX Enhancements
*   **Native Swipe-to-Refresh**: Implements Android's native `SwipeRefreshLayout` allowing users to pull down to refresh the page.
*   **Dynamic Theming**: The WebView background and the Swipe-to-Refresh spinner colors automatically adapt to the user's system-level Dark or Light mode settings to prevent jarring flashes.
*   **Double Back to Exit**: Prevents accidental app closures by requiring the user to tap the "Back" button twice within 2 seconds when on the root page.

## 5. Storage & State Persistence
*   **Forced Cookie Persistence**: Ensures cookies (like session data and cookie consent) are actively flushed to disk when the app is backgrounded.
*   **DOM Storage Enabled**: Explicitly enables LocalStorage and Database storage to support modern web app features and preferences tracking.
