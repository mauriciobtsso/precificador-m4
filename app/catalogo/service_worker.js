/* M4 Tática — cache offline do catálogo.
 * Sintaxe ES5 de propósito: o iPad Mini 1 não executa Service Worker,
 * mas navegadores antigos que suportem o recurso não devem exigir transpile.
 */
(function () {
    'use strict';

    var CACHE_NAME = 'm4-catalogo-v1';
    var PRECACHE = [
        '/catalogo/',
        '/static/vendor/bootstrap-icons/bootstrap-icons-loja.css',
        '/static/vendor/bootstrap-icons/fonts/bootstrap-icons.woff2?1fa40e8900654d2863d011707b9fb6f2',
        '/static/img/logo_pedido.png',
        '/static/img/favicon-loja.png',
        '/static/img/placeholder.jpg'
    ];

    self.addEventListener('install', function (event) {
        event.waitUntil(
            caches.open(CACHE_NAME).then(function (cache) {
                return cache.addAll(PRECACHE);
            }).then(function () {
                return self.skipWaiting();
            })
        );
    });

    self.addEventListener('activate', function (event) {
        event.waitUntil(
            caches.keys().then(function (keys) {
                return Promise.all(keys.map(function (key) {
                    if (key.indexOf('m4-catalogo-') === 0 && key !== CACHE_NAME) {
                        return caches.delete(key);
                    }
                    return Promise.resolve(false);
                }));
            }).then(function () {
                return self.clients.claim();
            })
        );
    });

    self.addEventListener('fetch', function (event) {
        var request = event.request;
        var url = new URL(request.url);

        if (request.method !== 'GET' || url.origin !== self.location.origin) {
            return;
        }

        // Busca e APIs precisam sempre da resposta atual e não entram offline.
        if (url.pathname.indexOf('/catalogo/api/') === 0 ||
            url.pathname.indexOf('/catalogo/image-proxy/') === 0 && url.search.indexOf('offline=') !== -1) {
            return;
        }

        // Navegação e assets do catálogo usam cache-first para abrir rápido;
        // quando online, a resposta nova é gravada para a próxima visita.
        event.respondWith(
            caches.match(request).then(function (cached) {
                if (cached) return cached;
                return fetch(request).then(function (response) {
                    if (!response || response.status !== 200 || response.type === 'opaque') {
                        return response;
                    }
                    var copy = response.clone();
                    caches.open(CACHE_NAME).then(function (cache) {
                        cache.put(request, copy);
                    });
                    return response;
                }).catch(function () {
                    if (request.mode === 'navigate' ||
                        (request.headers.get('accept') || '').indexOf('text/html') !== -1) {
                        return caches.match('/catalogo/');
                    }
                    return caches.match('/static/img/placeholder.jpg');
                });
            })
        );
    });
}());
