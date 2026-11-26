/**
 * Commercial Lending Solutions - clscre.com privacy choices (CCPA/CPRA opt-out model)
 *
 * What it does
 *   - Honors the Global Privacy Control signal (navigator.globalPrivacyControl) and a
 *     saved opt-out (localStorage "cls_privacy_optout" = "1") as an opt-out of
 *     advertising and analytics tracking.
 *   - The decision that matters before any tag loads is made by a tiny inline script
 *     in every page head (it sets window.clsOptOut and a Google Consent Mode default
 *     of "denied" BEFORE Google Tag Manager starts). This file adds the visible parts:
 *     the one-time notice, the "Your Privacy Choices" footer link, and the dialog.
 *   - Opting out: updates Google Consent Mode to denied, tells Clarity to stop,
 *     clears the ad click IDs we stored for lead attribution, and removes the
 *     analytics/advertising cookies this site can see. It applies fully from the next
 *     page view (a third-party script that already loaded cannot be unloaded).
 *   - Essential cookies (form spam protection, the site's own functions) are not affected.
 */
(function () {
  'use strict';
  if (typeof document === 'undefined') return;

  var OPT_KEY = 'cls_privacy_optout';
  var SEEN_KEY = 'cls_privacy_notice_seen';
  var gpc = false;
  try { gpc = navigator.globalPrivacyControl === true; } catch (e) {}

  function get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function put(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  function drop(k) { try { localStorage.removeItem(k); } catch (e) {} }

  function isOptedOut() { return gpc || get(OPT_KEY) === '1'; }

  window.dataLayer = window.dataLayer || [];
  function g() { window.dataLayer.push(arguments); }

  function setConsent(state) {
    g('consent', 'update', {
      ad_storage: state, ad_user_data: state, ad_personalization: state, analytics_storage: state
    });
  }

  function clearTrackingData() {
    ['gclid', 'wbraid', 'gbraid'].forEach(function (k) { drop('cls_' + k); });
    var re = /^(_ga|_gid|_gat|_gcl_|_gac_|_gads|_gpi|_clck|_clsk|CLID|SM|MUID|ANONCHK|li_|bcookie|bscookie|lidc|UserMatchHistory|AnalyticsSyncHistory|_uet|IDE|test_cookie)/;
    var host = location.hostname;
    var parts = host.split('.');
    var domains = ['', host, '.' + host];
    if (parts.length > 2) domains.push('.' + parts.slice(-2).join('.'));
    else if (parts.length === 2) domains.push('.' + host);
    document.cookie.split(';').forEach(function (c) {
      var name = c.split('=')[0].replace(/^\s+/, '');
      if (!name || !re.test(name)) return;
      domains.forEach(function (d) {
        document.cookie = name + '=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/' + (d ? '; domain=' + d : '');
      });
    });
  }

  function optOut() {
    put(OPT_KEY, '1');
    window.clsOptOut = true;
    setConsent('denied');
    try { if (typeof window.clarity === 'function') { window.clarity('consent', false); window.clarity('stop'); } } catch (e) {}
    clearTrackingData();
  }

  function optIn() {
    if (gpc) return; // a browser-level opt-out signal is always honored
    put(OPT_KEY, '0');
    window.clsOptOut = false;
    setConsent('granted');
  }

  window.clsPrivacy = { optOut: optOut, optIn: optIn, isOptedOut: isOptedOut, gpc: gpc };

  // Keep the page-level flag in step with storage even if the head script was missing.
  if (isOptedOut()) {
    window.clsOptOut = true;
    clearTrackingData();
  }

  /* ---------- UI ---------- */
  var CSS = ''
    + '#cls-pn{position:fixed;left:16px;bottom:16px;z-index:9990;max-width:430px;background:#fff;color:#1f2937;'
    + 'border:1px solid #d1d5db;border-top:3px solid #153D63;border-radius:10px;box-shadow:0 10px 36px rgba(0,0,0,.18);'
    + 'padding:16px 18px;font:14px/1.5 Inter,system-ui,-apple-system,sans-serif}'
    + '#cls-pn p{margin:0 0 12px}#cls-pn a{color:#153D63;text-decoration:underline}'
    + '.cls-pn-row{display:flex;flex-wrap:wrap;gap:8px}'
    + '.cls-pn-btn{font:600 13px Inter,system-ui,sans-serif;padding:9px 16px;border-radius:6px;cursor:pointer;border:2px solid #153D63;background:#fff;color:#153D63}'
    + '.cls-pn-btn.pri{background:#153D63;color:#fff}.cls-pn-btn:hover{background:#006A4E;border-color:#006A4E;color:#fff}'
    + '.cls-pn-btn:focus-visible,#cls-pd a:focus-visible{outline:3px solid #00A676;outline-offset:2px}'
    + '#cls-pd-wrap{position:fixed;inset:0;z-index:10000;background:rgba(13,43,71,.55);display:flex;align-items:center;justify-content:center;padding:16px}'
    + '#cls-pd{background:#fff;color:#1f2937;border-radius:12px;max-width:480px;width:100%;padding:24px;box-shadow:0 24px 60px rgba(0,0,0,.3);font:14px/1.55 Inter,system-ui,-apple-system,sans-serif}'
    + '#cls-pd h2{margin:0 0 10px;font:400 24px "DM Serif Display",Georgia,serif;color:#153D63}'
    + '#cls-pd p{margin:0 0 12px}#cls-pd .st{font-weight:700;color:#153D63}'
    + '.cls-pc-fallback{padding:14px 16px;text-align:center;font:13px Inter,system-ui,sans-serif;background:#111827}'
    + '.cls-pc-fallback a{color:rgba(255,255,255,.75)}'
    + '@media(max-width:600px){#cls-pn{left:12px;right:12px;max-width:none}}';

  function el(tag, attrs, text) {
    var n = document.createElement(tag);
    if (attrs) for (var k in attrs) n.setAttribute(k, attrs[k]);
    if (text) n.textContent = text;
    return n;
  }

  function injectStyle() {
    if (document.getElementById('cls-pc-style')) return;
    var s = el('style', { id: 'cls-pc-style' });
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  var notice = null;
  function closeNotice() {
    if (notice && notice.parentNode) notice.parentNode.removeChild(notice);
    notice = null;
  }

  function showNotice() {
    if (get(SEEN_KEY) || document.getElementById('cls-pn')) return;
    injectStyle();
    notice = el('div', { id: 'cls-pn', role: 'region', 'aria-label': 'Privacy notice' });
    var p = el('p');
    if (gpc) {
      p.appendChild(document.createTextNode('Your browser is sending a Global Privacy Control signal, so advertising and analytics tracking is already off for you. '));
    } else {
      p.appendChild(document.createTextNode('We use cookies and similar tools for analytics and advertising. You can opt out at any time. '));
    }
    var a = el('a', { href: '/privacy.html' }, 'Privacy Policy');
    p.appendChild(a);
    p.appendChild(document.createTextNode('.'));
    notice.appendChild(p);
    var row = el('div', { 'class': 'cls-pn-row' });
    var ok = el('button', { type: 'button', 'class': 'cls-pn-btn pri' }, gpc ? 'OK' : 'Got it');
    ok.addEventListener('click', function () { put(SEEN_KEY, '1'); closeNotice(); });
    row.appendChild(ok);
    if (!gpc) {
      var no = el('button', { type: 'button', 'class': 'cls-pn-btn' }, 'Opt out');
      no.addEventListener('click', function () { optOut(); put(SEEN_KEY, '1'); closeNotice(); openDialog(); });
      row.appendChild(no);
    }
    notice.appendChild(row);
    document.body.appendChild(notice);
    // Keep clear of the mobile call-to-action bar if the page shows one.
    try {
      var bar = document.getElementById('cls-mcb');
      if (bar && getComputedStyle(bar).display !== 'none' && window.innerWidth <= 768) {
        notice.style.bottom = (bar.offsetHeight + 12) + 'px';
      }
    } catch (e) {}
  }

  var lastFocus = null;
  function closeDialog() {
    var w = document.getElementById('cls-pd-wrap');
    if (w && w.parentNode) w.parentNode.removeChild(w);
    document.removeEventListener('keydown', onKey, true);
    if (lastFocus && lastFocus.focus) { try { lastFocus.focus(); } catch (e) {} }
    refreshStatus();
  }
  function onKey(e) {
    if (e.key === 'Escape') { e.preventDefault(); closeDialog(); }
  }

  function statusText() {
    if (gpc) return 'OFF (your browser’s Global Privacy Control signal is honored automatically)';
    return isOptedOut() ? 'OFF (you have opted out)' : 'ON';
  }

  function refreshStatus() {
    var nodes = document.querySelectorAll('[data-cls-privacy-status]');
    for (var i = 0; i < nodes.length; i++) nodes[i].textContent = statusText();
    var btns = document.querySelectorAll('[data-cls-privacy-toggle]');
    for (var j = 0; j < btns.length; j++) {
      btns[j].textContent = isOptedOut() ? 'Turn tracking back on' : 'Opt out of advertising and analytics tracking';
      btns[j].disabled = gpc;
      btns[j].style.opacity = gpc ? '.55' : '';
    }
  }

  function openDialog() {
    if (document.getElementById('cls-pd-wrap')) return;
    injectStyle();
    lastFocus = document.activeElement;
    var wrap = el('div', { id: 'cls-pd-wrap' });
    var box = el('div', { id: 'cls-pd', role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': 'cls-pd-h' });
    box.appendChild(el('h2', { id: 'cls-pd-h' }, 'Your Privacy Choices'));
    var p1 = el('p');
    p1.appendChild(document.createTextNode('Advertising and analytics tracking on this site: '));
    p1.appendChild(el('span', { 'class': 'st', 'data-cls-privacy-status': '' }));
    box.appendChild(p1);
    box.appendChild(el('p', null, 'Opting out turns off Google Ads and Google Analytics measurement, LinkedIn advertising and Microsoft Clarity for this browser. It takes full effect on your next page view. Cookies needed for forms and spam protection stay on, and your choice is remembered on this device only.'));
    var row = el('div', { 'class': 'cls-pn-row' });
    var tog = el('button', { type: 'button', 'class': 'cls-pn-btn pri', 'data-cls-privacy-toggle': '' });
    tog.addEventListener('click', function () { if (isOptedOut()) optIn(); else optOut(); refreshStatus(); });
    var cl = el('button', { type: 'button', 'class': 'cls-pn-btn' }, 'Close');
    cl.addEventListener('click', closeDialog);
    row.appendChild(tog); row.appendChild(cl);
    box.appendChild(row);
    var pp = el('p', { style: 'margin:14px 0 0;font-size:12px' });
    var link = el('a', { href: '/privacy.html', style: 'color:#153D63' }, 'Read the full Privacy Policy');
    pp.appendChild(link);
    box.appendChild(pp);
    wrap.appendChild(box);
    wrap.addEventListener('click', function (e) { if (e.target === wrap) closeDialog(); });
    document.body.appendChild(wrap);
    document.addEventListener('keydown', onKey, true);
    refreshStatus();
    tog.focus();
  }

  function bindTriggers(root) {
    var nodes = (root || document).querySelectorAll('[data-cls-privacy-choices]');
    for (var i = 0; i < nodes.length; i++) {
      if (nodes[i].__clsBound) continue;
      nodes[i].__clsBound = true;
      nodes[i].addEventListener('click', function (e) { e.preventDefault(); openDialog(); });
    }
  }

  function addFooterLink() {
    if (document.querySelector('a[data-cls-privacy-choices]')) return;
    var anchors = document.querySelectorAll('footer a[href$="privacy.html"], a[href$="privacy.html"]');
    var link = el('a', { href: '#privacy-choices', 'data-cls-privacy-choices': '' }, 'Your Privacy Choices');
    if (anchors.length) {
      var ref = anchors[0];
      ref.parentNode.insertBefore(link, ref.nextSibling);
      link.style.cssText = ref.style.cssText;
      link.className = ref.className;
      if (ref.parentNode.nodeName === 'LI') { /* inline list: keep link in same item */ }
      if (ref.parentNode.nodeName === 'DIV' || ref.parentNode.nodeName === 'FOOTER') {
        if (getComputedStyle(ref).display === 'inline') link.style.marginLeft = '14px';
      }
    } else {
      var d = el('div', { 'class': 'cls-pc-fallback' });
      d.appendChild(link);
      document.body.appendChild(d);
      injectStyle();
    }
  }

  function init() {
    addFooterLink();
    bindTriggers();
    refreshStatus();
    if (!isOptedOut() || gpc) showNotice();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
