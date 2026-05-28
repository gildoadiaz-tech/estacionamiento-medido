const CACHE_NAME = 'estaciona-v2';
const urlsToCache = [
  '/login',
  '/conductor',
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
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
});

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
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
