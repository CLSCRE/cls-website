/**
 * CLS CRE Anti-Spam Protection
 * Blocks bots with multiple layered checks that real users pass automatically.
 */
(function() {
  'use strict';

  var HUMAN_SIGNALS = {
    mouseMoved: false,
    keyPressed: false,
    scrolled: false,
    touched: false,
    focused: false,
    timeLoaded: Date.now()
  };

  // Track human interaction signals
  document.addEventListener('mousemove', function() { HUMAN_SIGNALS.mouseMoved = true; }, { once: true });
  document.addEventListener('keydown', function() { HUMAN_SIGNALS.keyPressed = true; }, { once: true });
  document.addEventListener('scroll', function() { HUMAN_SIGNALS.scrolled = true; }, { once: true });
  document.addEventListener('touchstart', function() { HUMAN_SIGNALS.touched = true; }, { once: true });
  document.addEventListener('focusin', function() { HUMAN_SIGNALS.focused = true; }, { once: true });

  // Generate proof-of-work challenge (lightweight, invisible to users)
  function generatePOW() {
    var nonce = 0;
    var ts = Date.now().toString(36);
    // Find a nonce where hash starts with '00' (trivial for browsers, hard to mass-produce for bots)
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

    // Check 1: Honeypot fields (two of them)
    var honey1 = form.querySelector('[name="_honey"]');
    var honey2 = form.querySelector('[name="website_url"]');
    if ((honey1 && honey1.value) || (honey2 && honey2.value)) {
      // Silent redirect — don't tell the bot it failed
      window.location.href = 'thank-you.html';
      return false;
    }

    // Check 2: Time-based (must spend at least 3 seconds on page)
    var elapsed = (Date.now() - HUMAN_SIGNALS.timeLoaded) / 1000;
    if (elapsed < 3) {
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

    // Check 4: JS token must be set (proves JS executed)
    var tokenEl = form.querySelector('[name="_cls_token"]');
    if (!tokenEl || !tokenEl.value || !tokenEl.value.startsWith('cls_')) {
      errors.push('token');
    }

    // Check 5: Timestamp check (form must have been on page)
    var tsEl = form.querySelector('[name="Form_Loaded_At"]') || form.querySelector('[name="Form Loaded At"]');
    if (tsEl && tsEl.value) {
      var loadTime = new Date(tsEl.value).getTime();
      var diff = Date.now() - loadTime;
      if (diff < 2000 || diff > 86400000) { // less than 2s or more than 24h
        errors.push('timestamp');
      }
    }

    // Check 6: Email validation (block obvious fake patterns)
    var emailEl = form.querySelector('[name="Email"]') || form.querySelector('[name="email"]') || form.querySelector('[type="email"]');
    if (emailEl && emailEl.value) {
      var email = emailEl.value.toLowerCase();
      // Block disposable/fake email patterns
      var fakePatterns = [/^test@/, /^asdf/, /^qwer/, /^1234/, /@mailinator/, /@guerrillamail/, /@tempmail/, /@throwaway/, /@fake/];
      for (var i = 0; i < fakePatterns.length; i++) {
        if (fakePatterns[i].test(email)) {
          errors.push('email');
          break;
        }
      }
    }

    // Check 7: Loan amount sanity (block round suspicious amounts)
    var loanEl = form.querySelector('[name="Loan_Amount"]') || form.querySelector('[name="Loan Amount"]');
    if (loanEl && loanEl.value) {
      var amount = loanEl.value.replace(/[^0-9]/g, '');
      var num = parseInt(amount);
      // If exactly $1,000,000 or $5,000,000 with "Need more info" as details, likely bot
      var detailsEl = form.querySelector('[name="Deal_Details"]') || form.querySelector('[name="Deal Details"]') || form.querySelector('[name="Deal Summary"]');
      var details = detailsEl ? detailsEl.value.toLowerCase().trim() : '';
      if (details.length < 10 && (details === 'need more info' || details === 'need more details' || details === 'i want more' || details === 'inquiry')) {
        // Check if other fields also look templated
        var phone = form.querySelector('[name="Phone"]') || form.querySelector('[name="phone"]');
        if (phone && phone.value && elapsed < 30) {
          errors.push('template');
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

    // If any hard failures, silently redirect (don't educate the bot)
    if (errors.indexOf('speed') > -1 && errors.indexOf('interaction') > -1) {
      window.location.href = 'thank-you.html';
      return false;
    }

    // If 2+ soft failures, block
    if (errors.length >= 2) {
      window.location.href = 'thank-you.html';
      return false;
    }

    return true; // Human — allow submission
  };

  // Initialize all forms on page load
  function initForms() {
    var forms = document.querySelectorAll('form');
    forms.forEach(function(form) {
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

      // Add proof-of-work field if not present
      if (!form.querySelector('[name="_pow"]')) {
        var powInput = document.createElement('input');
        powInput.type = 'hidden';
        powInput.name = '_pow';
        powInput.value = generatePOW();
        form.appendChild(powInput);
      }

      // Add anti-spam check to form submission
      form.addEventListener('submit', function(e) {
        if (!window.clsAntiSpam(form)) {
          e.preventDefault();
          return false;
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
