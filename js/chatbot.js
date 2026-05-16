/**
 * CLS CRE Chatbot Widget
 * Floating chat button → panel with Claude-powered conversation + lead capture
 */
(function () {
  'use strict';

  const WORKER_URL = 'https://cls-cre-chatbot.clscre.workers.dev';
  const MAX_MSG = 20;

  // State
  let messages = [];
  let isOpen = false;
  let isLoading = false;
  let leadCaptured = false;

  // --- Build DOM ---
  const wrapper = document.createElement('div');
  wrapper.id = 'cls-chat';
  wrapper.innerHTML = `
    <button id="cls-chat-btn" aria-label="Chat with us">
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
      </svg>
    </button>
    <div id="cls-chat-panel">
      <div id="cls-chat-header">
        <div id="cls-chat-header-left">
          <strong>CLS CRE</strong>
          <span>Commercial Lending Advisor</span>
        </div>
        <button id="cls-chat-close" aria-label="Close chat">&times;</button>
      </div>
      <div id="cls-chat-messages">
        <div class="cls-msg cls-msg-bot">
          <div class="cls-msg-bubble">Welcome to Commercial Lending Solutions. I can help with commercial real estate financing: rates, loan programs, qualification requirements, and more. What can I help you with?</div>
        </div>
        <div class="cls-quick-btns">
          <button class="cls-quick-btn" data-msg="What are current commercial loan rates?">Current Rates</button>
          <button class="cls-quick-btn" data-msg="How do I qualify for a commercial mortgage?">How to Qualify</button>
          <button class="cls-quick-btn" data-msg="I have a deal I'd like to discuss">I Have a Deal</button>
        </div>
      </div>
      <div id="cls-chat-lead" style="display:none">
        <p>Share your info and we'll have an advisor reach out within 24 hours:</p>
        <input type="text" id="cls-lead-name" placeholder="Name *" required>
        <input type="email" id="cls-lead-email" placeholder="Email *" required>
        <input type="tel" id="cls-lead-phone" placeholder="Phone (optional)">
        <button id="cls-lead-submit">Send My Info</button>
        <button id="cls-lead-skip">No thanks, keep chatting</button>
      </div>
      <form id="cls-chat-input">
        <input type="text" id="cls-chat-text" placeholder="Type a message..." autocomplete="off">
        <button type="submit" id="cls-chat-send" aria-label="Send">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
        </button>
      </form>
    </div>
  `;
  document.body.appendChild(wrapper);

  // --- Style ---
  const style = document.createElement('style');
  style.textContent = `
    #cls-chat{position:fixed;bottom:24px;right:24px;z-index:9999;font-family:'Inter',system-ui,sans-serif}
    #cls-chat-btn{width:60px;height:60px;border-radius:50%;background:#153D63;border:none;cursor:pointer;box-shadow:0 4px 16px rgba(0,0,0,.25);display:flex;align-items:center;justify-content:center;transition:transform .2s,box-shadow .2s}
    #cls-chat-btn:hover{transform:scale(1.08);box-shadow:0 6px 24px rgba(0,0,0,.3)}
    #cls-chat-panel{display:none;position:absolute;bottom:72px;right:0;width:380px;max-height:520px;background:#fff;border-radius:16px;box-shadow:0 8px 40px rgba(0,0,0,.18);flex-direction:column;overflow:hidden}
    #cls-chat-panel.open{display:flex}
    #cls-chat-header{background:#153D63;color:#fff;padding:16px 18px;display:flex;align-items:center;justify-content:space-between}
    #cls-chat-header-left{display:flex;flex-direction:column;gap:2px}
    #cls-chat-header-left strong{font-size:15px}
    #cls-chat-header-left span{font-size:12px;opacity:.8}
    #cls-chat-close{background:none;border:none;color:#fff;font-size:24px;cursor:pointer;padding:0 4px;line-height:1}
    #cls-chat-messages{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:12px;min-height:200px;max-height:340px}
    .cls-msg{display:flex}
    .cls-msg-bot{justify-content:flex-start}
    .cls-msg-user{justify-content:flex-end}
    .cls-msg-bubble{max-width:85%;padding:10px 14px;border-radius:12px;font-size:14px;line-height:1.5;word-wrap:break-word}
    .cls-msg-bot .cls-msg-bubble{background:#f0f2f5;color:#1a1a1a;border-bottom-left-radius:4px}
    .cls-msg-user .cls-msg-bubble{background:#153D63;color:#fff;border-bottom-right-radius:4px}
    .cls-msg-typing .cls-msg-bubble{color:#999}
    #cls-chat-input{display:flex;border-top:1px solid #e8e8e8;padding:10px 12px;gap:8px;align-items:center}
    #cls-chat-text{flex:1;border:1px solid #ddd;border-radius:8px;padding:10px 14px;font-size:14px;outline:none;font-family:inherit}
    #cls-chat-text:focus{border-color:#153D63}
    #cls-chat-send{background:#153D63;border:none;border-radius:8px;width:38px;height:38px;display:flex;align-items:center;justify-content:center;cursor:pointer;color:#fff;flex-shrink:0}
    #cls-chat-send:hover{background:#1a4a76}
    #cls-chat-send:disabled{opacity:.5;cursor:default}
    #cls-chat-lead{padding:14px 18px;border-top:1px solid #e8e8e8;background:#fafbfc}
    #cls-chat-lead p{font-size:13px;color:#555;margin:0 0 10px;line-height:1.4}
    #cls-chat-lead input{display:block;width:100%;box-sizing:border-box;border:1px solid #ddd;border-radius:6px;padding:8px 12px;font-size:13px;margin-bottom:8px;font-family:inherit}
    #cls-chat-lead input:focus{border-color:#153D63;outline:none}
    #cls-lead-submit{width:100%;padding:10px;background:#C5A355;color:#fff;border:none;border-radius:6px;font-size:14px;font-weight:600;cursor:pointer;font-family:inherit}
    #cls-lead-submit:hover{background:#b3923d}
    #cls-lead-skip{width:100%;padding:6px;background:none;border:none;color:#888;font-size:12px;cursor:pointer;margin-top:4px}
    .cls-quick-btns{display:flex;gap:6px;padding:0 16px 12px;flex-wrap:wrap}
    .cls-quick-btn{background:#f0f2f5;border:1px solid #ddd;border-radius:16px;padding:6px 14px;font-size:12px;color:#153D63;cursor:pointer;font-family:inherit;font-weight:600;transition:all .15s;white-space:nowrap}
    .cls-quick-btn:hover{background:#153D63;color:#fff;border-color:#153D63}
    .cls-chat-cta{display:block;margin:8px 0;padding:10px 16px;background:#153D63;color:#fff;border-radius:8px;text-decoration:none;font-size:13px;font-weight:600;text-align:center;transition:background .2s}
    .cls-chat-cta:hover{background:#153D63}
    @media(max-width:480px){
      #cls-chat-panel{width:calc(100vw - 32px);right:-8px;bottom:68px;max-height:70vh}
      #cls-chat-btn{width:52px;height:52px}
    }
  `;
  document.head.appendChild(style);

  // --- Elements ---
  const btn = document.getElementById('cls-chat-btn');
  const panel = document.getElementById('cls-chat-panel');
  const closeBtn = document.getElementById('cls-chat-close');
  const msgContainer = document.getElementById('cls-chat-messages');
  const form = document.getElementById('cls-chat-input');
  const textInput = document.getElementById('cls-chat-text');
  const sendBtn = document.getElementById('cls-chat-send');
  const leadPanel = document.getElementById('cls-chat-lead');
  const leadSubmit = document.getElementById('cls-lead-submit');
  const leadSkip = document.getElementById('cls-lead-skip');

  // --- Toggle ---
  btn.addEventListener('click', () => {
    isOpen = !isOpen;
    panel.classList.toggle('open', isOpen);
    if (isOpen) textInput.focus();
  });
  closeBtn.addEventListener('click', () => {
    isOpen = false;
    panel.classList.remove('open');
  });

  // --- Chat ---
  function addMessage(role, text) {
    const div = document.createElement('div');
    div.className = 'cls-msg ' + (role === 'user' ? 'cls-msg-user' : 'cls-msg-bot');
    div.innerHTML = '<div class="cls-msg-bubble">' + escapeHtml(text) + '</div>';
    msgContainer.appendChild(div);
    msgContainer.scrollTop = msgContainer.scrollHeight;
  }

  function showTyping() {
    const div = document.createElement('div');
    div.className = 'cls-msg cls-msg-bot cls-msg-typing';
    div.id = 'cls-typing';
    div.innerHTML = '<div class="cls-msg-bubble">Typing...</div>';
    msgContainer.appendChild(div);
    msgContainer.scrollTop = msgContainer.scrollHeight;
  }

  function removeTyping() {
    const el = document.getElementById('cls-typing');
    if (el) el.remove();
  }

  function escapeHtml(str) {
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
  }

  async function sendMessage(text) {
    if (isLoading || !text.trim()) return;
    isLoading = true;
    sendBtn.disabled = true;

    addMessage('user', text);
    messages.push({ role: 'user', content: text });

    // Trim to last MAX_MSG messages
    if (messages.length > MAX_MSG) messages = messages.slice(-MAX_MSG);

    showTyping();

    try {
      const res = await fetch(WORKER_URL + '/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: messages }),
      });
      const data = await res.json();
      removeTyping();

      const reply = data.reply || 'I apologize for the technical difficulty. Please call us at 310.708.0690.';
      addMessage('assistant', reply);
      messages.push({ role: 'assistant', content: reply });

      // Show lead form based on engagement signals
      const userMsgCount = messages.filter(m => m.role === 'user').length;
      const allUserText = messages.filter(m => m.role === 'user').map(m => m.content.toLowerCase()).join(' ');
      const hasDealIntent = /deal|property|loan|refinance|bridge|acquisition|purchase|million|\$|closing|lender|rate|quote|apply/i.test(allUserText);
      if (!leadCaptured && (userMsgCount >= 4 || (userMsgCount >= 2 && hasDealIntent))) {
        showLeadForm();
      }
    } catch (err) {
      removeTyping();
      addMessage('assistant', 'I apologize for the technical difficulty. Please call us at 310.708.0690 or visit our contact page.');
    }

    isLoading = false;
    sendBtn.disabled = false;
  }

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const text = textInput.value.trim();
    if (!text) return;
    textInput.value = '';
    sendMessage(text);
  });

  // Quick-reply buttons
  document.querySelectorAll('.cls-quick-btn').forEach(btn => {
    btn.addEventListener('click', function() {
      const msg = this.getAttribute('data-msg');
      // Hide quick buttons after first click
      const container = document.querySelector('.cls-quick-btns');
      if (container) container.style.display = 'none';
      sendMessage(msg);
    });
  });

  // --- Lead Capture ---
  function showLeadForm() {
    leadPanel.style.display = 'block';
    form.style.display = 'none';
  }

  function hideLeadForm() {
    leadPanel.style.display = 'none';
    form.style.display = 'flex';
    textInput.focus();
  }

  leadSkip.addEventListener('click', () => {
    leadCaptured = true;
    hideLeadForm();
  });

  leadSubmit.addEventListener('click', async () => {
    const name = document.getElementById('cls-lead-name').value.trim();
    const email = document.getElementById('cls-lead-email').value.trim();
    const phone = document.getElementById('cls-lead-phone').value.trim();

    if (!name || !email) {
      alert('Please enter your name and email.');
      return;
    }

    leadSubmit.disabled = true;
    leadSubmit.textContent = 'Sending...';

    // Build deal summary from conversation
    const deal = messages.filter(m => m.role === 'user').map(m => m.content).join(' | ');

    try {
      await fetch(WORKER_URL + '/lead', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email, phone, deal }),
      });

      leadCaptured = true;
      hideLeadForm();
      addMessage('assistant', 'Thank you, ' + name + '! A Commercial Lending Solutions advisor will reach out within 24 hours. In the meantime, you can apply directly at clscre.com/apply.html or call us at 310.708.0690.');

      // GA4 event
      if (typeof gtag === 'function') {
        gtag('event', 'generate_lead', { event_category: 'chatbot', event_label: 'lead_capture' });
      }
    } catch (err) {
      leadSubmit.disabled = false;
      leadSubmit.textContent = 'Send My Info';
      addMessage('assistant', 'There was an issue submitting your info. Please try our contact page or call 310.708.0690.');
      hideLeadForm();
    }
  });
})();

