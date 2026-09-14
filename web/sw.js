const CACHE_NAME = 'sonometa-v2.1';
const ASSETS_TO_CACHE = [
  './',
  './index.html',
  './css/styles.css',
  './js/app.js',
  './js/auth.js',
  './js/dashboard.js',
  './js/supabase.js',
  './manifest.json'
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS_TO_CACHE))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
    )
  );
  self.clients.claim();
});

// Estrategia Stale-While-Revalidate
self.addEventListener('fetch', (e) => {
  // Ignorar peticiones a Supabase o CDN para no cachear datos mutables/tokens
  if (e.request.url.includes('supabase.co') || e.request.method !== 'GET') {
    return;
  }

  e.respondWith(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.match(e.request).then((cachedResponse) => {
        const fetchPromise = fetch(e.request)
          .then((networkResponse) => {
            if (networkResponse.status === 200) {
              cache.put(e.request, networkResponse.clone());
            }
            return networkResponse;
          })
          .catch(() => cachedResponse);

        return cachedResponse || fetchPromise;
      });
    })
  );
});