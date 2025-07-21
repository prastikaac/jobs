importScripts('https://www.gstatic.com/firebasejs/10.12.2/firebase-app-compat.js'); 
importScripts('https://www.gstatic.com/firebasejs/10.12.2/firebase-messaging-compat.js');

firebase.initializeApp({
  apiKey:            "AIzaSyAstAXkwifJ-ukfZKSXiLG_l9iNwg4tPw4",
  authDomain:        "findjobsinfinland-3c061.firebaseapp.com",
  projectId:         "findjobsinfinland-3c061",
  storageBucket:     "findjobsinfinland-3c061.appspot.com",
  messagingSenderId: "575437446165",
  appId:             "1:575437446165:web:51922bc01fd291b09b821c"
});

const messaging = firebase.messaging();

// (Optional) Activate the service worker immediately
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', () => self.clients.claim());


