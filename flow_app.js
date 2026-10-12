/* ============================================
   DISKWALA — APP.JS
   All JavaScript for the site
   Version: 1.0
   ============================================ */

// ===== PARTICLES =====
function createParticles(containerId, count, color) {
    const container = document.getElementById(containerId);
    if (!container) return;
    for (let i = 0; i < count; i++) {
        const p = document.createElement('div');
        p.className = 'particle';
        p.style.left = Math.random() * 100 + '%';
        p.style.top = Math.random() * 100 + '%';
        p.style.width = Math.random() * 4 + 2 + 'px';
        p.style.height = p.style.width;
        p.style.background = color || 'rgba(16,185,129,0.3)';
        p.style.animationDelay = Math.random() * 5 + 's';
        p.style.animationDuration = Math.random() * 10 + 10 + 's';
        container.appendChild(p);
    }
}

document.addEventListener('DOMContentLoaded', function () {
    createParticles('heroParticles', 30, 'rgba(16,185,129,0.2)');
    createParticles('footerParticles', 20, 'rgba(255,255,255,0.1)');
});

// ===== CURSOR GLOW =====
const cursor = document.getElementById('cursorGlow');
if (cursor) {
    document.addEventListener('mousemove', (e) => {
        cursor.style.left = e.clientX - 150 + 'px';
        cursor.style.top = e.clientY - 150 + 'px';
    });
}

// ===== SCROLL PROGRESS =====
const scrollProgress = document.getElementById('scrollProgress');
if (scrollProgress) {
    window.addEventListener('scroll', () => {
        const h = document.documentElement;
        const st = h.scrollTop;
        const sh = h.scrollHeight - h.clientHeight;
        scrollProgress.style.width = (st / sh) * 100 + '%';
    });
}

// ===== NAVBAR SCROLL EFFECT =====
const mainNav = document.getElementById('mainNav');
if (mainNav) {
    window.addEventListener('scroll', () => {
        mainNav.classList.toggle('scrolled', window.scrollY > 50);
    });
}

// ===== SCROLL REVEAL =====
const revealElements = document.querySelectorAll(
    '.section-header, .card-glass, .step-card, .counter-card, .accordion-item, .contact-glass, .feature-list, .phone-showcase'
);

const reveal = () => {
    revealElements.forEach(el => {
        const rect = el.getBoundingClientRect();
        if (rect.top < window.innerHeight - 100) {
            el.classList.add('revealed');
        }
    });
};

window.addEventListener('scroll', reveal);
window.addEventListener('load', () => {
    revealElements.forEach(el => el.classList.add('revealed'));
});

// ===== PASTE BUTTON =====
const pasteBtn = document.getElementById('pasteBtn');
if (pasteBtn) {
    pasteBtn.addEventListener('click', async function () {
        try {
            document.getElementById('videoUrl').value = await navigator.clipboard.readText();
        } catch (e) {
            document.getElementById('videoUrl').focus();
        }
    });
}

// ===== SEARCH BUTTON =====
const searchBtn = document.getElementById('searchBtn');
if (searchBtn) {
    searchBtn.addEventListener('click', async function () {
        const url = document.getElementById('videoUrl').value.trim();
        const btn = this;

        if (!url) {
            document.getElementById('videoUrl').classList.add('is-invalid');
            setTimeout(() => {
                document.getElementById('videoUrl').classList.remove('is-invalid');
            }, 2000);
            return;
        }

        btn.innerHTML = '<span class="btn-text">Searching</span><i class="bi bi-hourglass-split"></i>';
        btn.disabled = true;

        try {
            const response = await fetch('/searchVideo', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-TOKEN': document
                        .querySelector('meta[name="csrf-token"]')
                        .getAttribute('content'),
                },
                body: JSON.stringify({ url: url })
            });

            const data = await response.json();

            btn.innerHTML = '<span class="btn-text">Search</span><i class="bi bi-arrow-right"></i>';
            btn.disabled = false;

            console.log(data);
            if (data.status == true) {
                const res = data.response[0];

                document.getElementById('searchResults').style.display = 'block';
                document.getElementById('searchResults').classList.add('fade-in');
                document.getElementById('resultTitle').textContent = res['file_name'] ?? 'No Title';
                document.getElementById('resultViews').textContent = data.response.length ?? '1';
                document.getElementById('resultSize').textContent = res.file_size ?? '1';
            } else {
                alert(data['message'] || 'Video not found');
            }
        } catch (error) {
            btn.innerHTML = '<span class="btn-text">Search</span><i class="bi bi-arrow-right"></i>';
            btn.disabled = false;
            console.error(error);
            alert('Something went wrong');
        }
    });
}

// ===== APP REDIRECT BUTTONS =====
document.addEventListener('DOMContentLoaded', function () {
    const playStoreUrl = document.body.dataset.playstoreUrl || '';
    document.querySelectorAll('.app-redirect').forEach(btn => {
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            if (playStoreUrl) window.open(playStoreUrl, '_blank');
        });
    });
});