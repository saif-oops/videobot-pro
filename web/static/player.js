/**
 * TeraBox Video Downloader — Client-side logic
 * Includes 10-second Monetag Ad countdown interstitial, VIP bypass, and cross-promotion.
 */
(function () {
  'use strict';

  // ─── DOM References ────────────────────────────────────────
  const urlInput         = document.getElementById('urlInput');
  const pasteBtn         = document.getElementById('pasteBtn');
  const fetchBtn         = document.getElementById('fetchBtn');
  const fetchBtnText     = document.getElementById('fetchBtnText');
  const fetchSpinner     = document.getElementById('fetchSpinner');
  const statusBar        = document.getElementById('statusBar');
  const statusIcon       = document.getElementById('statusIcon');
  const statusText       = document.getElementById('statusText');
  const playerCard       = document.getElementById('playerCard');
  const videoPlayer      = document.getElementById('videoPlayer');
  const videoOverlay     = document.getElementById('videoOverlay');
  const playBadge        = document.getElementById('playBadge');
  const videoTitle       = document.getElementById('videoTitle');
  const videoMeta        = document.getElementById('videoMeta');
  const downloadBtn      = document.getElementById('downloadBtn');
  const vdiskBtn         = document.getElementById('vdiskBtn');
  const pipBtn           = document.getElementById('pipBtn');
  const fullscreenBtn    = document.getElementById('fullscreenBtn');
  const downloadProgress = document.getElementById('downloadProgress');
  const progressFill     = document.getElementById('progressFill');
  const progressText     = document.getElementById('progressText');
  const actionButtons    = document.getElementById('actionButtons');
  const diskwalaActions  = document.getElementById('diskwalaActions');
  const btnDiskwalaVPlayer = document.getElementById('btnDiskwalaVPlayer');
  const btnDiskwalaApp   = document.getElementById('btnDiskwalaApp');
  const btnDiskwalaCopy  = document.getElementById('btnDiskwalaCopy');

  // Ad Modal References
  const adOverlay        = document.getElementById('adOverlay');
  const adTimerText      = document.getElementById('adTimerText');
  const adContinueBtn    = document.getElementById('adContinueBtn');
  const adContinueBtnText= document.getElementById('adContinueBtnText');
  const adCloseBtn       = document.getElementById('adCloseBtn');
  const adVipCtaBtn      = document.getElementById('adVipCtaBtn');

  // Subscription Modal References
  const subOverlay       = document.getElementById('subOverlay');
  const subCloseBtn      = document.getElementById('subCloseBtn');
  const btnSubRazorpay   = document.getElementById('btnSubRazorpay');
  const btnSubUpi        = document.getElementById('btnSubUpi');
  const btnSubRefer      = document.getElementById('btnSubRefer');

  // Network / Header References
  const userTierPill     = document.getElementById('userTierPill');
  const tierIcon         = document.getElementById('tierIcon');
  const tierText         = document.getElementById('tierText');
  const btnOfficialChannel = document.getElementById('btnOfficialChannel');
  const btnDiskwala      = document.getElementById('btnDiskwala');
  const btnRefer         = document.getElementById('btnRefer');
  const btnBuyVip        = document.getElementById('btnBuyVip');
  const botFooterLink    = document.getElementById('botFooterLink');

  // ─── State ─────────────────────────────────────────────────
  let currentVideoInfo   = null;
  let hlsInstance        = null;
  let isFetching         = false;
  let isVip              = false;
  let freeUses           = 5;
  let appConfig          = { channel: '@TeraBox_Viral_1', bot_username: '' };
  let adInterval         = null;
  let pendingAction      = null;

  // ─── Telegram WebApp SDK Init ──────────────────────────────
  const tg = window.Telegram && window.Telegram.WebApp;
  const urlParams = new URLSearchParams(window.location.search);
  const currentSid = urlParams.get('sid') || '';
  const uidParam = urlParams.get('uid');

  let telegramUserId = null;
  if (tg) {
    tg.ready();
    tg.expand();
    document.documentElement.style.setProperty('--tg-bg', tg.themeParams.bg_color || '#0a0e1a');
    if (tg.initDataUnsafe && tg.initDataUnsafe.user) {
      telegramUserId = tg.initDataUnsafe.user.id;
      try { localStorage.setItem('videobot_tg_uid', telegramUserId); } catch (e) {}
    }
  }

  if (!telegramUserId && uidParam) {
    telegramUserId = uidParam;
    try { localStorage.setItem('videobot_tg_uid', telegramUserId); } catch (e) {}
  } else if (!telegramUserId) {
    try { telegramUserId = localStorage.getItem('videobot_tg_uid'); } catch (e) {}
  }

  // ─── Helpers ───────────────────────────────────────────────
  function getApiBase() {
    return window.location.origin;
  }

  function showStatus(type, icon, message) {
    statusBar.className = 'status-bar active ' + type;
    statusIcon.textContent = icon;
    statusText.textContent = message;
  }

  function hideStatus() {
    statusBar.className = 'status-bar';
  }

  function setFetching(active) {
    isFetching = active;
    fetchBtn.disabled = active;
    fetchSpinner.className = active ? 'spinner active' : 'spinner';
    fetchBtnText.textContent = active ? 'Fetching…' : 'Download';
  }

  function openTg(link) {
    if (tg && typeof tg.openTelegramLink === 'function') {
      try {
        tg.openTelegramLink(link);
        return;
      } catch (e) {
        // Fallback to window.open
      }
    }
    window.open(link, '_blank');
  }

  // ─── Subscription Modal & Quota UI ────────────────────────
  function showSubscriptionModal() {
    if (subOverlay) {
      subOverlay.style.display = 'flex';
      if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred('warning');
    }
  }

  function hideSubscriptionModal() {
    if (subOverlay) {
      subOverlay.style.display = 'none';
    }
  }

  if (subCloseBtn) {
    subCloseBtn.addEventListener('click', hideSubscriptionModal);
  }

  if (btnSubRazorpay) {
    btnSubRazorpay.addEventListener('click', () => {
      window.open('https://rzp.io/rzp/1tGAGsc', '_blank');
    });
  }

  if (btnSubUpi) {
    btnSubUpi.addEventListener('click', () => {
      const botName = appConfig.bot_username || 'Tera_Player_Bot';
      openTg('https://t.me/' + botName + '?start=premium');
    });
  }

  if (btnSubRefer) {
    btnSubRefer.addEventListener('click', () => {
      const botName = appConfig.bot_username || 'Tera_Player_Bot';
      openTg('https://t.me/' + botName + '?start=refer');
    });
  }

  function updateTierPill() {
    if (isVip) {
      userTierPill.className = 'user-tier-pill vip';
      tierIcon.textContent = '👑';
      tierText.textContent = 'VIP Member (No Ads)';
    } else if (freeUses <= 0) {
      userTierPill.className = 'user-tier-pill limit-reached';
      tierIcon.textContent = '⛔';
      tierText.textContent = 'Limit Reached (0/5) — Subscribe';
    } else {
      userTierPill.className = 'user-tier-pill';
      tierIcon.textContent = '🎫';
      tierText.textContent = `Free (${freeUses}/5 Left)`;
    }
  }

  userTierPill.addEventListener('click', () => {
    if (!isVip) {
      showSubscriptionModal();
    }
  });

  // ─── Init User VIP Status & Config ─────────────────────────
  async function loadConfigAndUser() {
    try {
      const cfgResp = await fetch(getApiBase() + '/api/config');
      if (cfgResp.ok) {
        appConfig = await cfgResp.json();
        if (appConfig.bot_username) {
          botFooterLink.textContent = '@' + appConfig.bot_username;
          botFooterLink.href = 'https://t.me/' + appConfig.bot_username;
        }
        if (appConfig.channel) {
          const chClean = appConfig.channel.replace('@', '');
          btnOfficialChannel.onclick = () => openTg('https://t.me/' + chClean);
        }
      }
    } catch (e) {
      console.warn('Could not load app config:', e);
    }

    if (telegramUserId) {
      try {
        const userResp = await fetch(getApiBase() + '/api/user_status?user_id=' + telegramUserId);
        if (userResp.ok) {
          const userData = await userResp.json();
          if (userData.is_premium) {
            isVip = true;
            freeUses = 999999;
          } else {
            isVip = false;
            freeUses = userData.free_uses !== undefined ? userData.free_uses : 0;
          }
          updateTierPill();
        }
      } catch (e) {
        console.warn('Could not fetch user status:', e);
      }
    } else {
      updateTierPill();
    }
  }

  // ─── Cross-Promotion Button Handlers ───────────────────────
  btnDiskwala.addEventListener('click', () => {
    openTg('https://t.me/sky577bot');
  });

  btnRefer.addEventListener('click', () => {
    const botName = appConfig.bot_username || 'Tera_Player_Bot';
    openTg('https://t.me/' + botName + '?start=refer');
  });

  function triggerVipPurchase() {
    const botName = appConfig.bot_username || 'Tera_Player_Bot';
    openTg('https://t.me/' + botName + '?start=premium');
  }

  btnBuyVip.addEventListener('click', triggerVipPurchase);
  adVipCtaBtn.addEventListener('click', triggerVipPurchase);

  // ─── 10-Second Monetag Ad Countdown Interstitial ───────────
  function runWithAdGate(action) {
    if (isVip) {
      // VIP Users bypass 100% of ads!
      action();
      return;
    }

    pendingAction = action;

    // 1. Try native Monetag Rewarded Interstitial SDK first
    if (typeof window.show_12032731 === 'function') {
      try {
        window.show_12032731().then(() => {
          // Monetag Ad viewed successfully!
          if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred('success');
          if (typeof pendingAction === 'function') {
            const act = pendingAction;
            pendingAction = null;
            act();
          }
        }).catch((err) => {
          console.warn('Monetag ad dismissed or failed, using fallback:', err);
          showFallbackAdModal();
        });
        return;
      } catch (e) {
        console.warn('Monetag call exception:', e);
      }
    }

    // 2. Fallback: Show our built-in 10-second countdown modal if SDK is offline/blocked
    showFallbackAdModal();
  }

  function showFallbackAdModal() {
    adOverlay.style.display = 'flex';
    adContinueBtn.className = 'btn btn-continue disabled';
    adContinueBtn.disabled = true;

    function unlockReward() {
      if (adInterval) {
        clearInterval(adInterval);
        adInterval = null;
      }
      adTimerText.textContent = '00:00';
      adContinueBtn.className = 'btn btn-continue active';
      adContinueBtn.disabled = false;
      adContinueBtnText.textContent = 'Continue to Download ✅';
      if (tg && tg.HapticFeedback) {
        tg.HapticFeedback.notificationOccurred('success');
      }
    }

    let secondsLeft = 10;
    adTimerText.textContent = `00:${String(secondsLeft).padStart(2, '0')}`;
    adContinueBtnText.textContent = `Please wait (${secondsLeft}s)…`;

    if (adInterval) clearInterval(adInterval);

    adInterval = setInterval(() => {
      secondsLeft--;
      if (secondsLeft > 0) {
        adTimerText.textContent = `00:${String(secondsLeft).padStart(2, '0')}`;
        adContinueBtnText.textContent = `Please wait (${secondsLeft}s)…`;
      } else {
        unlockReward();
      }
    }, 1000);
  }

  adCloseBtn.addEventListener('click', () => {
    if (adInterval) clearInterval(adInterval);
    adOverlay.style.display = 'none';
    pendingAction = null;
  });

  adContinueBtn.addEventListener('click', () => {
    if (adContinueBtn.disabled) return;
    adOverlay.style.display = 'none';
    if (typeof pendingAction === 'function') {
      const act = pendingAction;
      pendingAction = null;
      act();
    }
  });

  // ─── Paste Button (Optional) ───────────────────────────────
  if (pasteBtn) {
    pasteBtn.addEventListener('click', async () => {
      try {
        const text = await navigator.clipboard.readText();
        if (text) {
          urlInput.value = text.trim();
          urlInput.focus();
          if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
        }
      } catch {
        urlInput.focus();
        urlInput.select();
      }
    });
  }

  // ─── Fetch / Download Button ───────────────────────────────
  fetchBtn.addEventListener('click', () => {
    const url = urlInput.value.trim();
    if (!url) {
      showStatus('error', '⚠️', 'Please paste a TeraBox or DiskWala link first.');
      return;
    }

    // Strict Quota Check: If 5/5 free uses have been exhausted and user is not VIP, BLOCK immediately!
    if (!isVip && freeUses <= 0 && !currentSid) {
      showStatus('error', '🚫', 'Free limit reached (5/5 uses used). Subscription required!');
      showSubscriptionModal();
      return;
    }

    // Run with 10-second ad countdown gate
    runWithAdGate(() => {
      fetchVideo(url);
    });
  });

  urlInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') fetchBtn.click();
  });

  // ─── Fetch Video Info ──────────────────────────────────────
  async function fetchVideo(url) {
    if (isFetching) return;
    setFetching(true);
    hideStatus();
    playerCard.classList.remove('active');

    const dwMatch = url.match(/diskwala\.com\/(?:app|c)\/([a-zA-Z0-9]+)/i);
    if (dwMatch) {
      await fetchDiskwalaVideo(url, dwMatch[1]);
      setFetching(false);
      return;
    }

    showStatus('loading', '🔍', 'Processing video link…');

    try {
      const resp = await fetch(getApiBase() + '/api/fetch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url,
          user_id: telegramUserId,
          sid: currentSid
        }),
      });

      const data = await resp.json();

      if (resp.status === 403 || data.error === 'QUOTA_EXCEEDED') {
        freeUses = 0;
        updateTierPill();
        showStatus('error', '🚫', 'Free limit reached (5/5 uses used). Subscription required!');
        showSubscriptionModal();
        return;
      }

      if (!resp.ok || data.error) {
        throw new Error(data.error || 'Failed to fetch video info.');
      }

      // Quota decremented successfully on backend
      if (!isVip && !currentSid) {
        freeUses = Math.max(0, freeUses - 1);
        updateTierPill();
      }

      currentVideoInfo = data;
      showStatus('success', '✅', 'Video ready! Tap Play or Download.');
      displayVideo(data);

      setTimeout(() => {
        hideStatus();
      }, 2500);

    } catch (err) {
      showStatus('error', '❌', err.message || 'Something went wrong.');
      if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred('error');
    } finally {
      setFetching(false);
    }
  }

  // ─── DiskWala AppiCrypt Client Extractor ─────────────────────
  async function fetchDiskwalaVideo(url, fileId) {
    showStatus('loading', '🔐', 'Authenticating with DiskWala AppiCrypt…');
    try {
      let appicryptModule;
      try {
        appicryptModule = await import('/pkg/appicrypt-web-f-0_1_216.js');
      } catch (e) {
        appicryptModule = await import('https://www.diskwala.com/pkg/appicrypt-web-f-0_1_216.js');
      }

      // Fetch qt magic string
      const qtResp = await fetch('/static/qt.txt');
      const qt = (await qtResp.text()).trim();
      await appicryptModule.setMagicFile(qt);

      function Yt(e) {
        if (null === e || void 0 === e) return "";
        if ("object" !== typeof e) return JSON.stringify(e);
        if (Array.isArray(e)) return `[${e.map(Yt).join(",")}]`;
        return `{${Object.keys(e).sort().map(t => `${JSON.stringify(t)}:${Yt(e[t])}`).join(",")}}`;
      }

      const ts = Date.now().toString();
      const urlPath = "/file/temp_info";
      const bodyObj = { id: fileId };
      const bodyStr = Yt(bodyObj);
      const c = `POST ${urlPath} | params= | body=${bodyStr} | ts=${ts}`;
      const u = new TextEncoder().encode(c);
      const d = await crypto.subtle.digest("SHA-256", u);
      const cryptogram = await appicryptModule.getCryptogram(new Uint8Array(d));

      showStatus('loading', '🔍', 'Fetching DiskWala file details…');

      const metaResp = await fetch(getApiBase() + '/api/diskwala_meta', {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id: fileId,
          appicrypt: cryptogram,
          appicrypt_ts: ts,
          user_id: telegramUserId,
          sid: currentSid
        })
      });

      const metaData = await metaResp.json();

      if (metaResp.status === 403 || metaData.error === 'QUOTA_EXCEEDED') {
        freeUses = 0;
        updateTierPill();
        showStatus('error', '🚫', 'Free limit reached (5/5 uses used). Subscription required!');
        showSubscriptionModal();
        return;
      }

      if (metaData && metaData.fileInfo) {
        // Quota decremented successfully on backend
        if (!isVip && !currentSid) {
          freeUses = Math.max(0, freeUses - 1);
          updateTierPill();
        }

        const fi = metaData.fileInfo;
        const uploader = metaData.uploader || {};
        const sizeBytes = fi.size || 0;
        const sizeStr = (sizeBytes / (1024 * 1024)).toFixed(2) + ' MB';

        const diskwalaInfo = {
          title: fi.name || `DiskWala Media (${fileId})`,
          filesize_str: sizeStr,
          platform: 'diskwala',
          url: url,
          file_id: fileId,
          uploader_name: uploader.name || '',
          extension: fi.extension || 'mp4',
          type: fi.type || 'video/mp4',
          is_app_only: true
        };

        currentVideoInfo = diskwalaInfo;
        showStatus('success', '✅', 'DiskWala video details loaded!');
        displayDiskwalaCard(diskwalaInfo);
        setTimeout(hideStatus, 2500);
        return;
      }
      throw new Error(metaData.error || 'Could not verify DiskWala file.');
    } catch (err) {
      console.warn('DiskWala client fetch fallback to backend /api/fetch:', err);
      try {
        const resp = await fetch(getApiBase() + '/api/fetch', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            url,
            user_id: telegramUserId,
            sid: currentSid
          }),
        });
        const data = await resp.json();

        if (resp.status === 403 || data.error === 'QUOTA_EXCEEDED') {
          freeUses = 0;
          updateTierPill();
          showStatus('error', '🚫', 'Free limit reached (5/5 uses used). Subscription required!');
          showSubscriptionModal();
          return;
        }

        if (!resp.ok || data.error) throw new Error(data.error || 'Failed to fetch video info.');

        if (!isVip && !currentSid) {
          freeUses = Math.max(0, freeUses - 1);
          updateTierPill();
        }

        currentVideoInfo = data;
        displayDiskwalaCard(data);
      } catch (fallbackErr) {
        showStatus('error', '❌', fallbackErr.message || 'Something went wrong.');
        if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred('error');
      }
    }
  }

  // ─── Display DiskWala Card ─────────────────────────────────
  function displayDiskwalaCard(info) {
    videoTitle.textContent = info.title || 'DiskWala Video';

    videoMeta.innerHTML = '';
    const badges = [
      { icon: '📦', text: info.filesize_str || 'File' },
      { icon: '🎬', text: (info.extension || 'mp4').toUpperCase() },
      { icon: '👤', text: info.uploader_name ? info.uploader_name.trim() : 'Creator' },
      { icon: '⚡', text: 'DiskWala Cloud' },
    ];

    badges.forEach(b => {
      const el = document.createElement('span');
      el.className = 'meta-badge';
      el.innerHTML = `<span class="badge-icon">${b.icon}</span> ${b.text}`;
      videoMeta.appendChild(el);
    });

    // Custom DiskWala animated preview banner in videoWrapper
    const videoWrapper = document.getElementById('videoWrapper');
    videoPlayer.style.display = 'none';
    videoOverlay.style.display = 'none';

    let dwBanner = document.getElementById('dwBannerPreview');
    if (!dwBanner) {
      dwBanner = document.createElement('div');
      dwBanner.id = 'dwBannerPreview';
      dwBanner.style.cssText = 'width: 100%; aspect-ratio: 16/9; display: flex; flex-direction: column; align-items: center; justify-content: center; background: radial-gradient(circle at center, #1e1b4b 0%, #0c0f17 100%); border-radius: var(--radius-md); padding: 20px; text-align: center; cursor: pointer;';
      videoWrapper.appendChild(dwBanner);
    }
    dwBanner.style.display = 'flex';
    dwBanner.innerHTML = `
      <div style="width: 60px; height: 60px; border-radius: 50%; background: var(--brand-gradient); display: flex; align-items: center; justify-content: center; font-size: 26px; color: #fff; box-shadow: 0 0 25px rgba(139, 92, 246, 0.7); margin-bottom: 12px; transition: transform 0.2s;">▶</div>
      <div style="font-size: 15px; font-weight: 700; color: #fff; margin-bottom: 4px;">Stream Ready in V-Player 📱</div>
      <div style="font-size: 12px; color: var(--text-secondary);">Tap below to stream or open app</div>
    `;
    dwBanner.onclick = () => openInVDiskPro(info.url);

    if (actionButtons) actionButtons.style.display = 'none';
    if (diskwalaActions) diskwalaActions.style.display = 'flex';

    if (btnDiskwalaVPlayer) btnDiskwalaVPlayer.onclick = () => openInVDiskPro(info.url);
    if (btnDiskwalaApp) btnDiskwalaApp.onclick = () => openInDiskwalaApp(info.url);
    if (btnDiskwalaCopy) btnDiskwalaCopy.onclick = () => copyDiskwalaLink(info.url);

    playerCard.classList.add('active');
    playerCard.scrollIntoView({ behavior: 'smooth', block: 'center' });

    if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred('success');
  }

  // ─── External Player Handlers (VDiskPro / DiskWala App) ─────
  function openInVDiskPro(videoUrl) {
    if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred('medium');
    const isAndroid = /Android/i.test(navigator.userAgent);
    const isIOS = /(iPhone|iPad|iPod)/i.test(navigator.userAgent);

    if (isAndroid) {
      const clean = videoUrl.replace(/^https?:\/\//, '');
      window.location.href = `intent://${clean}#Intent;scheme=https;package=com.rpk.video_player;type=video/*;S.browser_fallback_url=https://play.google.com/store/apps/details?id=com.rpk.video_player;end`;
      return;
    }
    if (isIOS) {
      window.location.href = 'https://apps.apple.com/us/app/v-player-all-in-one/id6774285429';
      return;
    }
    if (navigator.clipboard) {
      navigator.clipboard.writeText(videoUrl);
      showStatus('success', '📋', 'Stream link copied! Open in V-Player / VLC.');
      setTimeout(hideStatus, 3000);
    }
  }

  function openInDiskwalaApp(videoUrl) {
    if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred('medium');
    const isAndroid = /Android/i.test(navigator.userAgent);
    if (isAndroid) {
      const clean = videoUrl.replace(/^https?:\/\//, '');
      window.location.href = `intent://${clean}#Intent;scheme=https;package=com.diskwalaapp;S.browser_fallback_url=https://play.google.com/store/apps/details?id=com.diskwalaapp;end`;
      return;
    }
    window.open(videoUrl, '_blank');
  }

  function copyDiskwalaLink(videoUrl) {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(videoUrl).then(() => {
        if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred('success');
        showStatus('success', '📋', 'DiskWala link copied to clipboard!');
        setTimeout(hideStatus, 2500);
      });
    }
  }

  // ─── Display Video ─────────────────────────────────────────
  function displayVideo(info) {
    videoTitle.textContent = info.title || 'Video';

    // Restore video player & controls
    videoPlayer.style.display = 'block';
    videoOverlay.style.display = '';
    const dwBanner = document.getElementById('dwBannerPreview');
    if (dwBanner) dwBanner.style.display = 'none';

    if (actionButtons) actionButtons.style.display = 'flex';
    if (diskwalaActions) diskwalaActions.style.display = 'none';

    if (vdiskBtn) {
      vdiskBtn.onclick = () => {
        const streamUrl = info.stream_url || info.direct_url || (info.formats && info.formats[0]?.direct_url) || info.url;
        openInVDiskPro(streamUrl);
      };
    }

    videoMeta.innerHTML = '';
    const badges = [];
    if (info.duration && info.duration !== 'Unknown') {
      badges.push({ icon: '⏱', text: info.duration });
    }
    if (info.filesize_str && info.filesize_str !== 'Unknown') {
      badges.push({ icon: '📦', text: info.filesize_str });
    }
    if (info.formats && info.formats.length > 0) {
      const fmt = info.formats[0];
      if (fmt.height > 0) {
        badges.push({ icon: '🎚', text: `${fmt.height}p` });
      }
    }
    badges.push({ icon: '⚡', text: 'Fast Stream' });

    badges.forEach(b => {
      const el = document.createElement('span');
      el.className = 'meta-badge';
      el.innerHTML = `<span class="badge-icon">${b.icon}</span> ${b.text}`;
      videoMeta.appendChild(el);
    });

    loadVideoSource(info);

    playerCard.classList.add('active');
    playerCard.scrollIntoView({ behavior: 'smooth', block: 'center' });

    if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred('success');
  }

  // ─── Load Video Source ─────────────────────────────────────
  function loadVideoSource(info) {
    if (hlsInstance) {
      hlsInstance.destroy();
      hlsInstance = null;
    }

    const streamUrl = info.stream_url || info.direct_url ||
      (info.formats && info.formats[0] && (info.formats[0].direct_url || info.formats[0].url));

    if (!streamUrl) {
      showStatus('error', '❌', 'No playable stream found.');
      return;
    }

    const proxiedUrl = getApiBase() + '/api/stream?url=' + encodeURIComponent(streamUrl);
    const isHLS = streamUrl.includes('.m3u8') || streamUrl.includes('M3U8');

    if (isHLS && Hls.isSupported()) {
      hlsInstance = new Hls({
        maxBufferLength: 30,
        maxMaxBufferLength: 60,
        enableWorker: true,
      });
      hlsInstance.loadSource(proxiedUrl);
      hlsInstance.attachMedia(videoPlayer);
      hlsInstance.on(Hls.Events.MANIFEST_PARSED, () => {
        videoPlayer.play().catch(() => {});
      });
      hlsInstance.on(Hls.Events.ERROR, (event, data) => {
        if (data.fatal) {
          console.warn('HLS fatal error, falling back to direct MP4');
          hlsInstance.destroy();
          hlsInstance = null;
          videoPlayer.src = proxiedUrl;
          videoPlayer.play().catch(() => {});
        }
      });
    } else {
      videoPlayer.src = proxiedUrl;
      videoPlayer.addEventListener('loadeddata', () => {
        videoPlayer.play().catch(() => {});
      }, { once: true });
    }

    videoPlayer.addEventListener('play', () => {
      videoOverlay.style.display = 'none';
    });
    videoPlayer.addEventListener('pause', () => {
      videoOverlay.style.display = '';
    });
  }

  // ─── Play Badge Click ──────────────────────────────────────
  playBadge.addEventListener('click', () => {
    if (videoPlayer.paused) {
      videoPlayer.play().catch(() => {});
    } else {
      videoPlayer.pause();
    }
  });

  // ─── Download Button Handler ───────────────────────────────
  downloadBtn.addEventListener('click', () => {
    if (!currentVideoInfo) return;

    const streamUrl = currentVideoInfo.stream_url || currentVideoInfo.direct_url ||
      (currentVideoInfo.formats && currentVideoInfo.formats[0] &&
        (currentVideoInfo.formats[0].direct_url || currentVideoInfo.formats[0].url));

    if (!streamUrl) {
      showStatus('error', '❌', 'No download URL available.');
      return;
    }

    // Free users watch 10-second countdown before download starts
    runWithAdGate(() => {
      const downloadUrl = getApiBase() + '/api/download?url=' + encodeURIComponent(streamUrl) +
        '&title=' + encodeURIComponent(currentVideoInfo.title || 'video');

      const a = document.createElement('a');
      a.href = downloadUrl;
      a.target = '_blank';
      a.click();

      if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred('medium');
    });
  });

  // ─── PiP & Fullscreen ──────────────────────────────────────
  pipBtn.addEventListener('click', async () => {
    try {
      if (document.pictureInPictureElement) {
        await document.exitPictureInPicture();
      } else if (videoPlayer.requestPictureInPicture) {
        await videoPlayer.requestPictureInPicture();
      }
    } catch {}
  });

  fullscreenBtn.addEventListener('click', () => {
    const wrapper = document.getElementById('videoWrapper');
    if (document.fullscreenElement) {
      document.exitFullscreen();
    } else if (wrapper.requestFullscreen) {
      wrapper.requestFullscreen();
    }
  });

  // ─── Auto-Fetch from URL Query Param ───────────────────────
  async function init() {
    await loadConfigAndUser();
    const url = urlParams.get('url');
    if (url) {
      urlInput.value = url;
      // If user has a valid unlocked session from bot chat (currentSid), or is VIP, or still has quota:
      if (currentSid || isVip || freeUses > 0) {
        fetchVideo(url);
      } else {
        showStatus('error', '🚫', 'Free limit reached (5/5 uses used). Subscription required!');
        showSubscriptionModal();
      }
    }
  }

  init();

})();
