const CACHE_NAME = 'estaciona-v3';
const TILE_CACHE = 'map-tiles-v1';
const urlsToCache = [
  '/login',
  '/conductor',
  '/conductor/buscar',
  '/conductor/mapa',
  '/conductor/historial',
  '/permisionario',
  '/admin',
];

self.addEventListener('install', event => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(urlsToCache))
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME && k !== TILE_CACHE).map(k => caches.delete(k)))
    )
  );
});

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // Cache OSM map tiles: cache-first (they never change)
  if (url.hostname.endsWith('tile.openstreetmap.org')) {
    event.respondWith(
      caches.open(TILE_CACHE).then(cache =>
        cache.match(event.request).then(cached => {
          if (cached) return cached;
          return fetch(event.request).then(res => {
            if (res.ok) cache.put(event.request, res.clone());
            return res;
          }).catch(() => new Response('', {status: 408}));
        })
      )
    );
    return;
  }

  // No cachear HTML ni llamadas API
  if (url.pathname.endsWith('.html') || url.pathname.startsWith('/api/') || url.pathname === '/' || url.pathname === '/conductor' || url.pathname === '/conductor/mapa') {
    event.respondWith(fetch(event.request).catch(() => caches.match(event.request)));
    return;
  }
  event.respondWith(
    caches.match(event.request).then(response =>
      response || fetch(event.request)
    )
  );
});
