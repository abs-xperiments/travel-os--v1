// TripOS service worker — deliberately tiny. Its job is PWA installability plus snappy
// static assets; it does NOT try to make an offline chatbot (the product needs the network).
// Strategy: cache-first for /static/*, network-first (with a graceful fallback) for pages.
const CACHE = 'tripos-v1';
const STATIC_ASSETS = [
  '/static/manifest.webmanifest',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(STATIC_ASSETS)));
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET') return;           // never touch POSTs (chat, auth)
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(event.request).then((hit) => hit || fetch(event.request))
    );
  }
  // Pages and the SSE stream go straight to the network — freshness over offline here.
});
