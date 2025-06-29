importScripts('https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js');
importScripts('https://www.gstatic.com/firebasejs/10.12.2/firebase-messaging.js');

firebase.initializeApp({
  apiKey: "AIzaSyAstAXkwifJ-ukfZKSXiLG_l9iNwg4tPw4",
  authDomain: "findjobsinfinland-3c061.firebaseapp.com",
  projectId: "findjobsinfinland-3c061",
  storageBucket: "findjobsinfinland-3c061.appspot.com",
  messagingSenderId: "575437446165",
  appId: "1:575437446165:web:51922bc01fd291b09b821c"
});

const messaging = firebase.messaging();

messaging.onBackgroundMessage((payload) => {
  console.log('[firebase-messaging-sw.js] Received background message ', payload);

  const notificationTitle = payload.notification.title || 'New Notification';
  const notificationOptions = {
    body: payload.notification.body || '',
    icon: '/images/icon.png', // Optional app icon
    image: payload.notification.image || undefined, // Show job image if available
    data: {
      jobLink: payload.data?.jobLink || null // Save job URL for click event
    }
  };

  self.registration.showNotification(notificationTitle, notificationOptions);
});

// Handle notification click to open the job URL
self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  const jobUrl = event.notification.data?.jobLink;
  if (jobUrl) {
    event.waitUntil(
      clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
        for (const client of clientList) {
          // If the job URL is already open, focus that tab
          if (client.url === jobUrl && 'focus' in client) {
            return client.focus();
          }
        }
        // Otherwise, open a new tab with the job URL
        if (clients.openWindow) {
          return clients.openWindow(jobUrl);
        }
      })
    );
  }
});
