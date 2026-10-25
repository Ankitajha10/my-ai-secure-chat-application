/**
 * My AI – Secure LLM Chat Application Frontend Controller
 * Vanilla JavaScript with Persistent Conversation History,
 * Date-Grouped Sidebar, Multi-Turn Context, and Rich Markdown Rendering.
 */

(function () {
  'use strict';

  // --- Storage Keys ---
  const STORAGE_TOKEN_KEY = 'my_ai_access_token';
  const STORAGE_USER_KEY = 'my_ai_username';
  const STORAGE_ROLE_KEY = 'my_ai_role';
  const STORAGE_ACTIVE_CONV_KEY = 'my_ai_active_conv_id';

  // --- DOM Elements ---
  const authView = document.getElementById('auth-view');
  const chatView = document.getElementById('chat-view');
  const authAlert = document.getElementById('auth-alert');
  const loginForm = document.getElementById('login-form');
  const signupForm = document.getElementById('signup-form');
  const gotoSignupLink = document.getElementById('goto-signup-link');
  const gotoLoginLink = document.getElementById('goto-login-link');
  const loginBtn = document.getElementById('login-btn');
  const signupBtn = document.getElementById('signup-btn');

  // Chat DOM Elements
  const headerAvatar = document.getElementById('header-avatar');
  const headerUsername = document.getElementById('header-username');
  const headerRole = document.getElementById('header-role');
  const adminVerifyBtn = document.getElementById('admin-verify-btn');
  const logoutBtn = document.getElementById('logout-btn');
  const chatMessages = document.getElementById('chat-messages');
  const welcomeBox = document.getElementById('welcome-box');
  const chatInput = document.getElementById('chat-input');
  const sendBtn = document.getElementById('send-btn');
  const chatErrorToast = document.getElementById('chat-error');

  // Image Upload & Preview DOM Elements
  const attachBtn = document.getElementById('attach-btn');
  const imageFileInput = document.getElementById('image-file-input');
  const imagePreviewContainer = document.getElementById('image-preview-container');
  const imagePreviewThumb = document.getElementById('image-preview-thumb');
  const imagePreviewName = document.getElementById('image-preview-name');
  const imagePreviewSize = document.getElementById('image-preview-size');
  const imagePreviewRemove = document.getElementById('image-preview-remove');

  // Sidebar Elements
  const chatSidebar = document.getElementById('chat-sidebar');
  const sidebarOverlay = document.getElementById('sidebar-overlay');
  const sidebarToggleBtn = document.getElementById('sidebar-toggle-btn');
  const sidebarCloseBtn = document.getElementById('sidebar-close-btn');
  const newChatBtn = document.getElementById('new-chat-btn');
  const historyContainer = document.getElementById('history-container');

  // --- State Management ---
  let isGenerating = false;
  let activeConversationId = null;
  let selectedImageFile = null;

  function getToken() {
    return sessionStorage.getItem(STORAGE_TOKEN_KEY);
  }

  function getUsername() {
    return sessionStorage.getItem(STORAGE_USER_KEY);
  }

  function getRole() {
    return sessionStorage.getItem(STORAGE_ROLE_KEY);
  }

  function setSession(token, username, role) {
    sessionStorage.setItem(STORAGE_TOKEN_KEY, token);
    sessionStorage.setItem(STORAGE_USER_KEY, username);
    sessionStorage.setItem(STORAGE_ROLE_KEY, role || 'user');
  }

  function clearSession() {
    sessionStorage.removeItem(STORAGE_TOKEN_KEY);
    sessionStorage.removeItem(STORAGE_USER_KEY);
    sessionStorage.removeItem(STORAGE_ROLE_KEY);
    sessionStorage.removeItem(STORAGE_ACTIVE_CONV_KEY);
    activeConversationId = null;
  }

  // --- UI View Switching ---
  function showAuthView() {
    chatView.classList.add('hidden');
    authView.classList.remove('hidden');
    loginForm.classList.remove('hidden');
    signupForm.classList.add('hidden');
    hideAuthAlert();
  }

  function showChatView() {
    authView.classList.add('hidden');
    chatView.classList.remove('hidden');

    const username = getUsername() || 'User';
    const role = getRole() || 'user';

    headerUsername.textContent = username;
    headerAvatar.textContent = username.charAt(0).toUpperCase();
    headerRole.textContent = role;

    if (role === 'admin') {
      headerRole.classList.add('role-admin');
      adminVerifyBtn.classList.remove('hidden');
    } else {
      headerRole.classList.remove('role-admin');
      adminVerifyBtn.classList.add('hidden');
    }

    // Load conversation history and restore previous active conversation
    loadConversations().then(() => {
      const savedConvId = sessionStorage.getItem(STORAGE_ACTIVE_CONV_KEY);
      if (savedConvId) {
        selectConversation(parseInt(savedConvId, 10));
      } else {
        startNewChat();
      }
    });

    chatInput.focus();
  }

  // --- Alerts & Toast Helpers ---
  function showAuthAlert(message, type = 'danger') {
    authAlert.textContent = message;
    authAlert.className = `alert alert-${type}`;
    authAlert.classList.remove('hidden');
  }

  function hideAuthAlert() {
    authAlert.classList.add('hidden');
    authAlert.textContent = '';
  }

  let toastTimer = null;
  function showToast(message, isError = true) {
    if (toastTimer) clearTimeout(toastTimer);
    chatErrorToast.textContent = message;
    chatErrorToast.style.backgroundColor = isError ? '#7f1d1d' : '#065f46';
    chatErrorToast.style.borderColor = isError ? '#ef4444' : '#10b981';
    chatErrorToast.style.color = isError ? '#fecaca' : '#d1fae5';
    chatErrorToast.classList.remove('hidden');

    toastTimer = setTimeout(() => {
      chatErrorToast.classList.add('hidden');
    }, 5000);
  }

  // --- Button Loading Helpers ---
  function setBtnLoading(btn, isLoading) {
    const textSpan = btn.querySelector('.btn-text');
    const spinner = btn.querySelector('.btn-spinner');
    if (isLoading) {
      btn.disabled = true;
      if (textSpan) textSpan.classList.add('hidden');
      if (spinner) spinner.classList.remove('hidden');
    } else {
      btn.disabled = false;
      if (textSpan) textSpan.classList.remove('hidden');
      if (spinner) spinner.classList.add('hidden');
    }
  }

  // --- Mobile Sidebar Toggle ---
  function openMobileSidebar() {
    chatSidebar.classList.add('open');
    sidebarOverlay.classList.remove('hidden');
  }

  function closeMobileSidebar() {
    chatSidebar.classList.remove('open');
    sidebarOverlay.classList.add('hidden');
  }

  if (sidebarToggleBtn) sidebarToggleBtn.addEventListener('click', openMobileSidebar);
  if (sidebarCloseBtn) sidebarCloseBtn.addEventListener('click', closeMobileSidebar);
  if (sidebarOverlay) sidebarOverlay.addEventListener('click', closeMobileSidebar);

  // --- Authentication Handlers ---
  gotoSignupLink.addEventListener('click', (e) => {
    e.preventDefault();
    hideAuthAlert();
    loginForm.classList.add('hidden');
    signupForm.classList.remove('hidden');
    document.getElementById('signup-username').focus();
  });

  gotoLoginLink.addEventListener('click', (e) => {
    e.preventDefault();
    hideAuthAlert();
    signupForm.classList.add('hidden');
    loginForm.classList.remove('hidden');
    document.getElementById('login-username').focus();
  });

  // Signup Submit
  signupForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    hideAuthAlert();

    const usernameInput = document.getElementById('signup-username');
    const passwordInput = document.getElementById('signup-password');
    const confirmInput = document.getElementById('signup-confirm-password');

    const username = usernameInput.value.trim();
    const password = passwordInput.value;
    const confirm_password = confirmInput.value;

    if (!username || !password || !confirm_password) {
      showAuthAlert('Please fill in all required fields.');
      return;
    }

    if (password.length < 6) {
      showAuthAlert('Password must be at least 6 characters long.');
      return;
    }

    if (password !== confirm_password) {
      showAuthAlert('Passwords do not match.');
      return;
    }

    setBtnLoading(signupBtn, true);

    try {
      const response = await fetch('/signup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password, confirm_password }),
      });

      const data = await response.json();

      if (response.ok && data.success) {
        signupForm.reset();
        signupForm.classList.add('hidden');
        loginForm.classList.remove('hidden');
        document.getElementById('login-username').value = username;
        document.getElementById('login-password').focus();
        showAuthAlert('Account created successfully! Please sign in.', 'success');
      } else {
        showAuthAlert(data.error || 'Failed to create account.');
      }
    } catch (err) {
      showAuthAlert('Network error occurred. Please try again.');
    } finally {
      setBtnLoading(signupBtn, false);
    }
  });

  // Login Submit
  loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    hideAuthAlert();

    const usernameInput = document.getElementById('login-username');
    const passwordInput = document.getElementById('login-password');

    const username = usernameInput.value.trim();
    const password = passwordInput.value;

    if (!username || !password) {
      showAuthAlert('Please enter both username and password.');
      return;
    }

    setBtnLoading(loginBtn, true);

    try {
      const response = await fetch('/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });

      const data = await response.json();

      if (response.ok && data.success && data.access_token) {
        setSession(data.access_token, data.username, data.role);
        loginForm.reset();
        showChatView();
      } else {
        showAuthAlert(data.error || 'Invalid credentials. Please try again.');
      }
    } catch (err) {
      showAuthAlert('Unable to reach server. Please check your connection.');
    } finally {
      setBtnLoading(loginBtn, false);
    }
  });

  // Logout
  logoutBtn.addEventListener('click', () => {
    clearSession();
    clearMessagesView();
    showAuthView();
  });

  // Admin Verification Check
  adminVerifyBtn.addEventListener('click', async () => {
    const token = getToken();
    if (!token) {
      handleUnauthorized();
      return;
    }

    try {
      const response = await fetch('/admin', {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: 'application/json',
        },
      });

      const data = await response.json();
      if (response.ok && data.access === 'authorized') {
        showToast('Admin Authorized: Access granted to admin portal.', false);
      } else if (response.status === 403) {
        showToast('Access Forbidden: Admin privileges required.');
      } else if (response.status === 401) {
        handleUnauthorized();
      } else {
        showToast(data.error || 'Failed to verify admin status.');
      }
    } catch (err) {
      showToast('Network error verifying admin status.');
    }
  });

  function handleUnauthorized() {
    clearSession();
    showAuthView();
    showAuthAlert('Your session has expired or is invalid. Please sign in again.');
  }

  // =========================================================
  // Image Attachment & Preview Handlers
  // =========================================================

  function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }

  function clearImageSelection() {
    selectedImageFile = null;
    if (imageFileInput) imageFileInput.value = '';
    if (imagePreviewContainer) imagePreviewContainer.classList.add('hidden');
    if (imagePreviewThumb) imagePreviewThumb.src = '';
  }

  function handleImageSelected(file) {
    if (!file) return;

    const validTypes = ['image/jpeg', 'image/png', 'image/webp'];
    const validExts = ['.jpg', '.jpeg', '.png', '.webp'];
    const fileName = file.name.toLowerCase();
    const hasValidExt = validExts.some((ext) => fileName.endsWith(ext));
    const hasValidType = validTypes.includes(file.type);

    if (!hasValidType && !hasValidExt) {
      showToast('Unsupported image format. Allowed formats: JPG, PNG, WEBP.');
      clearImageSelection();
      return;
    }

    if (file.size > 10 * 1024 * 1024) {
      showToast('Image size exceeds the 10 MB limit.');
      clearImageSelection();
      return;
    }

    selectedImageFile = file;

    const reader = new FileReader();
    reader.onload = (e) => {
      if (imagePreviewThumb) imagePreviewThumb.src = e.target.result;
    };
    reader.readAsDataURL(file);

    if (imagePreviewName) imagePreviewName.textContent = file.name;
    if (imagePreviewSize) imagePreviewSize.textContent = formatFileSize(file.size);
    if (imagePreviewContainer) imagePreviewContainer.classList.remove('hidden');

    chatInput.focus();
  }

  if (attachBtn) {
    attachBtn.addEventListener('click', () => {
      if (imageFileInput) imageFileInput.click();
    });
  }

  if (imageFileInput) {
    imageFileInput.addEventListener('change', (e) => {
      const file = e.target.files && e.target.files[0];
      if (file) {
        handleImageSelected(file);
      }
    });
  }

  if (imagePreviewRemove) {
    imagePreviewRemove.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      clearImageSelection();
      chatInput.focus();
    });
  }

  // =========================================================
  // Conversation History & Sidebar Management
  // =========================================================

  function clearMessagesView() {
    clearImageSelection();
    const messages = chatMessages.querySelectorAll('.message-row');
    messages.forEach((msg) => msg.remove());
    if (welcomeBox) welcomeBox.classList.remove('hidden');
  }

  function startNewChat() {
    activeConversationId = null;
    sessionStorage.removeItem(STORAGE_ACTIVE_CONV_KEY);
    clearMessagesView();

    // Update active class in sidebar
    document.querySelectorAll('.history-item').forEach((item) => {
      item.classList.remove('active');
    });

    closeMobileSidebar();
    chatInput.focus();
  }

  newChatBtn.addEventListener('click', startNewChat);

  /**
   * Groups a list of conversations by date:
   * - Today
   * - Yesterday
   * - Previous 7 Days
   * - Older
   */
  function groupConversationsByDate(conversations) {
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    const sevenDaysAgo = new Date(today);
    sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);

    const groups = {
      Today: [],
      Yesterday: [],
      'Previous 7 Days': [],
      Older: [],
    };

    conversations.forEach((conv) => {
      const date = new Date(conv.updated_at || conv.created_at);
      const convDay = new Date(date.getFullYear(), date.getMonth(), date.getDate());

      if (convDay.getTime() === today.getTime()) {
        groups.Today.push(conv);
      } else if (convDay.getTime() === yesterday.getTime()) {
        groups.Yesterday.push(conv);
      } else if (convDay >= sevenDaysAgo) {
        groups['Previous 7 Days'].push(conv);
      } else {
        groups.Older.push(conv);
      }
    });

    return groups;
  }

  /**
   * Loads all conversations from backend and populates the sidebar.
   */
  async function loadConversations() {
    const token = getToken();
    if (!token) return;

    try {
      const response = await fetch('/conversations', {
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: 'application/json',
        },
      });

      if (response.status === 401) {
        handleUnauthorized();
        return;
      }

      const data = await response.json();
      if (!response.ok || !data.success) return;

      renderSidebar(data.conversations || []);
    } catch (err) {
      console.error('Failed to load conversations:', err);
    }
  }

  function renderSidebar(conversations) {
    historyContainer.innerHTML = '';

    if (!conversations || conversations.length === 0) {
      historyContainer.innerHTML = '<div class="history-empty">No conversations yet</div>';
      return;
    }

    const groups = groupConversationsByDate(conversations);

    for (const [groupName, convList] of Object.entries(groups)) {
      if (convList.length === 0) continue;

      const groupDiv = document.createElement('div');
      groupDiv.className = 'history-group';

      const titleDiv = document.createElement('div');
      titleDiv.className = 'history-group-title';
      titleDiv.textContent = groupName;
      groupDiv.appendChild(titleDiv);

      convList.forEach((conv) => {
        const item = document.createElement('div');
        item.className = 'history-item';
        item.setAttribute('data-id', conv.id);
        if (activeConversationId === conv.id) {
          item.classList.add('active');
        }

        // Speech bubble icon
        const iconSvg = `
          <svg class="history-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
          </svg>`;

        // Title span
        const titleSpan = document.createElement('span');
        titleSpan.className = 'history-title';
        titleSpan.textContent = conv.title || 'Conversation';

        // Delete button
        const delBtn = document.createElement('button');
        delBtn.className = 'history-delete-btn';
        delBtn.title = 'Delete chat';
        delBtn.innerHTML = `
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="3 6 5 6 21 6"></polyline>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
          </svg>`;

        delBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          deleteConversation(conv.id, conv.title);
        });

        item.innerHTML = iconSvg;
        item.appendChild(titleSpan);
        item.appendChild(delBtn);

        item.addEventListener('click', () => {
          selectConversation(conv.id);
        });

        groupDiv.appendChild(item);
      });

      historyContainer.appendChild(groupDiv);
    }
  }

  /**
   * Select and load a conversation's messages from the backend.
   */
  async function selectConversation(id) {
    if (!id) return;
    const token = getToken();
    if (!token) {
      handleUnauthorized();
      return;
    }

    try {
      const response = await fetch(`/conversations/${id}`, {
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: 'application/json',
        },
      });

      if (response.status === 401) {
        handleUnauthorized();
        return;
      }

      if (response.status === 404) {
        startNewChat();
        return;
      }

      const data = await response.json();
      if (!response.ok || !data.success) {
        showToast(data.error || 'Failed to open conversation.');
        return;
      }

      activeConversationId = id;
      sessionStorage.setItem(STORAGE_ACTIVE_CONV_KEY, id);

      // Highlight active in sidebar
      document.querySelectorAll('.history-item').forEach((item) => {
        if (parseInt(item.getAttribute('data-id'), 10) === id) {
          item.classList.add('active');
        } else {
          item.classList.remove('active');
        }
      });

      // Render messages
      clearMessagesView();
      const messages = data.conversation.messages || [];

      if (messages.length > 0 && welcomeBox) {
        welcomeBox.classList.add('hidden');
      }

      messages.forEach((msg) => {
        if (msg.role === 'user') {
          appendUserMessage(msg.content, msg.image_url, false);
        } else {
          appendAiMessage(msg.content, false);
        }
      });

      scrollToBottom();
      closeMobileSidebar();
      chatInput.focus();
    } catch (err) {
      showToast('Network error opening conversation.');
    }
  }

  /**
   * Delete a conversation.
   */
  async function deleteConversation(id, title) {
    const confirmDelete = window.confirm(`Delete conversation "${title || 'Chat'}"?`);
    if (!confirmDelete) return;

    const token = getToken();
    if (!token) {
      handleUnauthorized();
      return;
    }

    try {
      const response = await fetch(`/conversations/${id}`, {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: 'application/json',
        },
      });

      if (response.status === 401) {
        handleUnauthorized();
        return;
      }

      const data = await response.json();
      if (response.ok && data.success) {
        if (activeConversationId === id) {
          startNewChat();
        }
        loadConversations();
        showToast('Conversation deleted.', false);
      } else {
        showToast(data.error || 'Failed to delete conversation.');
      }
    } catch (err) {
      showToast('Network error deleting conversation.');
    }
  }

  // =========================================================
  // Rich Markdown Parser & Safe DOM Rendering
  // =========================================================

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  /**
   * Fallback lightweight markdown parser in case marked.js is not available.
   */
  function parseSimpleMarkdown(text) {
    let html = escapeHtml(text);

    // Code blocks: ```lang ... ```
    html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (match, lang, code) => {
      const safeLang = lang || 'code';
      return `<div class="code-block-container"><div class="code-block-header"><span class="code-lang">${safeLang}</span><button class="copy-code-btn" type="button">Copy</button></div><pre><code>${code.trim()}</code></pre></div>`;
    });

    // Inline code: `code`
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

    // Headers
    html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
    html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
    html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');

    // Bold
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    // Italic
    html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');

    // Horizontal Rule
    html = html.replace(/^---$/gim, '<hr>');

    // Lists
    html = html.replace(/^\* (.*$)/gim, '<ul><li>$1</li></ul>');
    html = html.replace(/^- (.*$)/gim, '<ul><li>$1</li></ul>');
    html = html.replace(/^\d+\. (.*$)/gim, '<ol><li>$1</li></ol>');
    // Merge consecutive list tags
    html = html.replace(/<\/ul>\s*<ul>/g, '');
    html = html.replace(/<\/ol>\s*<ol>/g, '');

    // Paragraphs
    const paragraphs = html.split(/\n\n+/);
    return paragraphs
      .map((p) => {
        p = p.trim();
        if (!p) return '';
        if (p.startsWith('<h') || p.startsWith('<ul') || p.startsWith('<ol') || p.startsWith('<div') || p.startsWith('<hr')) {
          return p;
        }
        return `<p>${p.replace(/\n/g, '<br>')}</p>`;
      })
      .join('');
  }

  /**
   * Renders ChatGPT-style formatted Markdown into container with copy buttons.
   */
  function renderMarkdownToContainer(container, rawMarkdown) {
    let html = '';

    if (window.marked && typeof window.marked.parse === 'function') {
      try {
        window.marked.setOptions({
          gfm: true,
          breaks: true,
        });
        html = window.marked.parse(rawMarkdown);
      } catch (e) {
        html = parseSimpleMarkdown(rawMarkdown);
      }
    } else {
      html = parseSimpleMarkdown(rawMarkdown);
    }

    container.innerHTML = html;

    // Enhance all <pre><code> blocks with ChatGPT-style header and Copy button
    container.querySelectorAll('pre').forEach((pre) => {
      // Check if already inside code-block-container
      if (pre.parentElement.classList.contains('code-block-container')) return;

      const codeEl = pre.querySelector('code');
      let lang = 'code';
      if (codeEl) {
        const classes = codeEl.className.split(' ');
        classes.forEach((cls) => {
          if (cls.startsWith('language-')) {
            lang = cls.replace('language-', '');
          }
        });
      }

      const wrapper = document.createElement('div');
      wrapper.className = 'code-block-container';

      const header = document.createElement('div');
      header.className = 'code-block-header';

      const langSpan = document.createElement('span');
      langSpan.className = 'code-lang';
      langSpan.textContent = lang;

      const copyBtn = document.createElement('button');
      copyBtn.className = 'copy-code-btn';
      copyBtn.type = 'button';
      copyBtn.innerHTML = `
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
        </svg>
        <span>Copy</span>`;

      copyBtn.addEventListener('click', () => {
        const textToCopy = codeEl ? codeEl.textContent : pre.textContent;
        navigator.clipboard.writeText(textToCopy).then(() => {
          const span = copyBtn.querySelector('span');
          if (span) span.textContent = 'Copied!';
          setTimeout(() => {
            if (span) span.textContent = 'Copy';
          }, 2000);
        });
      });

      header.appendChild(langSpan);
      header.appendChild(copyBtn);

      pre.parentNode.insertBefore(wrapper, pre);
      wrapper.appendChild(header);
      wrapper.appendChild(pre);
    });

    // Attach click listeners to any copy buttons generated by fallback parser
    container.querySelectorAll('.copy-code-btn').forEach((btn) => {
      if (!btn.hasAttribute('data-bound')) {
        btn.setAttribute('data-bound', 'true');
        btn.addEventListener('click', () => {
          const codeEl = btn.closest('.code-block-container').querySelector('code');
          if (codeEl) {
            navigator.clipboard.writeText(codeEl.textContent).then(() => {
              btn.textContent = 'Copied!';
              setTimeout(() => { btn.textContent = 'Copy'; }, 2000);
            });
          }
        });
      }
    });
  }

  function appendUserMessage(text, imageUrl, scroll = true) {
    if (welcomeBox) welcomeBox.classList.add('hidden');

    const row = document.createElement('div');
    row.className = 'message-row message-user';

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    const uname = getUsername() || 'U';
    avatar.textContent = uname.charAt(0).toUpperCase();

    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';

    // If an image was attached
    if (imageUrl) {
      const imgWrap = document.createElement('div');
      imgWrap.className = 'message-attachment';
      const img = document.createElement('img');
      const token = getToken();
      const isBlobOrData = imageUrl.startsWith('blob:') || imageUrl.startsWith('data:');
      img.src = isBlobOrData || !token ? imageUrl : `${imageUrl}?token=${encodeURIComponent(token)}`;
      img.alt = 'Uploaded image';
      img.loading = 'lazy';
      imgWrap.appendChild(img);
      bubble.appendChild(imgWrap);
    }

    if (text && text.trim()) {
      const textDiv = document.createElement('div');
      textDiv.className = 'message-text';
      textDiv.textContent = text;
      bubble.appendChild(textDiv);
    }

    row.appendChild(avatar);
    row.appendChild(bubble);
    chatMessages.appendChild(row);
    if (scroll) scrollToBottom();
  }

  function showTypingIndicator() {
    const row = document.createElement('div');
    row.className = 'message-row message-ai typing-indicator-row';
    row.id = 'typing-indicator';

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = 'AI';

    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';

    const dots = document.createElement('div');
    dots.className = 'typing-dots';
    dots.innerHTML = '<div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>';

    bubble.appendChild(dots);
    row.appendChild(avatar);
    row.appendChild(bubble);
    chatMessages.appendChild(row);
    scrollToBottom();
  }

  function removeTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    if (indicator) indicator.remove();
  }

  function appendAiMessage(text, scroll = true) {
    removeTypingIndicator();

    const row = document.createElement('div');
    row.className = 'message-row message-ai';

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = 'AI';

    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';

    // Rich Markdown Rendering (with bold, headers, lists, code blocks)
    renderMarkdownToContainer(bubble, text);

    row.appendChild(avatar);
    row.appendChild(bubble);
    chatMessages.appendChild(row);
    if (scroll) scrollToBottom();
  }

  function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  // --- Send Message Action ---
  async function sendMessage(promptText) {
    const prompt = (promptText !== undefined ? promptText : chatInput.value).trim();
    if ((!prompt && !selectedImageFile) || isGenerating) return;

    const token = getToken();
    if (!token) {
      handleUnauthorized();
      return;
    }

    const imageToSend = selectedImageFile;
    const localPreviewUrl = imageToSend ? URL.createObjectURL(imageToSend) : null;

    // Reset input and selection
    chatInput.value = '';
    autoResizeInput();
    clearImageSelection();

    appendUserMessage(prompt, localPreviewUrl);
    showTypingIndicator();

    isGenerating = true;
    sendBtn.disabled = true;

    try {
      let response;
      if (imageToSend) {
        const formData = new FormData();
        if (prompt) formData.append('prompt', prompt);
        if (activeConversationId) formData.append('conversation_id', activeConversationId);
        formData.append('image', imageToSend);

        response = await fetch('/generate', {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`,
          },
          body: formData,
        });
      } else {
        const payload = { prompt };
        if (activeConversationId) {
          payload.conversation_id = activeConversationId;
        }

        response = await fetch('/generate', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(payload),
        });
      }

      const data = await response.json();

      if (response.ok && data.success) {
        if (data.conversation_id) {
          activeConversationId = data.conversation_id;
          sessionStorage.setItem(STORAGE_ACTIVE_CONV_KEY, data.conversation_id);
        }

        appendAiMessage(data.response || 'No response text received.');

        // Refresh sidebar conversation list
        loadConversations();
      } else if (response.status === 401) {
        removeTypingIndicator();
        handleUnauthorized();
      } else {
        removeTypingIndicator();
        const errMsg = data.details
          ? `${data.error}: ${data.details}`
          : data.error || 'Failed to generate response. Please try again.';
        showToast(errMsg);
      }
    } catch (err) {
      removeTypingIndicator();
      showToast('Network error connecting to AI service.');
    } finally {
      isGenerating = false;
      sendBtn.disabled = false;
      chatInput.focus();
    }
  }

  // Input events
  sendBtn.addEventListener('click', () => sendMessage());

  chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  function autoResizeInput() {
    chatInput.style.height = 'auto';
    chatInput.style.height = Math.min(chatInput.scrollHeight, 160) + 'px';
  }

  chatInput.addEventListener('input', autoResizeInput);

  // Suggested prompt pills
  document.querySelectorAll('.suggestion-pill').forEach((pill) => {
    pill.addEventListener('click', () => {
      const prompt = pill.getAttribute('data-prompt');
      if (prompt) {
        sendMessage(prompt);
      }
    });
  });

  // --- Initialize on Page Load ---
  function initApp() {
    const token = getToken();
    if (token) {
      showChatView();
    } else {
      showAuthView();
    }
  }

  initApp();
})();
