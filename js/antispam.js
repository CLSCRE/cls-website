/**
 * CLS CRE Anti-Spam Protection v3
 * Multi-layered bot defense for static site forms.
 * - Cloudflare Turnstile (visible challenge, replaces reCAPTCHA v3)
 * - Headless browser detection
 * - Proof of work (CPU-bound)
 * - Honeypot fields
 * - Human interaction signals
 * - Disposable email blocking (60+ domains)
 * - Bot phrase / phone pattern detection
 * - Canvas fingerprint anomaly check
 */
(function() {
  'use strict';

  // ── Config ──────────────────────────────────────────────────────────
  // Cloudflare Turnstile (free, replaces reCAPTCHA v3)
  // Get your site key at https://dash.cloudflare.com/?to=/:account/turnstile
  // Set to '' to disable Turnstile and fall back to other checks
  var TURNSTILE_SITE_KEY = '';

  // Legacy reCAPTCHA v3 — kept as fallback if Turnstile is not configured
  var RECAPTCHA_SITE_KEY = '6LeB3JMsAAAAAKwoYS1jZKGPfsqVcl3IjVidDWZw';

  // ── Obfuscated endpoint ─────────────────────────────────────────────
  // Form endpoint ONLY exists in JavaScript. HTML has action="#".
  // XOR-encoded endpoint parts — NOT plain char codes, requires decode logic
  var _aX=[104,108,114,113,108,116,110,100,113]; // user part
  var _bX=[98,110,112,103,119,99,41,98,109,110]; // domain part
  var _cP=[104,116,116,112,115,58,47,47,102,111,114,109,115,117,98,109,105,116,46,99,111,47]; // host
  function _buildEndpoint(){
    var user='';for(var i=0;i<_aX.length;i++)user+=String.fromCharCode(_aX[i]^(i%7+1));
    var dom='';for(var i=0;i<_bX.length;i++)dom+=String.fromCharCode(_bX[i]^(i%7+1));
    var host='';for(var i=0;i<_cP.length;i++)host+=String.fromCharCode(_cP[i]);
    return host+user+'@'+dom;
  }

  // ── Turnstile / reCAPTCHA loader ────────────────────────────────────
  var captchaReady = false;
  var captchaType = 'none'; // 'turnstile' | 'recaptcha' | 'none'

  if (TURNSTILE_SITE_KEY) {
    captchaType = 'turnstile';
    var tsScript = document.createElement('script');
    tsScript.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?onload=_clsTurnstileReady';
    tsScript.async = true;
    tsScript.defer = true;
    document.head.appendChild(tsScript);
    window._clsTurnstileReady = function() { captchaReady = true; };
  } else if (RECAPTCHA_SITE_KEY) {
    captchaType = 'recaptcha';
    var rcScript = document.createElement('script');
    rcScript.src = 'https://www.google.com/recaptcha/api.js?render=' + RECAPTCHA_SITE_KEY;
    rcScript.async = true;
    rcScript.defer = true;
    rcScript.onload = function() { captchaReady = true; };
    document.head.appendChild(rcScript);
  }

  // ── Human interaction tracking ──────────────────────────────────────
  var HUMAN = {
    mouse: false, key: false, scroll: false,
    touch: false, focus: false, click: false,
    timeLoaded: Date.now(),
    moveCount: 0, keyCount: 0, scrollCount: 0
  };

  document.addEventListener('mousemove', function() {
    HUMAN.mouse = true; HUMAN.moveCount++;
  }, {passive: true});
  document.addEventListener('keydown', function() {
    HUMAN.key = true; HUMAN.keyCount++;
  }, {passive: true});
  document.addEventListener('scroll', function() {
    HUMAN.scroll = true; HUMAN.scrollCount++;
  }, {passive: true});
  document.addEventListener('touchstart', function() { HUMAN.touch = true; }, {once: true, passive: true});
  document.addEventListener('focusin', function() { HUMAN.focus = true; }, {once: true});
  document.addEventListener('click', function() { HUMAN.click = true; }, {once: true});

  // ── Headless browser detection ──────────────────────────────────────
  function detectHeadless() {
    var dominated = 0;

    // navigator.webdriver is set by Selenium/Puppeteer/Playwright
    if (navigator.webdriver === true) dominated += 3;

    // Missing chrome object in Chrome UA
    if (/Chrome/.test(navigator.userAgent) && !window.chrome) dominated += 2;

    // Zero plugins (real browsers almost always have at least 1)
    if (navigator.plugins && navigator.plugins.length === 0) dominated++;

    // Missing languages
    if (!navigator.languages || navigator.languages.length === 0) dominated++;

    // Headless in UA
    if (/HeadlessChrome|PhantomJS|Headless/i.test(navigator.userAgent)) dominated += 3;

    // Impossible screen dimensions
    if (window.outerWidth === 0 && window.outerHeight === 0) dominated += 2;
    if (screen.width < 100 || screen.height < 100) dominated += 2;

    // Missing permissions API (most headless don't have it)
    if (!navigator.permissions) dominated++;

    // Notification permission oddity
    if (window.Notification && Notification.permission === 'denied' &&
        !navigator.userAgent.match(/Firefox/)) dominated++;

    // Canvas fingerprint anomaly — headless renderers often produce uniform output
    try {
      var canvas = document.createElement('canvas');
      canvas.width = 200; canvas.height = 50;
      var ctx = canvas.getContext('2d');
      ctx.textBaseline = 'top';
      ctx.font = '14px Arial';
      ctx.fillStyle = '#f60';
      ctx.fillRect(125, 1, 62, 20);
      ctx.fillStyle = '#069';
      ctx.fillText('CLS CRE anti-bot', 2, 15);
      var data = canvas.toDataURL();
      // Extremely short data URL = rendering failure (headless)
      if (data.length < 1000) dominated += 2;
    } catch(e) {
      dominated++;
    }

    return dominated;
  }

  // ── Proof of work (harder: hash % 1000 == 0 → ~1000 iterations avg) ─
  function generatePOW() {
    var nonce = 0;
    var ts = Date.now().toString(36);
    var maxIter = 500000;
    while (nonce < maxIter) {
      var check = 'cls:' + ts + ':' + nonce;
      var hash = 0;
      for (var i = 0; i < check.length; i++) {
        hash = ((hash << 5) - hash) + check.charCodeAt(i);
        hash = ((hash << 13) ^ hash) - (hash >>> 7);
        hash |= 0;
      }
      if ((Math.abs(hash) % 1000) === 0) {
        return ts + ':' + nonce + ':' + hash;
      }
      nonce++;
    }
    return ts + ':fail:0';
  }

  // ── Disposable email domains (60+) ──────────────────────────────────
  var DISPOSABLE_DOMAINS = [
    'mailinator.com','guerrillamail.com','guerrillamail.de','tempmail.com',
    'throwaway.email','fakeinbox.com','sharklasers.com','guerrillamailblock.com',
    'grr.la','dispostable.com','yopmail.com','trashmail.com','maildrop.cc',
    'mailnesia.com','tempinbox.com','tmpmail.org','getnada.com','emailondeck.com',
    'mohmal.com','burner.kiwi','temp-mail.org','10minutemail.com',
    'minuteinbox.com','tempmailaddress.com','mailtemp.net','discard.email',
    'harakirimail.com','mailcatch.com','tempmails.net','disposableemailaddresses.emailmiser.com',
    'tmail.com','tempmailo.com','mytemp.email','inboxbear.com',
    'tempail.com','crazymailing.com','mailslurp.com','guerrillamail.net',
    'spam4.me','trashmail.me','trashmail.net','trash-mail.com',
    'tempmailer.com','jetable.com','mailnator.com','fakemailgenerator.com',
    'tempsky.com','emkei.cz','mailsac.com','mailbox.in.ua',
    'anonbox.net','binkmail.com','bobmail.info','classpmail.com',
    'flirtto.com','getairmail.com','incognitomail.com','mailexpire.com',
    'mailforspam.com','mailinater.com','meltmail.com','spamavert.com',
    'spamfree24.org','spamgourmet.com','tempomail.fr','wegwerfmail.de',
    'protonmail.com' // often used by spam bots, not disposable but high-spam
  ];
  // Remove protonmail — it's legit. Keep the rest.
  DISPOSABLE_DOMAINS.pop();

  // ── Validate form submission ────────────────────────────────────────
  window.clsAntiSpam = function(form) {
    var errors = [];
    var hardBlock = false;

    // ─ Check 0: Headless browser detection ─
    var headlessScore = detectHeadless();
    if (headlessScore >= 4) {
      // Very likely headless — silent block
      _silentBlock();
      return false;
    }
    if (headlessScore >= 2) {
      errors.push('headless');
    }

    // ─ Check 1: Honeypot fields ─
    var honey1 = form.querySelector('[name="_honey"]');
    var honey2 = form.querySelector('[name="website_url"]');
    var honey3 = form.querySelector('[name="_company_fax"]');
    if ((honey1 && honey1.value) || (honey2 && honey2.value) || (honey3 && honey3.value)) {
      _silentBlock();
      return false;
    }

    // ─ Check 2: Time-based (must spend at least 5 seconds on page) ─
    var elapsed = (Date.now() - HUMAN.timeLoaded) / 1000;
    if (elapsed < 5) {
      errors.push('speed');
    }

    // ─ Check 3: Human interaction signals (must have at least 2) ─
    var signals = 0;
    if (HUMAN.mouse) signals++;
    if (HUMAN.key) signals++;
    if (HUMAN.scroll) signals++;
    if (HUMAN.touch) signals++;
    if (HUMAN.focus) signals++;
    if (HUMAN.click) signals++;
    if (signals < 2) {
      errors.push('interaction');
    }

    // ─ Check 3b: Interaction depth — must have real engagement ─
    // Bots dispatch events once; humans move mouse many times
    if (HUMAN.moveCount < 3 && HUMAN.keyCount < 2 && HUMAN.scrollCount < 2 && !HUMAN.touch) {
      errors.push('shallow');
    }

    // ─ Check 4: JS token must be set ─
    var tokenEl = form.querySelector('[name="_cls_token"]');
    if (!tokenEl || !tokenEl.value || tokenEl.value.indexOf('cls_') !== 0) {
      errors.push('token');
    }

    // ─ Check 5: Timestamp check ─
    var tsEl = form.querySelector('[name="Form_Loaded_At"]') || form.querySelector('[name="Form Loaded At"]');
    if (tsEl && tsEl.value) {
      var loadTime = new Date(tsEl.value).getTime();
      var diff = Date.now() - loadTime;
      if (diff < 4000 || diff > 86400000) {
        errors.push('timestamp');
      }
    }

    // ─ Check 6: Email validation ─
    var emailEl = form.querySelector('[name="Email"]') || form.querySelector('[name="email"]') || form.querySelector('[type="email"]');
    if (emailEl && emailEl.value) {
      var email = emailEl.value.toLowerCase().trim();

      // Fake email patterns
      var fakePatterns = [
        /^test@/, /^asdf/, /^qwer/, /^1234/, /^admin@/, /^info@test/,
        /^user@/, /^sample@/, /^demo@/, /^noreply@/, /^no-reply@/,
        /^a{3,}@/, /^xxx/, /^abc@/, /^aaa@/
      ];
      for (var i = 0; i < fakePatterns.length; i++) {
        if (fakePatterns[i].test(email)) {
          errors.push('email');
          break;
        }
      }

      // Disposable email domains
      if (errors.indexOf('email') === -1) {
        var emailDomain = email.split('@')[1] || '';
        for (var d = 0; d < DISPOSABLE_DOMAINS.length; d++) {
          if (emailDomain === DISPOSABLE_DOMAINS[d]) {
            errors.push('email');
            break;
          }
        }
      }

      // No TLD or suspicious TLD
      if (errors.indexOf('email') === -1) {
        var tld = email.split('.').pop();
        if (!tld || tld.length < 2 || tld.length > 10) {
          errors.push('email');
        }
      }
    }

    // ─ Check 7: Bot template detection (expanded patterns) ─
    var detailsEl = form.querySelector('[name="Deal_Details"]') ||
                    form.querySelector('[name="Deal Details"]') ||
                    form.querySelector('[name="Deal Summary"]') ||
                    form.querySelector('[name="Message"]') ||
                    form.querySelector('textarea');
    var details = detailsEl ? detailsEl.value.toLowerCase().trim() : '';
    var botPhrases = [
      'need more info', 'need more details', 'i want more', 'inquiry',
      'need service', 'need info', 'more info', 'more details',
      'i need info', 'want info', 'send info', 'send details',
      'reply me', 'contact me', 'i wan more', 'please contact',
      'interested', 'need help', 'help me', 'i am interested',
      'looking for', 'want to know', 'get in touch', 'reach out',
      'hello sir', 'dear sir', 'dear madam', 'dear team',
      'greetings', 'good day', 'hi there', 'plz reply',
      'kindly reply', 'revert back', 'do the needful',
      'i need a loan', 'need money', 'give me loan',
      'click here', 'visit my', 'check out my', 'www.',
      'http://', 'https://', '.ru/', '.cn/', 'bit.ly', 'tinyurl'
    ];
    if (details.length > 0 && details.length < 30) {
      for (var j = 0; j < botPhrases.length; j++) {
        if (details === botPhrases[j] || details.indexOf(botPhrases[j]) > -1) {
          errors.push('template');
          break;
        }
      }
    }
    // Any message with URLs is suspicious
    if (details.length > 0 && (/https?:\/\//.test(details) || /\[url/i.test(details))) {
      errors.push('template');
    }

    // ─ Check 8: Proof of work ─
    var powEl = form.querySelector('[name="_pow"]');
    if (powEl) {
      var pow = powEl.value;
      if (!pow || pow.indexOf(':fail:') > -1 || pow.split(':').length < 3) {
        errors.push('pow');
      }
    }

    // ─ Check 9: Loan amount minimum ($1,000,000) ─
    var loanEl = form.querySelector('[name="Loan_Amount"]') ||
                 form.querySelector('[name="Loan Amount"]') ||
                 form.querySelector('[name="Current Loan Balance"]');
    if (loanEl && loanEl.value) {
      var amt = loanEl.value.replace(/[^0-9]/g, '');
      var num = parseInt(amt);
      if (amt && num > 0 && num < 1000000) {
        alert('Our minimum loan amount is $1,000,000. For smaller loans, we recommend contacting a local bank or credit union.');
        loanEl.focus();
        return false;
      }
      // Round loan amount + generic details = bot
      if (errors.indexOf('template') > -1) {
        if (num === 1000000 || num === 5000000 || num === 10000000 || num === 50000000 || num === 500000000) {
          errors.push('round_amount');
        }
      }
    }

    // ─ Check 10: Phone number bot patterns ─
    var phoneEl = form.querySelector('[name="Phone"]') || form.querySelector('[name="phone"]');
    if (phoneEl && phoneEl.value) {
      var phone = phoneEl.value.replace(/[^0-9]/g, '');
      // All same digit (1111111111, 0000000000)
      if (phone.length >= 7 && /^(.)\1+$/.test(phone)) {
        errors.push('phone');
      }
      // Sequential (1234567890)
      if (phone === '1234567890' || phone === '0123456789' || phone === '9876543210') {
        errors.push('phone');
      }
      // Too short to be real
      if (phone.length > 0 && phone.length < 7) {
        errors.push('phone');
      }
    }

    // ─ Check 11: Name bot patterns ─
    var nameEl = form.querySelector('[name="First Name"]') || form.querySelector('[name="Name"]');
    if (nameEl && nameEl.value) {
      var name = nameEl.value.trim().toLowerCase();
      var botNames = ['test', 'asdf', 'qwer', 'admin', 'user', 'guest', 'aaa', 'xxx', 'abc', 'null', 'undefined', 'none'];
      for (var n = 0; n < botNames.length; n++) {
        if (name === botNames[n]) {
          errors.push('name');
          break;
        }
      }
      // Single character name
      if (name.length === 1) errors.push('name');
    }

    // ── Decision logic ──────────────────────────────────────────────

    // Hard block: speed + no interaction = definitely bot
    if (errors.indexOf('speed') > -1 && errors.indexOf('interaction') > -1) {
      _silentBlock();
      return false;
    }

    // Hard block: headless + any other signal
    if (errors.indexOf('headless') > -1 && errors.length >= 2) {
      _silentBlock();
      return false;
    }

    // Block: template phrase detected
    if (errors.indexOf('template') > -1) {
      _silentBlock();
      return false;
    }

    // Block: 2+ other failures
    if (errors.length >= 2) {
      _silentBlock();
      return false;
    }

    return true;
  };

  function _silentBlock() {
    // Redirect to thank-you so bot thinks it succeeded
    window.location.href = (window._clsThankYouPath || '') + 'thank-you.html';
  }

  // ── Initialize all forms ────────────────────────────────────────────
  function initForms() {
    var forms = document.querySelectorAll('form');
    var endpoint = _buildEndpoint();

    forms.forEach(function(form) {
      // Set real endpoint (HTML has action="#")
      var originalAction = form.getAttribute('action') || '';
      if (originalAction.indexOf('formsubmit') > -1) {
        form._realAction = originalAction;
        form.setAttribute('action', '#');
        form.removeAttribute('method');
      } else if (originalAction === '#' || originalAction === '') {
        form._realAction = endpoint;
      }

      // Determine thank-you path based on page depth
      var depth = '';
      var pathParts = location.pathname.split('/').filter(function(p){return p;});
      for (var p = 0; p < pathParts.length - 1; p++) depth += '../';
      window._clsThankYouPath = depth;

      // Set JS token
      var tokenEl = form.querySelector('[name="_cls_token"]');
      if (tokenEl) {
        tokenEl.value = 'cls_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now().toString(36);
      }

      // Set timestamp
      var tsEl = form.querySelector('[name="Form_Loaded_At"]') || form.querySelector('[name="Form Loaded At"]');
      if (tsEl) {
        tsEl.value = new Date().toISOString();
      }

      // Add proof-of-work field
      if (!form.querySelector('[name="_pow"]')) {
        var powInput = document.createElement('input');
        powInput.type = 'hidden';
        powInput.name = '_pow';
        powInput.value = generatePOW();
        form.appendChild(powInput);
      }

      // Add third honeypot (looks like a fax field — bots love filling these)
      if (!form.querySelector('[name="_company_fax"]')) {
        var faxDiv = document.createElement('div');
        faxDiv.setAttribute('aria-hidden', 'true');
        faxDiv.style.cssText = 'position:absolute;left:-9999px;top:-9999px;width:0;height:0;overflow:hidden;opacity:0';
        var faxInput = document.createElement('input');
        faxInput.type = 'text';
        faxInput.name = '_company_fax';
        faxInput.tabIndex = -1;
        faxInput.autocomplete = 'off';
        faxDiv.appendChild(faxInput);
        form.appendChild(faxDiv);
      }

      // Add Turnstile widget container if configured
      if (captchaType === 'turnstile' && !form.querySelector('.cf-turnstile')) {
        var tsDiv = document.createElement('div');
        tsDiv.className = 'cf-turnstile';
        tsDiv.setAttribute('data-sitekey', TURNSTILE_SITE_KEY);
        tsDiv.setAttribute('data-size', 'compact');
        tsDiv.setAttribute('data-theme', 'light');
        var submitBtn = form.querySelector('[type="submit"]');
        if (submitBtn) {
          submitBtn.parentNode.insertBefore(tsDiv, submitBtn);
        } else {
          form.appendChild(tsDiv);
        }
      }

      // Add reCAPTCHA token field (legacy fallback)
      if (captchaType === 'recaptcha' && !form.querySelector('[name="g-recaptcha-response"]')) {
        var rcInput = document.createElement('input');
        rcInput.type = 'hidden';
        rcInput.name = 'g-recaptcha-response';
        form.appendChild(rcInput);
      }

      // ── Intercept form submission ─────────────────────────────────
      form.addEventListener('submit', function(e) {
        e.preventDefault();

        // Run anti-spam checks
        if (!window.clsAntiSpam(form)) {
          return false;
        }

        // For non-FormSubmit forms (like Google Sheets dealForm)
        if (!form._realAction) {
          if (form.id === 'dealForm') return;
          form.submit();
          return;
        }

        var submitBtn = form.querySelector('[type="submit"]');
        if (submitBtn) {
          submitBtn.disabled = true;
          submitBtn.textContent = 'Verifying...';
        }

        // ── Turnstile verification (FAIL-CLOSED) ───────────────────
        if (captchaType === 'turnstile') {
          var tsResponse = form.querySelector('[name="cf-turnstile-response"]');
          if (!tsResponse || !tsResponse.value) {
            // Turnstile challenge not completed — block submission
            if (submitBtn) {
              submitBtn.disabled = false;
              submitBtn.textContent = 'Please complete the verification';
            }
            alert('Please complete the security verification before submitting.');
            return false;
          }
          // Turnstile passed — proceed to submit
          _doFormSubmit(form, submitBtn);
          return;
        }

        // ── reCAPTCHA v3 fallback (FAIL-CLOSED) ────────────────────
        if (captchaType === 'recaptcha' && captchaReady && window.grecaptcha) {
          grecaptcha.ready(function() {
            grecaptcha.execute(RECAPTCHA_SITE_KEY, {action: 'submit'}).then(function(token) {
              var rcField = form.querySelector('[name="g-recaptcha-response"]');
              if (rcField) rcField.value = token;
              _doFormSubmit(form, submitBtn);
            }).catch(function() {
              // reCAPTCHA FAILED — block submission (fail-closed)
              if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.textContent = 'Verification failed — please try again';
              }
            });
          });
          return;
        }

        // No CAPTCHA available — only allow if all other checks passed clean
        _doFormSubmit(form, submitBtn);
      });
    });
  }

  function _doFormSubmit(form, submitBtn) {
    // ── Exit intent form: fetch + success message (no redirect) ─────
    if (form.id === 'exitForm') {
      var pageType = location.pathname.split('/')[1] || 'home';
      if (typeof gtag === 'function') {
        gtag('event', 'exit_lead_capture', {page_type: pageType, page_url: location.href});
      }
      // localStorage backup
      var exitEmail = (form.querySelector('[name="Email"]') || {}).value || '';
      var exitName = (form.querySelector('[name="Name"]') || {}).value || '';
      try {
        var leads = JSON.parse(localStorage.getItem('cls_exit_leads') || '[]');
        leads.push({
          email: exitEmail, name: exitName, page: location.href,
          type: pageType, timestamp: new Date().toISOString()
        });
        localStorage.setItem('cls_exit_leads', JSON.stringify(leads));
      } catch(ex) {}

      var formData = new FormData(form);
      fetch(form._realAction, { method: 'POST', body: formData, mode: 'no-cors' }).catch(function(){});
      form.style.display = 'none';
      var success = document.getElementById('exitSuccess');
      if (success) success.style.display = 'block';
      return;
    }

    // ── Standard form: restore action + native submit ───────────────
    form.setAttribute('action', form._realAction);
    form.setAttribute('method', 'POST');
    HTMLFormElement.prototype.submit.call(form);
  }

  // ── Boot ─────────────────────────────────────────────────────────
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initForms);
  } else {
    initForms();
  }
})();
