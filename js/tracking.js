/**
 * Commercial Lending Solutions - clscre.com tracking
 *
 * Fires events on:
 *   - Contact clicks (mailto:, tel:, sms:) for ANY address (legacy compat)
 *   - "Web-sourced lead" for website-only channels (loans@clscre.com,
 *     phone 310-708-0690, text 310-758-3064)
 *
 * Events emitted (both dataLayer for GTM and gtag for direct GA4/Ads):
 *   - contact_click            - any tel:/mailto:/sms: click (legacy)
 *   - web_sourced_lead         - website-only phone / SMS / email channels
 *   - tool_engagement          - 30+ second engagement on a calculator
 *   - (Ads conversion)         - Outlook "Book a Call" booking-link clicks
 *                                report straight to Google Ads via send_to;
 *                                GA4 book_a_call stays GTM-owned
 *
 * Configure in Google Ads:
 *   - Primary conversion: web_sourced_lead (Sources: GA4 imported event)
 *   - Secondary (form): generate_lead (already fired by form handlers)
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

  // Website-only channel identifiers. Match on last-10 digits so +1 /
  // punctuation variants still count as web-sourced.
  var WEBSITE_ONLY_PHONE_LAST10 = ['3107080690'];
  var WEBSITE_ONLY_SMS_LAST10 = ['3107583064'];
  var WEBSITE_ONLY_EMAILS = ['loans@clscre.com'];

  function digitsOnly(value) {
    return (value || '').replace(/\D/g, '');
  }

  function last10(value) {
    var d = digitsOnly(value);
    return d.length <= 10 ? d : d.slice(-10);
  }

  function isWebsiteOnlyPhone(value) {
    return WEBSITE_ONLY_PHONE_LAST10.indexOf(last10(value)) !== -1;
  }

  function isWebsiteOnlySms(value) {
    return WEBSITE_ONLY_SMS_LAST10.indexOf(last10(value)) !== -1;
  }

  function isWebsiteOnlyEmail(value) {
    var v = (value || '').toLowerCase().trim();
    return WEBSITE_ONLY_EMAILS.indexOf(v) !== -1;
  }

  function fireEvent(eventName, params) {
    var payload = Object.assign({ event: eventName }, params || {});
    window.dataLayer.push(payload);
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
      } else if (href.indexOf('sms:') === 0) {
        // sms:+13107583064 or sms:+13107583064?body=...
        var smsTarget = href.replace('sms:', '').split('?')[0];
        var webSourcedSms = isWebsiteOnlySms(smsTarget);

        fireEvent('contact_click', {
          contact_method: 'sms',
          contact_value: smsTarget,
          page_path: pagePath,
          link_text: linkText,
          website_only_channel: webSourcedSms
        });

        if (webSourcedSms) {
          fireEvent('web_sourced_lead', {
            channel: 'sms_3107583064',
            contact_value: smsTarget,
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
        // Book a Call — Ads conversion only; GA4 book_a_call is GTM-owned.
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

  // Tool engagement: 30+ seconds on /tools/ with at least one input interaction.
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
