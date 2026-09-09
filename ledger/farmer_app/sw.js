// sw.js — makes the app shell (this form) load even with zero network,
// so a farmer can open it, fill it in, and queue a batch entirely offline.
// The actual DATA syncing is handled separately in app.js's queue logic —
// this service worker only caches the static files (HTML/JS/CSS).

const CACHE_NAME = "gi-batch-capture-v1";
const APP_SHELL = ["./", "index.html", "app.js", "manifest.json"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", (event) => {
  // Only intercept requests for our own app shell files — never intercept
  // API calls to farmer_api.py, those need to hit the real network (or
  // genuinely fail, so app.js's queue logic knows to keep the record queued).
  if (event.request.url.includes("/farmer/")) return;

  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request))
  );
});
