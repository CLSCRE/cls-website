(function(){
  if (typeof document === 'undefined') return;
  window.dataLayer = window.dataLayer || [];

  document.addEventListener('click', function(e) {
    var a = e.target && e.target.closest ? e.target.closest('a[href]') : null;
    if (!a) return;
    var href = a.getAttribute('href') || '';
    if (href.indexOf('tel:') === 0) {
      window.dataLayer.push({
        event: 'contact_click',
        contact_method: 'phone',
        contact_value: href.replace('tel:', ''),
        page_path: location.pathname,
        link_text: (a.textContent || '').trim().slice(0, 80)
      });
    } else if (href.indexOf('mailto:') === 0) {
      window.dataLayer.push({
        event: 'contact_click',
        contact_method: 'email',
        contact_value: href.replace('mailto:', '').split('?')[0],
        page_path: location.pathname,
        link_text: (a.textContent || '').trim().slice(0, 80)
      });
    }
  }, { passive: true });
})();
