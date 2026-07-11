/**
 * Commercial Lending Solutions - clscre.com tracking
 *
 * Fires events on:
 *   - Contact clicks (mailto:, tel:) for ANY address (legacy compat)
 *   - "Web-sourced lead" specifically for the dedicated website-only
 *     channels (loans@clscre.com + 310-708-0690). These channels are
 *     reserved for clscre.com surfaces only, so a click there proves
 *     web origin and is the primary conversion event for paid ads.
 *
 * Events emitted (both dataLayer for GTM and gtag for direct GA4/Ads):
 *   - contact_click            - any tel:/mailto: click (legacy)
 *   - web_sourced_lead         - clicks on loans@ or 310-708-0690 only
 *   - tool_engagement          - 30+ second engagement on a calculator
 *   - exit_intent_engaged      - exit intent CTA click
 *   - (Ads conversion)         - Outlook "Book a Call" booking-link clicks
 *                                report straight to Google Ads action
 *                                7652984790 via its conversion label; the
 *                                GA4 book_a_call event stays GTM-owned so
 *                                it isn't double-counted in GA4
 *
 * Configure in Google Ads:
 *   - Primary conversion: web_sourced_lead (Sources: GA4 imported event)
 *   - Secondary (form): generate_lead (already fired by form onclick)
 *   - Secondary (soft): tool_engagement (for retargeting / awareness)
 *
 * Configure in GA4:
 *   - Mark web_sourced_lead and generate_lead as Key Events
 *   - Mark tool_engagement as a Standard Event (for audiences)
 */
(function () {
  if (typeof document === 'undefined') return;
  window.dataLayer = window.dataLayer || [];

  // Google Ads conversion destination. Some pages (generated from _base.html)
  // load gtag.js for GA4; hand-maintained pages (homepage etc.) run GTM only
  // and have no window.gtag at all. Conversions reported via send_to need the
  // gtag.js library with the AW destination registered on THIS page, so this
  // block makes tracking.js self-sufficient on every page:
  //   - define window.gtag if the page didn't
  //   - load gtag.js (browser-cached; GTM loads the same library) if absent
  //   - register the AW destination with the on-page gtag instance
  var ADS_ID = 'AW-17966960701';
  var BOOK_A_CALL_SEND_TO = ADS_ID + '/TIpaCNaPncEcEL2gqPdC';
  if (typeof window.gtag !== 'function') {
    window.gtag = function gtag() { window.dataLayer.push(arguments); };
    window.gtag('js', new Date());
  }
  if (!document.querySelector('script[src*="googletagmanager.com/gtag/js"]')) {
    var gtagScript = document.createElement('script');
    gtagScript.async = true;
    gtagScript.src = 'https://www.googletagmanager.com/gtag/js?id=' + ADS_ID;
    (document.head || document.documentElement).appendChild(gtagScript);
  }
  window.gtag('config', ADS_ID);

  // Website-only channel identifiers. Any contact click matching these
  // values is provably web-sourced and triggers the web_sourced_lead
  // conversion event in addition to the generic contact_click.
  var WEBSITE_ONLY_PHONES = ['3107080690', '+13107080690', '310-708-0690', '310.708.0690'];
  var WEBSITE_ONLY_EMAILS = ['loans@clscre.com'];

  function normalizePhone(value) {
    return (value || '').replace(/[^\d+]/g, '');
  }

  function isWebsiteOnlyPhone(value) {
    var n = normalizePhone(value);
    return WEBSITE_ONLY_PHONES.some(function (p) {
      return normalizePhone(p) === n;
    });
  }

  function isWebsiteOnlyEmail(value) {
    var v = (value || '').toLowerCase().trim();
    return WEBSITE_ONLY_EMAILS.indexOf(v) !== -1;
  }

  function fireEvent(eventName, params) {
    // Push to dataLayer for GTM-mediated routing
    var payload = Object.assign({ event: eventName }, params || {});
    window.dataLayer.push(payload);

    // Fire gtag directly so GA4 / Google Ads can ingest without GTM tag config.
    // gtag is loaded by GTM, GA4 base tag, or Google Ads tag manually.
    if (typeof window.gtag === 'function') {
      window.gtag('event', eventName, params || {});
    }
  }

  document.addEventListener(
    'click',
    function (e) {
      var a = e.target && e.target.closest ? e.target.closest('a[href]') : null;
      if (!a) return;
      var href = a.getAttribute('href') || '';
      var linkText = (a.textContent || '').trim().slice(0, 80);
      var pagePath = location.pathname;

      if (href.indexOf('tel:') === 0) {
        var phone = href.replace('tel:', '');
        var webSourced = isWebsiteOnlyPhone(phone);

        fireEvent('contact_click', {
          contact_method: 'phone',
          contact_value: phone,
          page_path: pagePath,
          link_text: linkText,
          website_only_channel: webSourced
        });

        if (webSourced) {
          fireEvent('web_sourced_lead', {
            channel: 'phone_3107080690',
            contact_value: phone,
            page_path: pagePath,
            link_text: linkText,
            value: 1.0,
            currency: 'USD'
          });
        }
      } else if (href.indexOf('mailto:') === 0) {
        var email = href.replace('mailto:', '').split('?')[0];
        var webSourcedEmail = isWebsiteOnlyEmail(email);

        fireEvent('contact_click', {
          contact_method: 'email',
          contact_value: email,
          page_path: pagePath,
          link_text: linkText,
          website_only_channel: webSourcedEmail
        });

        if (webSourcedEmail) {
          fireEvent('web_sourced_lead', {
            channel: 'email_loans',
            contact_value: email,
            page_path: pagePath,
            link_text: linkText,
            value: 1.0,
            currency: 'USD'
          });
        }
      } else if (href.indexOf('outlook.office.com/bookwithme') !== -1) {
        // "Book a Call" — report the Google Ads conversion directly.
        // The GA4 book_a_call event for this click is fired by GTM, so
        // only the Ads side is reported here. The action counts once per
        // ad click (ONE_PER_CLICK), so duplicate pings are deduplicated.
        if (typeof window.gtag === 'function') {
          window.gtag('event', 'conversion', {
            send_to: BOOK_A_CALL_SEND_TO,
            value: 1.0,
            currency: 'USD',
            transport_type: 'beacon',
            page_path: pagePath
          });
        }
      }
    },
    { passive: true }
  );

  // Tool engagement: fire if the user spends 30+ seconds on a calculator
  // page AND interacts with at least one input. Useful for retargeting and
  // for the Tools Soft Entry Google Ads campaign.
  if (location.pathname.indexOf('/tools/') === 0) {
    var startedAt = Date.now();
    var hasInteracted = false;
    var fired = false;

    var markInteraction = function () {
      hasInteracted = true;
    };
    document.addEventListener('input', markInteraction, { passive: true, once: true });
    document.addEventListener('change', markInteraction, { passive: true, once: true });

    setTimeout(function () {
      if (fired) return;
      if (!hasInteracted) return;
      fired = true;
      var calc = (location.pathname.split('/').pop() || '').replace('.html', '');
      fireEvent('tool_engagement', {
        calculator: calc,
        page_path: location.pathname,
        seconds_on_page: Math.round((Date.now() - startedAt) / 1000)
      });
    }, 30000);
  }
})();
