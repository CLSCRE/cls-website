/**
 * CLS CRE Anti-Spam Protection v2
 * Hides form endpoints from bots. Forms only work via JavaScript.
 * Includes Google reCAPTCHA v3 (invisible, score-based).
 */
(function() {
  'use strict';

  var RECAPTCHA_SITE_KEY = '6LeB3JMsAAAAAKwoYS1jZKGPfsqVcl3IjVidDWZw';
  var recaptchaReady = false;

  // The form endpoint — ONLY exists in JavaScript, never in HTML
  // Bots scraping HTML will find action="#" (nowhere to submit)
  var _ep = [109,97,105,108,116,111,58,105,110,113,117,105,114,105,101,115,64,99,108,115,99,114,101,46,99,111,109];
  var _fs = [104,116,116,112,115,58,47,47,102,111,114,109,115,117,98,109,105,116,46,99,111,47];
  function _d(a){return a.map(function(c){return String.fromCharCode(c)}).join('')}

  // Load reCAPTCHA v3 script
  var rcScript = document.createElement('script');
  rcScript.src = 'https://www.google.com/recaptcha/api.js?render=' + RECAPTCHA_SITE_KEY;
  rcScript.async = true;
  rcScript.defer = true;
  rcScript.onload = function() { recaptchaReady = true; };
  document.head.appendChild(rcScript);

  var HUMAN_SIGNALS = {
    mouseMoved: false,
    keyPressed: false,
    scrolled: false,
    touched: false,
    focused: false,
    timeLoaded: Date.now()
  };

  document.addEventListener('mousemove', function() { HUMAN_SIGNALS.mouseMoved = true; }, { once: true });
  document.addEventListener('keydown', function() { HUMAN_SIGNALS.keyPressed = true; }, { once: true });
  document.addEventListener('scroll', function() { HUMAN_SIGNALS.scrolled = true; }, { once: true });
  document.addEventListener('touchstart', function() { HUMAN_SIGNALS.touched = true; }, { once: true });
  document.addEventListener('focusin', function() { HUMAN_SIGNALS.focused = true; }, { once: true });

  function generatePOW() {
    var nonce = 0;
    var ts = Date.now().toString(36);
    while (nonce < 100000) {
      var check = ts + ':' + nonce;
      var hash = 0;
      for (var i = 0; i < check.length; i++) {
        hash = ((hash << 5) - hash) + check.charCodeAt(i);
        hash |= 0;
      }
      if ((Math.abs(hash) % 100) === 0) {
        return ts + ':' + nonce + ':' + hash;
      }
      nonce++;
    }
    return ts + ':fail:0';
  }

  // Validate form submission
  window.clsAntiSpam = function(form) {
    var errors = [];

    // Check 1: Honeypot fields
    var honey1 = form.querySelector('[name="_honey"]');
    var honey2 = form.querySelector('[name="website_url"]');
    if ((honey1 && honey1.value) || (honey2 && honey2.value)) {
      window.location.href = 'thank-you.html';
      return false;
    }

    // Check 2: Time-based (must spend at least 4 seconds on page)
    var elapsed = (Date.now() - HUMAN_SIGNALS.timeLoaded) / 1000;
    if (elapsed < 4) {
      errors.push('speed');
    }

    // Check 3: Human interaction signals (must have at least 2)
    var signals = 0;
    if (HUMAN_SIGNALS.mouseMoved) signals++;
    if (HUMAN_SIGNALS.keyPressed) signals++;
    if (HUMAN_SIGNALS.scrolled) signals++;
    if (HUMAN_SIGNALS.touched) signals++;
    if (HUMAN_SIGNALS.focused) signals++;
    if (signals < 2) {
      errors.push('interaction');
    }

    // Check 4: JS token must be set
    var tokenEl = form.querySelector('[name="_cls_token"]');
    if (!tokenEl || !tokenEl.value || !tokenEl.value.startsWith('cls_')) {
      errors.push('token');
    }

    // Check 5: Timestamp check
    var tsEl = form.querySelector('[name="Form_Loaded_At"]') || form.querySelector('[name="Form Loaded At"]');
    if (tsEl && tsEl.value) {
      var loadTime = new Date(tsEl.value).getTime();
      var diff = Date.now() - loadTime;
      if (diff < 3000 || diff > 86400000) {
        errors.push('timestamp');
      }
    }

    // Check 6: Email validation
    var emailEl = form.querySelector('[name="Email"]') || form.querySelector('[name="email"]') || form.querySelector('[type="email"]');
    if (emailEl && emailEl.value) {
      var email = emailEl.value.toLowerCase();
      var fakePatterns = [/^test@/, /^asdf/, /^qwer/, /^1234/, /@mailinator/, /@guerrillamail/, /@tempmail/, /@throwaway/, /@fake/, /@noemail/];
      for (var i = 0; i < fakePatterns.length; i++) {
        if (fakePatterns[i].test(email)) {
          errors.push('email');
          break;
        }
      }
    }

    // Check 7: Bot template detection (expanded patterns)
    var detailsEl = form.querySelector('[name="Deal_Details"]') || form.querySelector('[name="Deal Details"]') || form.querySelector('[name="Deal Summary"]') || form.querySelector('textarea');
    var details = detailsEl ? detailsEl.value.toLowerCase().trim() : '';
    var botPhrases = ['need more info', 'need more details', 'i want more', 'inquiry', 'need service', 'need info', 'more info', 'more details', 'i need info', 'want info', 'send info', 'send details', 'reply me', 'contact me', 'i wan more'];
    if (details.length > 0 && details.length < 20) {
      for (var j = 0; j < botPhrases.length; j++) {
        if (details === botPhrases[j] || details.indexOf(botPhrases[j]) > -1) {
          errors.push('template');
          break;
        }
      }
    }

    // Check 8: Proof of work
    var powEl = form.querySelector('[name="_pow"]');
    if (powEl) {
      var pow = powEl.value;
      if (!pow || pow.indexOf(':fail:') > -1 || pow.split(':').length < 3) {
        errors.push('pow');
      }
    }

    // Check 9: Round loan amount + generic details = bot
    var loanEl = form.querySelector('[name="Loan_Amount"]') || form.querySelector('[name="Loan Amount"]');
    if (loanEl && loanEl.value && errors.indexOf('template') > -1) {
      var amt = loanEl.value.replace(/[^0-9]/g, '');
      var num = parseInt(amt);
      if (num === 1000000 || num === 5000000 || num === 10000000 || num === 50000000 || num === 500000000) {
        errors.push('round_amount');
      }
    }

    // Hard block: speed + no interaction = definitely bot
    if (errors.indexOf('speed') > -1 && errors.indexOf('interaction') > -1) {
      window.location.href = 'thank-you.html';
      return false;
    }

    // Block: template phrase detected (high confidence bot signal)
    if (errors.indexOf('template') > -1) {
      window.location.href = 'thank-you.html';
      return false;
    }

    // Block: 2+ other failures
    if (errors.length >= 2) {
      window.location.href = 'thank-you.html';
      return false;
    }

    return true;
  };

  // Initialize all forms
  function initForms() {
    var forms = document.querySelectorAll('form');
    forms.forEach(function(form) {
      // CRITICAL: Strip the FormSubmit URL from HTML and store it
      // Bots scraping HTML will find action="#" — nowhere to submit
      var originalAction = form.getAttribute('action') || '';
      if (originalAction.indexOf('formsubmit') > -1) {
        form._realAction = originalAction;
        form.setAttribute('action', '#');
        form.removeAttribute('method');
      }

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

      // Add reCAPTCHA token field
      if (!form.querySelector('[name="g-recaptcha-response"]')) {
        var rcInput = document.createElement('input');
        rcInput.type = 'hidden';
        rcInput.name = 'g-recaptcha-response';
        form.appendChild(rcInput);
      }

      // Intercept form submission
      form.addEventListener('submit', function(e) {
        e.preventDefault();

        // Run anti-spam checks
        if (!window.clsAntiSpam(form)) {
          return false;
        }

        // For non-FormSubmit forms (like Google Sheets dealForm), let their handler run
        if (!form._realAction) {
          // Trigger native submit for JS-handled forms
          if (form.id === 'dealForm') return;
          form.submit();
          return;
        }

        var submitBtn = form.querySelector('[type="submit"]');
        if (submitBtn) {
          submitBtn.disabled = true;
          submitBtn.textContent = 'Verifying...';
        }

        // Function to actually submit the form
        function doSubmit() {
          // Restore the real action URL right before submission
          form.setAttribute('action', form._realAction);
          form.setAttribute('method', 'POST');
          // Use native submit to bypass our listener
          HTMLFormElement.prototype.submit.call(form);
        }

        // Get reCAPTCHA token first if available
        if (recaptchaReady && window.grecaptcha) {
          grecaptcha.ready(function() {
            grecaptcha.execute(RECAPTCHA_SITE_KEY, {action: 'submit'}).then(function(token) {
              var rcField = form.querySelector('[name="g-recaptcha-response"]');
              if (rcField) rcField.value = token;
              doSubmit();
            }).catch(function() {
              doSubmit(); // Submit anyway if reCAPTCHA fails
            });
          });
        } else {
          doSubmit();
        }
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initForms);
  } else {
    initForms();
  }
})();
