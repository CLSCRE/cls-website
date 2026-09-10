/* clscre.com site search — client-side, loads JSON index on first focus.
   GA4: fires search event with the raw term (data Trevor wants). */
(function () {
  "use strict";
  var idx = null;
  var loading = false;

  function loadIndex(cb) {
    if (idx) return cb();
    if (loading) return;
    loading = true;
    var s = document.createElement("script");
    var base = document.querySelector('script[src*="search.js"]');
    var root = base ? base.src.replace(/search\.js.*$/, "") : "/search/";
    s.src = root + "search-index.json";
    s.onload = function () {
      idx = window.__CLS_SEARCH_INDEX__ || [];
      cb();
    };
    s.onerror = function () { loading = false; };
    document.head.appendChild(s);
  }

  function score(e, q) {
    var t = e.t.toLowerCase(), h = (e.h || "").toLowerCase(), k = e.k;
    var s = 0, i;
    if (t === q) s += 100;
    if (t.indexOf(q) === 0) s += 50;
    if (t.indexOf(q) > -1) s += 25;
    if (h.indexOf(q) > -1) s += 15;
    if (k.indexOf(q) > -1) s += 5;
    var words = q.split(/\s+/);
    for (i = 0; i < words.length; i++) {
      if (words[i].length > 2) {
        if (t.indexOf(words[i]) > -1) s += 8;
        if (k.indexOf(words[i]) > -1) s += 2;
      }
    }
    return s;
  }

  function search(q) {
    q = q.trim().toLowerCase();
    if (!q || q.length < 2 || !idx) return [];
    var out = [];
    for (var i = 0; i < idx.length; i++) {
      var s = score(idx[i], q);
      if (s > 0) out.push({ e: idx[i], s: s });
    }
    out.sort(function (a, b) { return b.s - a.s; });
    return out.slice(0, 8);
  }

  function esc(s) {
    return s.replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function track(term) {
    try {
      if (window.gtag) {
        window.gtag("event", "search", {
          search_term: term,
          event_category: "site_search",
          event_label: "nav_search"
        });
      }
      if (window.dataLayer) {
        window.dataLayer.push({ event: "site_search", search_term: term });
      }
    } catch (e) { /* never block UI on analytics */ }
  }

  var debounceTimer = null;

  function initInput(inp, wrap) {
    var results = wrap.querySelector(".cls-search-results");
    var resultList = wrap.querySelector(".cls-search-results-list");

    inp.addEventListener("focus", function () { loadIndex(function () {}); });

    inp.addEventListener("input", function () {
      var v = inp.value;
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(function () {
        if (v.trim().length < 2) {
          results.style.display = "none";
          return;
        }
        track(v);  // every typed query (debounced) is the data Trevor wants
        loadIndex(function () {
          var hits = search(v);
          resultList.innerHTML = "";
          if (!hits.length) {
            resultList.innerHTML =
              '<div class="cls-search-empty">No results — try "life company", "bridge loan", "construction", or a city name.</div>';
          } else {
            hits.forEach(function (hit) {
              var a = document.createElement("a");
              a.className = "cls-search-item";
              var depth = (/^(https?:\/\/[^\/]+)?\//.test(a.baseURI) ? "" : "");
              a.href = relPrefix() + hit.e.u;
              a.innerHTML =
                '<span class="cls-search-item-title">' + esc(hit.e.t) + "</span>" +
                '<span class="cls-search-item-section">' + esc(hit.e.s) + "</span>";
              resultList.appendChild(a);
            });
          }
          results.style.display = "block";
        });
      }, 220);
    });

    inp.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape") {
        results.style.display = "none";
        inp.blur();
      }
    });

    document.addEventListener("click", function (ev) {
      if (!wrap.contains(ev.target)) results.style.display = "none";
    });
  }

  function relPrefix() {
    // compute prefix so /search/index paths work from subdirs
    var path = location.pathname;
    var m = path.match(/^\/(.+)\/(?:[^\/]+\.html)?$/);
    if (!m) return "/";
    return "/" + m[1] + "/";
  }

  function boot() {
    var inputs = document.querySelectorAll(".cls-search-input");
    for (var i = 0; i < inputs.length; i++) {
      var inp = inputs[i];
      var wrap = inp.closest(".cls-search") || inp.parentElement;
      initInput(inp, wrap);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
