const VERSION = 'v1.0.1';
const PRECACHE = `nocturne-precache-${VERSION}`;
const RUNTIME = 'nocturne-runtime';
const IMAGES = 'nocturne-images';
const MAX_IMAGES = 60;
const NAV_TIMEOUT_MS = 4000;

const CORE = [
  './',
  './index.html',
  './manifest.json',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/maskable-192.png',
  './icons/maskable-512.png',
  './icons/apple-touch-icon.png',
  './icons/favicon-32.png',
  './icons/favicon-16.png',
  './icons/favicon.ico',
];

const CDN_PRECACHE = [
  'https://tailwindcss.com',
  'https://googleapis.com',
  'https://cloudflare.com',
];

const CDN_HOSTS = new Set([
  '://tailwindcss.com',
  '://googleapis.com',
  '://gstatic.com',
  '://cloudflare.com',
]);
const IMAGE_HOSTS = new Set(['://unsplash.com']);

const OFFLINE_SVG =
  '<svg xmlns="http://w3.org" viewBox="0 0 400 300">' +
    '<rect width="400" height="300" fill="#121216"/>' +
    '<rect x="1" y="1" width="398" height="298" fill="none" stroke="#c5a059" stroke-opacity=".25"/>' +
    '<path d="M170 105h60l-30 45zM200 150v40m-22 0h44" fill="none" stroke="#c5a059" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>' +
    '<text x="200" y="232" fill="#6b7280" font-size="14" text-anchor="middle" font-family="sans-serif">離線中，圖片暫時無法顯示</text>' +
  '</svg>';

self.addEventListener('install', (event) => {
  event.waitUntil(
    (async () => {
      const pre = await caches.open(PRECACHE);
      await pre.addAll(CORE);
      const rt = await caches.open(RUNTIME);
      await Promise.allSettled(
        CDN_PRECACHE.map(async (url) => {
          const res = await fetchWithCorsFallback(url);
          if (isCacheable(res)) await rt.put(url, res);
        })
      );
    })()
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const keep = new Set([PRECACHE, RUNTIME, IMAGES]);
      const names = await caches.keys();
      await Promise.all(
        names
          .filter((n) => n.startsWith('nocturne-') && !keep.has(n))
          .map((n) => caches.delete(n))
      );
      if (self.registration.navigationPreload) {
        await self.registration.navigationPreload.disable().catch(() => {});
      }
      await self.clients.claim();
    })()
  );
});

self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') self.skipWaiting();
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.protocol !== 'http:' && url.protocol !== 'https:') return;

  if (req.mode === 'navigate') {
    event.respondWith(handleNavigation(req));
    return;
  }
  if (url.origin === self.location.origin) {
    event.respondWith(staleWhileRevalidate(event, req, PRECACHE, { ignoreSearch: true }));
    return;
  }
  if (IMAGE_HOSTS.has(url.hostname)) {
    event.respondWith(
      staleWhileRevalidate(event, req, IMAGES, { maxEntries: MAX_IMAGES, fallback: offlineImage })
    );
    return;
  }
  if (CDN_HOSTS.has(url.hostname)) {
    event.respondWith(staleWhileRevalidate(event, req, RUNTIME));
    return;
  }
});

function isCacheable(res) {
  return !!res && (res.ok || res.type === 'opaque');
}

async function fetchWithCorsFallback(url) {
  try {
    return await fetch(new Request(url, { mode: 'cors', credentials: 'omit' }));
  } catch (_) {
    return fetch(new Request(url, { mode: 'no-cors', credentials: 'omit' }));
  }
}

async function handleNavigation(req) {
  const indexUrl = new URL('./index.html', self.registration.scope).href;
  const cache = await caches.open(PRECACHE);
  try {
    const res = await Promise.race([
      fetch(req),
      new Promise((_, reject) => setTimeout(() => reject(new Error('timeout')), NAV_TIMEOUT_MS)),
    ]);
    if (res && res.ok) cache.put(indexUrl, res.clone());
    return res;
  } catch (_) {
    return (
      (await cache.match(indexUrl, { ignoreSearch: true })) ||
      new Response('目前離線，且尚未快取頁面。', {
        status: 503,
        headers: { 'Content-Type': 'text/plain; charset=utf-8' },
      })
    );
  }
}

function offlineImage() {
  return new Response(OFFLINE_SVG, {
    headers: { 'Content-Type': 'image/svg+xml', 'Cache-Control': 'no-store' },
  });
}

async function trimCache(cache, max) {
  const keys = await cache.keys();
  for (let i = 0; i < keys.length - max; i++) await cache.delete(keys[i]);
}

async function staleWhileRevalidate(event, req, cacheName, opts = {}) {
  const { ignoreSearch = false, maxEntries = 0, fallback = null } = opts;
  const cache = await caches.open(cacheName);
  const cached = await cache.match(req, { ignoreSearch });

  const update = (async () => {
    try {
      const sameOrigin = new URL(req.url).origin === self.location.origin;
      const res = sameOrigin ? await fetch(req) : await fetchWithCorsFallback(req.url);
      if (isCacheable(res)) {
        await cache.put(req, res.clone());
        if (maxEntries) await trimCache(cache, maxEntries);
      }
      return res;
    } catch (_) {
      return null;
    }
  })();

  if (cached) {
    event.waitUntil(update);
    return cached;
  }
  const fresh = await update;
  if (fresh) return fresh;
  if (fallback) return fallback();
  return Response.error();
}
