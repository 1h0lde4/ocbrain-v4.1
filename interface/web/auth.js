/*
 * interface/web/auth.js -- API authentication for the web UI (DEBT-025).
 *
 * The API requires "Authorization: Bearer <token>".  The token is the
 * per-installation secret in data/api_token.  It is held in sessionStorage only
 * (cleared when the tab closes) and is adopted from a "#token=..." URL fragment,
 * which the tray launcher supplies; the fragment is removed from the address bar
 * immediately.  If a call is rejected with 401 the user is asked for the token
 * once and the call is retried once.
 *
 * ocFetch(url, opts)            -- fetch() with the Authorization header added
 * ocEventStream(url, onMessage) -- EventSource replacement (EventSource cannot
 *                                  send headers); returns {close()}
 */
(function () {
  'use strict';
  var KEY = 'ocbrain_api_token';
  var pendingPrompt = null;

  function adoptFragmentToken() {
    var m = /(?:^|[#&])token=([^&]+)/.exec(window.location.hash || '');
    if (!m) return;
    try { sessionStorage.setItem(KEY, decodeURIComponent(m[1])); } catch (e) { /* storage blocked */ }
    try {
      window.history.replaceState(null, '', window.location.pathname + window.location.search);
    } catch (e) { /* ignore */ }
  }

  function getToken() {
    try { return sessionStorage.getItem(KEY) || ''; } catch (e) { return ''; }
  }

  function askForToken() {
    if (!pendingPrompt) {
      pendingPrompt = Promise.resolve().then(function () {
        var t = window.prompt('OCBrain API token (the contents of the data/api_token file on this machine):');
        t = t ? t.trim() : '';
        try {
          if (t) sessionStorage.setItem(KEY, t); else sessionStorage.removeItem(KEY);
        } catch (e) { /* ignore */ }
        pendingPrompt = null;
        return t;
      });
    }
    return pendingPrompt;
  }

  function withAuth(opts, token) {
    var o = Object.assign({}, opts || {});
    var h = new Headers(o.headers || {});
    if (token) h.set('Authorization', 'Bearer ' + token);
    o.headers = h;
    return o;
  }

  window.ocFetch = async function (url, opts) {
    var res = await fetch(url, withAuth(opts, getToken()));
    if (res.status !== 401) return res;
    var token = await askForToken();
    if (!token) return res;
    return fetch(url, withAuth(opts, token));
  };

  window.ocEventStream = function (url, onMessage) {
    var closed = false;
    var controller = null;

    async function run() {
      while (!closed) {
        controller = new AbortController();
        try {
          var res = await window.ocFetch(url, { signal: controller.signal, headers: { Accept: 'text/event-stream' } });
          if (!res.ok || !res.body) {
            if (res.status >= 400 && res.status < 500) return;  // auth/not-found: do not hammer the server
          } else {
            var reader = res.body.getReader();
            var decoder = new TextDecoder();
            var buf = '';
            for (;;) {
              var chunk = await reader.read();
              if (chunk.done) break;
              buf += decoder.decode(chunk.value, { stream: true });
              var idx;
              while ((idx = buf.indexOf('\n\n')) >= 0) {
                var block = buf.slice(0, idx);
                buf = buf.slice(idx + 2);
                var data = block.split('\n')
                  .filter(function (l) { return l.indexOf('data:') === 0; })
                  .map(function (l) { return l.slice(5).replace(/^ /, ''); })
                  .join('\n');
                if (data !== '' || block.indexOf('data:') >= 0) onMessage({ data: data });
              }
            }
          }
        } catch (e) {
          if (closed) return;
        }
        if (!closed) await new Promise(function (r) { setTimeout(r, 2000); });  // like EventSource: reconnect
      }
    }
    run();
    return { close: function () { closed = true; if (controller) controller.abort(); } };
  };

  adoptFragmentToken();
})();
