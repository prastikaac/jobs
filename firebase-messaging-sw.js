// /firebase-messaging-sw.js

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
    icon: '/firebase-logo.png' // Optional: your app icon path
  };

  self.registration.showNotification(notificationTitle, notificationOptions);
});
