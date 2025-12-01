importScripts('https://cdn.onesignal.com/sdks/OneSignalSDK.js');

self.addEventListener('install', function(event) {
  self.skipWaiting && self.skipWaiting();
});

self.addEventListener('activate', function(event) {
  self.clients && self.clients.claim && self.clients.claim();
});
