// 消防监督检查智能辅助系统 — Service Worker
// 策略：静态资源缓存优先 + API 网络优先（离线降级）
const CACHE_STATIC = "fire-inspect-static-v11";
const CACHE_CDN = "fire-inspect-cdn-v2";
const CACHE_API = "fire-inspect-api-v2";

// ── 安装：预缓存核心静态资源 ──────────────────────
// 注意：HTML 不在缓存列表中，始终从网络获取最新版本
const STATIC_ASSETS = [
  "/inspect/web/app_v70.js",
  "/inspect/web/styles_v3.css",
  "/inspect/web/manifest.json",
  "/inspect/web/app-extras.js",
  "/inspect/web/sw.js",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_STATIC).then((cache) => {
      return Promise.allSettled(
        STATIC_ASSETS.map((url) =>
          cache.add(url).catch(() => {
            // 忽略单个文件缓存失败
          })
        )
      );
    }).then(() => self.skipWaiting())
  );
});

// ── 激活：清理旧缓存 ──────────────────────────────
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k.startsWith("fire-inspect-") &&
            ![CACHE_STATIC, CACHE_CDN, CACHE_API].includes(k))
          .map((k) => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

// ── 请求拦截 ──────────────────────────────────────
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // API 请求：网络优先，离线降级
  if (url.pathname.includes("/api/")) {
    event.respondWith(networkFirst(event.request, CACHE_API));
    return;
  }

  // CDN 脚本：网络优先，失败才用缓存
  if (url.hostname === "unpkg.com" || url.hostname === "cdn.jsdelivr.net") {
    event.respondWith(networkFirst(event.request, CACHE_CDN));
    return;
  }

  // 所有页面和静态资源：网络优先（确保最新，离线降级）
  event.respondWith(networkFirst(event.request, CACHE_STATIC));
});

// ── 缓存策略 ──────────────────────────────────────

async function cacheFirst(request, cacheName) {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    // 完全离线返回空
    return new Response("", { status: 503 });
  }
}

async function networkFirst(request, cacheName) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    // 离线时尝试返回缓存数据
    const cached = await caches.match(request);
    if (cached) return cached;
    // 无缓存时返回离线提示
    return new Response(
      JSON.stringify({
        code: 0,
        data: [],
        message: "当前处于离线状态，数据将联网后同步",
      }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
  }
}

async function staleWhileRevalidate(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  const fetchPromise = fetch(request).then((response) => {
    if (response.ok) cache.put(request, response.clone());
    return response;
  }).catch(() => null);
  return cached || fetchPromise;
}
