// Pegasus Phantom Menace — Service Worker (persistent daemon)
// Keeps the PWA alive in the background, caches assets, and auto-restarts the app.

const CACHE_NAME = "pegasus-v2-cache";
const ASSETS = [
  "/",
  "/index.html",
  "/favicon.svg",
  "/favicon-192.png",
  "/favicon-512.png",
  "/apple-touch-icon.png",
  "/manifest.webmanifest",
];

// Install: cache core assets
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS)).then(() => self.skipWaiting())
  );
});

// Activate: clean old caches, take control immediately
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// Fetch: network-first with cache fallback
self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  event.respondWith(
    fetch(req)
      .then((res) => {
        const copy = res.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(req, copy));
        return res;
      })
      .catch(() => caches.match(req).then((r) => r || caches.match("/")))
  );
});

// Background sync: keep running when app is closed
self.addEventListener("sync", (event) => {
  if (event.tag === "pegasus-keepalive") {
    event.waitUntil(
      (async () => {
        const clients = await self.clients.matchAll({ includeUncontrolled: true });
        clients.forEach((c) => c.postMessage({ type: "KEEPALIVE", ts: Date.now() }));
      })()
    );
  }
});

// Periodic background sync (where supported) — keeps daemon alive
self.addEventListener("periodicsync", (event) => {
  if (event.tag === "pegasus-daemon") {
    event.waitUntil(
      (async () => {
        const clients = await self.clients.matchAll({ includeUncontrolled: true });
        clients.forEach((c) => c.postMessage({ type: "DAEMON_PING", ts: Date.now() }));
      })()
    );
  }
});

// Push notifications — wake the app
self.addEventListener("push", (event) => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch { data = { body: event.data?.text() }; }
  event.waitUntil(
    self.registration.showNotification(data.title || "Pegasus", {
      body: data.body || "Pegasus daemon is running",
      icon: "/favicon-192.png",
      badge: "/favicon-192.png",
      tag: "pegasus-daemon",
      renotify: true,
      requireInteraction: false,
    })
  );
});

// Notification click — focus or open the app
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      if (clients.length > 0) {
        return clients[0].focus();
      }
      return self.clients.openWindow("/");
    })
  );
});

// Message handler — accept keepalive commands from the app
self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "KEEPALIVE_START") {
    // Register periodic sync if supported
    if (self.registration.periodicSync) {
      self.registration.periodicSync.register("pegasus-daemon", {
        minInterval: 60 * 1000, // every minute
      }).catch(() => undefined);
    }
    // Register background sync
    if (self.registration.sync) {
      self.registration.sync.register("pegasus-keepalive").catch(() => undefined);
    }
  }
  if (event.data && event.data.type === "KEEPALIVE_STOP") {
    if (self.registration.periodicSync) {
      self.registration.periodicSync.unregister("pegasus-daemon").catch(() => undefined);
    }
  }
});
