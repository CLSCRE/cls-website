/**
 * CLS CRE Chatbot Widget
 * Floating chat button → panel with Claude-powered conversation + lead capture
 */
(function () {
  'use strict';

  const WORKER_URL = 'https://cls-cre-chatbot.tdamyan.workers.dev';
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
          <div class="cls-msg-bubble">Welcome to Commercial Lending Solutions. I can answer questions about commercial real estate financing, loan programs, and more. How can I help you today?</div>
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

      const reply = data.reply || 'I apologize for the technical difficulty. Please call us at 310.758.4042.';
      addMessage('assistant', reply);
      messages.push({ role: 'assistant', content: reply });

      // Show lead form after 4+ exchanges if not captured
      if (!leadCaptured && messages.filter(m => m.role === 'user').length >= 4) {
        showLeadForm();
      }
    } catch (err) {
      removeTyping();
      addMessage('assistant', 'I apologize for the technical difficulty. Please call us at 310.758.4042 or visit our contact page.');
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
      addMessage('assistant', 'Thank you, ' + name + '. A CLS CRE advisor will reach out within 24 hours. Feel free to keep chatting or call us at 310.758.4042.');

      // GA4 event
      if (typeof gtag === 'function') {
        gtag('event', 'generate_lead', { event_category: 'chatbot', event_label: 'lead_capture' });
      }
    } catch (err) {
      leadSubmit.disabled = false;
      leadSubmit.textContent = 'Send My Info';
      addMessage('assistant', 'There was an issue submitting your info. Please try our contact page or call 310.758.4042.');
      hideLeadForm();
    }
  });
})();
