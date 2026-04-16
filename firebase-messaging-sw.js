importScripts('https://www.gstatic.com/firebasejs/10.12.2/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.12.2/firebase-messaging-compat.js');

firebase.initializeApp({
  apiKey: "AIzaSyAstAXkwifJ-ukfZKSXiLG_l9iNwg4tPw4",
  authDomain: "findjobsinfinland-3c061.firebaseapp.com",
  projectId: "findjobsinfinland-3c061",
  storageBucket: "findjobsinfinland-3c061.appspot.com",
  messagingSenderId: "575437446165",
  appId: "1:575437446165:web:51922bc01fd291b09b821c"
});

const messaging = firebase.messaging();

// (Optional) Activate the service worker immediately
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', () => self.clients.claim());

// Handle notification click — open the appropriate URL
self.addEventListener('notificationclick', function (event) {
  event.notification.close();

  // Try to get the URL from the notification data
  const data = event.notification.data || {};
  // FCM wraps data inside FCM_MSG for background messages
  const fcmData = data.FCM_MSG ? data.FCM_MSG.data : data;
  let targetUrl = fcmData.url || fcmData.jobLink || '/newjobs';

  // Fix for local Live Server testing: Add .html extension locally for clean URLs
  if (self.location.hostname === 'localhost' || self.location.hostname === '127.0.0.1') {
    if (targetUrl.startsWith('/newjobs') && !targetUrl.includes('.html')) {
      targetUrl = targetUrl.replace('/newjobs', '/newjobs.html');
    }
  }

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (clientList) {
      // Focus an existing tab that already has the target URL open
      for (var i = 0; i < clientList.length; i++) {
        var client = clientList[i];
        if (client.url === targetUrl && 'focus' in client) {
          return client.focus();
        }
      }
      // Otherwise open a new tab
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
    })
  );
});
