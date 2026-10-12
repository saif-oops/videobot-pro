/**
 * TeraPlayer — Client-side video player logic
 * Handles URL fetching, HLS/MP4 playback, and download.
 */
(function () {
  'use strict';

  // ─── DOM References ────────────────────────────────────────
  const urlInput       = document.getElementById('urlInput');
  const pasteBtn       = document.getElementById('pasteBtn');
  const fetchBtn       = document.getElementById('fetchBtn');
  const fetchBtnText   = document.getElementById('fetchBtnText');
  const fetchSpinner   = document.getElementById('fetchSpinner');
  const statusBar      = document.getElementById('statusBar');
  const statusIcon     = document.getElementById('statusIcon');
  const statusText     = document.getElementById('statusText');
  const playerCard     = document.getElementById('playerCard');
  const videoPlayer    = document.getElementById('videoPlayer');
  const videoOverlay   = document.getElementById('videoOverlay');
  const playBadge      = document.getElementById('playBadge');
  const videoTitle     = document.getElementById('videoTitle');
  const videoMeta      = document.getElementById('videoMeta');
  const downloadBtn    = document.getElementById('downloadBtn');
  const pipBtn         = document.getElementById('pipBtn');
  const fullscreenBtn  = document.getElementById('fullscreenBtn');
  const downloadProgress = document.getElementById('downloadProgress');
  const progressFill   = document.getElementById('progressFill');
  const progressText   = document.getElementById('progressText');

  // ─── State ─────────────────────────────────────────────────
  let currentVideoInfo = null;
  let hlsInstance      = null;
  let isFetching       = false;

  // ─── Telegram WebApp SDK Init ──────────────────────────────
  const tg = window.Telegram && window.Telegram.WebApp;
  if (tg) {
    tg.ready();
    tg.expand();
    // Sync Telegram theme colors
    document.documentElement.style.setProperty('--tg-bg', tg.themeParams.bg_color || '#0a0e1a');
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
    fetchBtnText.textContent = active ? 'Fetching…' : '🔍 Fetch Video';
  }

  function formatDuration(secs) {
    if (!secs) return 'Unknown';
    const h = Math.floor(secs / 3600);
    const m = Math.floor((secs % 3600) / 60);
    const s = Math.floor(secs % 60);
    if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    return `${m}:${String(s).padStart(2, '0')}`;
  }

  // ─── Paste Button ──────────────────────────────────────────
  pasteBtn.addEventListener('click', async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        urlInput.value = text.trim();
        urlInput.focus();
        if (tg) tg.HapticFeedback.impactOccurred('light');
      }
    } catch {
      // Clipboard API might be blocked in Telegram WebView
      urlInput.focus();
      urlInput.select();
    }
  });

  // ─── Fetch Button ──────────────────────────────────────────
  fetchBtn.addEventListener('click', () => {
    const url = urlInput.value.trim();
    if (!url) {
      showStatus('error', '⚠️', 'Please paste a TeraBox link first.');
      return;
    }
    fetchVideo(url);
  });

  // ─── Enter key to fetch ────────────────────────────────────
  urlInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') fetchBtn.click();
  });

  // ─── Fetch Video Info ──────────────────────────────────────
  async function fetchVideo(url) {
    if (isFetching) return;
    setFetching(true);
    hideStatus();
    playerCard.classList.remove('active');

    showStatus('loading', '🔍', 'Fetching video info…');

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
      showStatus('success', '✅', 'Video loaded successfully!');
      displayVideo(data);

      // Auto-play after a brief moment
      setTimeout(() => {
        hideStatus();
      }, 2000);

    } catch (err) {
      showStatus('error', '❌', err.message || 'Something went wrong.');
      if (tg) tg.HapticFeedback.notificationOccurred('error');
    } finally {
      setFetching(false);
    }
  }

  // ─── Display Video ─────────────────────────────────────────
  function displayVideo(info) {
    // Title
    videoTitle.textContent = info.title || 'TeraBox Video';

    // Meta badges
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
    badges.push({ icon: '📦', text: 'TeraBox' });

    badges.forEach(b => {
      const el = document.createElement('span');
      el.className = 'meta-badge';
      el.innerHTML = `<span class="badge-icon">${b.icon}</span> ${b.text}`;
      videoMeta.appendChild(el);
    });

    // Load video source
    loadVideoSource(info);

    // Show player card
    playerCard.classList.add('active');
    playerCard.scrollIntoView({ behavior: 'smooth', block: 'center' });

    if (tg) tg.HapticFeedback.notificationOccurred('success');
  }

  // ─── Load Video Source (HLS / MP4) ─────────────────────────
  function loadVideoSource(info) {
    // Destroy previous HLS instance
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

    // Use our proxy to avoid CORS issues
    const proxiedUrl = getApiBase() + '/api/stream?url=' + encodeURIComponent(streamUrl);

    const isHLS = streamUrl.includes('.m3u8') || streamUrl.includes('M3U8');

    if (isHLS && Hls.isSupported()) {
      // HLS.js for m3u8 streams
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
          // Fallback: try direct MP4 load
          videoPlayer.src = proxiedUrl;
          videoPlayer.play().catch(() => {});
        }
      });
    } else if (isHLS && videoPlayer.canPlayType('application/vnd.apple.mpegurl')) {
      // Native HLS (Safari)
      videoPlayer.src = proxiedUrl;
      videoPlayer.addEventListener('loadedmetadata', () => {
        videoPlayer.play().catch(() => {});
      }, { once: true });
    } else {
      // Direct MP4
      videoPlayer.src = proxiedUrl;
      videoPlayer.addEventListener('loadeddata', () => {
        videoPlayer.play().catch(() => {});
      }, { once: true });
    }

    // Hide overlay when playing
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

  // ─── Download Button ───────────────────────────────────────
  downloadBtn.addEventListener('click', () => {
    if (!currentVideoInfo) return;

    const streamUrl = currentVideoInfo.stream_url || currentVideoInfo.direct_url ||
      (currentVideoInfo.formats && currentVideoInfo.formats[0] &&
        (currentVideoInfo.formats[0].direct_url || currentVideoInfo.formats[0].url));

    if (!streamUrl) {
      showStatus('error', '❌', 'No download URL available.');
      return;
    }

    const downloadUrl = getApiBase() + '/api/download?url=' + encodeURIComponent(streamUrl) +
      '&title=' + encodeURIComponent(currentVideoInfo.title || 'video');

    // Open in new tab to trigger browser download
    const a = document.createElement('a');
    a.href = downloadUrl;
    a.target = '_blank';
    a.click();

    if (tg) tg.HapticFeedback.impactOccurred('medium');
  });

  // ─── PiP Button ────────────────────────────────────────────
  pipBtn.addEventListener('click', async () => {
    try {
      if (document.pictureInPictureElement) {
        await document.exitPictureInPicture();
      } else if (videoPlayer.requestPictureInPicture) {
        await videoPlayer.requestPictureInPicture();
      }
    } catch {
      // PiP not supported
    }
  });

  // ─── Fullscreen Button ─────────────────────────────────────
  fullscreenBtn.addEventListener('click', () => {
    const wrapper = document.getElementById('videoWrapper');
    if (document.fullscreenElement) {
      document.exitFullscreen();
    } else if (wrapper.requestFullscreen) {
      wrapper.requestFullscreen();
    } else if (wrapper.webkitRequestFullscreen) {
      wrapper.webkitRequestFullscreen();
    }
  });

  // ─── Auto-Fetch from URL Params ────────────────────────────
  function init() {
    const params = new URLSearchParams(window.location.search);
    const url = params.get('url');
    if (url) {
      urlInput.value = url;
      fetchVideo(url);
    }
  }

  init();

})();
