// TripOS service worker — deliberately tiny. Its job is PWA installability plus snappy
// static assets; it does NOT try to make an offline chatbot (the product needs the network).
// Strategy: stale-while-revalidate for /static/* (assets update on the next visit after a
// deploy — bump CACHE on releases that change them), network for everything else.
const CACHE = 'tripos-v3';   // bumped: calendar-icon + dictation fixes must not serve stale
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
    // Stale-while-revalidate: serve the cached copy instantly, refresh it in the
    // background so a deploy's new theme/journal assets arrive by the next visit.
    event.respondWith(
      caches.open(CACHE).then(async (cache) => {
        const hit = await cache.match(event.request);
        const refresh = fetch(event.request)
          .then((res) => {
            if (res && res.ok) cache.put(event.request, res.clone());
            return res;
          })
          .catch(() => hit);
        return hit || refresh;
      })
    );
  }
  // Pages and the SSE stream go straight to the network — freshness over offline here.
});