/* ============================================================================
 * CLS CRE Contact Enhancements (Phase 5B)
 * Runs on every page that loads chatbot.js (i.e. every page).
 * Adds:
 *   1. Sticky mobile contact bar (phone + book call) below 768px
 *   2. URL-param prefill for contact forms (?name=X&email=Y&phone=Z&message=M)
 *   3. Exit-intent fallback popup pointing users to call/book/email
 *   4. Inline "Text Trevor" SMS link next to existing phone links on mobile
 * Privacy: no tracking beyond existing GTM; no third-party requests.
 * ========================================================================== */
(function () {
  'use strict';
  try {
    var PHONE = '+13107080690';
    var PHONE_DISPLAY = '310.708.0690';
    var EMAIL = 'loans@clscre.com';
    var BOOKING = 'https://outlook.office.com/bookwithme/user/c760895536d64481bd17039efdcead26@clscre.com?anonymous&ismsaljsauthenabled&ep=plink';

    // ── 1) Sticky mobile contact bar ──────────────────────────────────────
    function injectMobileBar() {
      if (document.getElementById('cls-mcb')) return;
      var bar = document.createElement('div');
      bar.id = 'cls-mcb';
      bar.innerHTML = ''
        + '<a href="tel:' + PHONE + '" class="cls-mcb-btn cls-mcb-primary" aria-label="Call Trevor at ' + PHONE_DISPLAY + '">'
        +   '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/></svg>'
        +   '<span>Call</span>'
        + '</a>'
        + '<a href="sms:' + PHONE + '" class="cls-mcb-btn cls-mcb-secondary" aria-label="Text Trevor at ' + PHONE_DISPLAY + '">'
        +   '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>'
        +   '<span>Text</span>'
        + '</a>'
        + '<a href="' + BOOKING + '" target="_blank" rel="noopener" class="cls-mcb-btn cls-mcb-secondary" aria-label="Book a 15-min call with Trevor">'
        +   '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>'
        +   '<span>Book</span>'
        + '</a>';

      var style = document.createElement('style');
      style.textContent = ''
        + '#cls-mcb{position:fixed;left:0;right:0;bottom:0;display:none;grid-template-columns:2fr 1fr 1fr;gap:8px;padding:10px 12px 14px;background:#153D63;box-shadow:0 -4px 24px rgba(0,0,0,.18);z-index:998}'
        + '@media (max-width:768px){#cls-mcb{display:grid}body{padding-bottom:72px !important}}'
        + '#cls-mcb .cls-mcb-btn{display:flex;align-items:center;justify-content:center;gap:6px;height:44px;border-radius:8px;font-size:14px;font-weight:700;text-decoration:none;letter-spacing:.2px}'
        + '#cls-mcb .cls-mcb-primary{background:#00A676;color:#fff}'
        + '#cls-mcb .cls-mcb-secondary{background:rgba(255,255,255,.1);color:#fff;border:1px solid rgba(255,255,255,.25)}'
        + '#cls-mcb .cls-mcb-btn:active{opacity:.85}'
        // Nudge the floating chatbot button up so it doesn't collide with the bar
        + '@media (max-width:768px){#cls-chat-btn{bottom:88px !important}}';
      document.head.appendChild(style);
      document.body.appendChild(bar);
    }

    // ── 2) URL-param prefill for contact forms ────────────────────────────
    // Supports: ?name=X&email=Y&phone=Z&message=M&inquiry=Affordable%2FEDI
    function prefillFromParams() {
      var params = new URLSearchParams(location.search);
      if (!params.toString()) return;
      var mapping = {
        'name': ['Name', 'name', 'first_name', 'c_name'],
        'email': ['Email', 'email', 'c_email'],
        'phone': ['Phone', 'phone', 'c_phone'],
        'message': ['Message', 'message', 'details', 'c_message'],
        'inquiry': ['Inquiry Type', 'c_deal_type']
      };
      Object.keys(mapping).forEach(function (paramKey) {
        var val = params.get(paramKey);
        if (!val) return;
        mapping[paramKey].forEach(function (fieldName) {
          // Try by name=, then by id=
          var el = document.querySelector('[name="' + fieldName + '"]') ||
                   document.getElementById(fieldName);
          if (el && !el.value) {
            el.value = val;
            try { el.dispatchEvent(new Event('input', {bubbles: true})); } catch (e) {}
          }
        });
      });
    }

    // ── 3) Exit-intent fallback popup (desktop-only, once per session) ────
    function setupExitIntent() {
      if (sessionStorage.getItem('cls-exit-shown')) return;
      if (location.pathname.indexOf('thank-you') > -1) return; // don't show on thank-you
      var shown = false;
      document.addEventListener('mouseleave', function (e) {
        if (shown || e.clientY > 10) return;
        if (window.innerWidth < 768) return; // skip mobile
        shown = true;
        sessionStorage.setItem('cls-exit-shown', '1');
        showExitPopup();
      });
    }

    function showExitPopup() {
      var overlay = document.createElement('div');
      overlay.id = 'cls-exit-overlay';
      overlay.innerHTML = ''
        + '<div class="cls-exit-card" role="dialog" aria-labelledby="cls-exit-title">'
        +   '<button class="cls-exit-close" aria-label="Close">&times;</button>'
        +   '<div class="cls-exit-label">Before you go</div>'
        +   '<h3 id="cls-exit-title">Questions about your deal?</h3>'
        +   '<p>Trevor personally reviews every inquiry. Call, text, book a time, or email, whichever is easiest.</p>'
        +   '<div class="cls-exit-actions">'
        +     '<a href="tel:' + PHONE + '">Call ' + PHONE_DISPLAY + '</a>'
        +     '<a href="' + BOOKING + '" target="_blank" rel="noopener">Book 15 min</a>'
        +     '<a href="mailto:' + EMAIL + '">Email Trevor</a>'
        +   '</div>'
        + '</div>';
      var style = document.createElement('style');
      style.textContent = ''
        + '#cls-exit-overlay{position:fixed;inset:0;background:rgba(21,61,99,.55);display:flex;align-items:center;justify-content:center;z-index:9999;padding:20px;animation:clsFade .22s ease}'
        + '@keyframes clsFade{from{opacity:0}to{opacity:1}}'
        + '#cls-exit-overlay .cls-exit-card{background:#fff;border-radius:14px;padding:36px 40px 32px;max-width:480px;width:100%;position:relative;box-shadow:0 20px 60px rgba(0,0,0,.25);font-family:inherit}'
        + '#cls-exit-overlay .cls-exit-close{position:absolute;top:12px;right:16px;background:none;border:none;font-size:28px;color:#888;cursor:pointer;line-height:1}'
        + '#cls-exit-overlay .cls-exit-label{font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#006A4E;font-weight:700;margin-bottom:8px}'
        + '#cls-exit-overlay .cls-exit-card h3{font-family:DM Serif Display,serif;font-size:26px;color:#153D63;margin:0 0 10px;line-height:1.2}'
        + '#cls-exit-overlay .cls-exit-card p{font-size:14px;color:#555;line-height:1.6;margin:0 0 22px}'
        + '#cls-exit-overlay .cls-exit-actions{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}'
        + '#cls-exit-overlay .cls-exit-actions a{display:flex;align-items:center;justify-content:center;padding:12px 10px;border-radius:8px;font-size:13px;font-weight:700;text-decoration:none}'
        + '#cls-exit-overlay .cls-exit-actions a:nth-child(1){background:#006A4E;color:#fff}'
        + '#cls-exit-overlay .cls-exit-actions a:nth-child(2){background:#153D63;color:#fff}'
        + '#cls-exit-overlay .cls-exit-actions a:nth-child(3){background:#f3f4f6;color:#153D63}'
        + '@media (max-width:480px){#cls-exit-overlay .cls-exit-actions{grid-template-columns:1fr}}';
      document.head.appendChild(style);
      document.body.appendChild(overlay);
      overlay.querySelector('.cls-exit-close').addEventListener('click', function () {
        overlay.remove();
      });
      overlay.addEventListener('click', function (e) {
        if (e.target === overlay) overlay.remove();
      });
      if (typeof gtag === 'function') {
        try { gtag('event', 'exit_popup_shown', {page_url: location.href}); } catch (e) {}
      }
    }

    // ── Run on DOM ready ─────────────────────────────────────────────────
    function ready() {
      injectMobileBar();
      prefillFromParams();
      setupExitIntent();
    }
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', ready);
    } else {
      ready();
    }
  } catch (err) {
    try { console.warn('CLS contact enhancements failed:', err); } catch (e) {}
  }
})();
