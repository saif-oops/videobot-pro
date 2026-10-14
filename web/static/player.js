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
  const pipBtn           = document.getElementById('pipBtn');
  const fullscreenBtn    = document.getElementById('fullscreenBtn');
  const downloadProgress = document.getElementById('downloadProgress');
  const progressFill     = document.getElementById('progressFill');
  const progressText     = document.getElementById('progressText');

  // Ad Modal References
  const adOverlay        = document.getElementById('adOverlay');
  const adTimerText      = document.getElementById('adTimerText');
  const adContinueBtn    = document.getElementById('adContinueBtn');
  const adContinueBtnText= document.getElementById('adContinueBtnText');
  const adCloseBtn       = document.getElementById('adCloseBtn');
  const adVipCtaBtn      = document.getElementById('adVipCtaBtn');

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
  let appConfig          = { channel: '@TeraBox_Viral_1', bot_username: '' };
  let adInterval         = null;
  let pendingAction      = null;

  // ─── Telegram WebApp SDK Init ──────────────────────────────
  const tg = window.Telegram && window.Telegram.WebApp;
  let telegramUserId = null;

  if (tg) {
    tg.ready();
    tg.expand();
    document.documentElement.style.setProperty('--tg-bg', tg.themeParams.bg_color || '#0a0e1a');
    if (tg.initDataUnsafe && tg.initDataUnsafe.user) {
      telegramUserId = tg.initDataUnsafe.user.id;
    }
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
            userTierPill.className = 'user-tier-pill vip';
            tierIcon.textContent = '👑';
            tierText.textContent = 'VIP Member (No Ads)';
          } else {
            isVip = false;
            tierText.textContent = `Free (${userData.free_uses} Left)`;
          }
        }
      } catch (e) {
        console.warn('Could not fetch user status:', e);
      }
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

  // ─── Paste Button ──────────────────────────────────────────
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

  // ─── Fetch / Download Button ───────────────────────────────
  fetchBtn.addEventListener('click', () => {
    const url = urlInput.value.trim();
    if (!url) {
      showStatus('error', '⚠️', 'Please paste a TeraBox or DiskWala link first.');
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

    showStatus('loading', '🔍', 'Processing video link…');

    try {
      const resp = await fetch(getApiBase() + '/api/fetch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      });

      const data = await resp.json();

      if (!resp.ok || data.error) {
        throw new Error(data.error || 'Failed to fetch video info.');
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

  // ─── Display Video ─────────────────────────────────────────
  function displayVideo(info) {
    videoTitle.textContent = info.title || 'Video';

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
  function init() {
    loadConfigAndUser();
    const params = new URLSearchParams(window.location.search);
    const url = params.get('url');
    if (url) {
      urlInput.value = url;
      fetchVideo(url);
    }
  }

  init();

})();
