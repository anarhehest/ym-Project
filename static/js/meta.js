const PLACEHOLDER = 'data:image/svg+xml;utf8,' + encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400" viewBox="0 0 400 400">' +
    '<rect fill="%23e9e9ee" width="100%" height="100%"/>' +
    '<g transform="translate(0,0)">' +
    '<text x="50%" y="46%" dominant-baseline="middle" text-anchor="middle" fill="%23888" font-family="Arial, Helvetica, sans-serif" font-size="34">No cover</text>' +
    '<text x="50%" y="64%" dominant-baseline="middle" text-anchor="middle" fill="%23bbb" font-family="Arial, Helvetica, sans-serif" font-size="16">Radio</text>' +
    '</g>' +
    '</svg>'
);

function normalizeCoverUri(uri) {
    if (!uri) return null;
    uri = uri.trim();
    if (!/^https?:\/\//i.test(uri)) {
        uri = 'https://' + uri.replace(/^\/+/, '');
    }
    if (uri.includes('%%')) {
        uri = uri.replace(/%%/g, 'm1000x1000');
    } else {
        if (!/\/m\d+x\d+(\/|$)/i.test(uri)) {
            uri = uri.replace(/\/+$/, '') + '/m1000x1000';
        }
    }
    return uri;
}

function setCardBackground(cardEl, url) {
    if (!cardEl) return;
    if (!url) {
        cardEl.style.removeProperty('--card-bg-image');
        return;
    }
    const safeUrl = url.startsWith('data:') ? url : url.replace(/"/g, '%22');
    cardEl.style.setProperty('--card-bg-image', `linear-gradient(rgba(0,0,0,0.06), rgba(0,0,0,0.02)), url("${safeUrl}")`);
}

const ev = new EventSource('/stream/meta');
const cardEl = document.querySelector('.player-card');
const coverEl = document.querySelector('.cover') || (() => {
    const img = document.createElement('img');
    img.id = 'cover';
    img.className = 'cover';
    img.alt = 'cover';
    const wrap = document.querySelector('.cover-wrap') || cardEl || document.body;
    wrap.appendChild(img);
    return img;
})();
let lastCoverLink = null;

if (coverEl) {
    coverEl.style.cursor = 'pointer';
    coverEl.addEventListener('click', (ev) => {
        if (!lastCoverLink) return;
        window.open(lastCoverLink, '_blank', 'noopener');
    });
}

const titleEl = document.getElementById('title') || document.querySelector('.meta .title');
const artistEl = document.getElementById('artist') || document.querySelector('.meta .artist');

function hideImg(img) {
    img.classList.remove('visible');
}

function showImg(img) {
    img.classList.add('visible');
}

function setCoverSafe(imgEl, url, altText) {
    hideImg(imgEl);
    const target = url || PLACEHOLDER;
    const tmp = new Image();
    tmp.crossOrigin = 'anonymous';
    tmp.onload = () => {
        imgEl.src = target;
        if (altText) imgEl.alt = altText;
        setCardBackground(cardEl, target);
        requestAnimationFrame(() => requestAnimationFrame(() => showImg(imgEl)));
    };
    tmp.onerror = () => {
        imgEl.src = PLACEHOLDER;
        imgEl.alt = altText || 'no cover';
        setCardBackground(cardEl, PLACEHOLDER);
        requestAnimationFrame(() => requestAnimationFrame(() => showImg(imgEl)));
    };
    tmp.src = target;
}

ev.onmessage = (e) => {
    try {
        const j = JSON.parse(e.data);

        let artists;
        if (Array.isArray(j.artists)) {
            artists = j.artists.length ? j.artists.join(', ') : '—';
        } else {
            artists = j.artists || '—';
        }

        const title = j.title || '—';
        if (titleEl) titleEl.textContent = title;
        if (artistEl) artistEl.textContent = artists;

        document.title = `${artists} — ${title}`;

        if (j.album_id && j.id) {
            try {
                const aid = encodeURIComponent(String(j.album_id));
                const tid = encodeURIComponent(String(j.id));
                lastCoverLink = `https://music.yandex.com/album/${aid}/track/${tid}`;
            } catch (err) {
                lastCoverLink = null;
            }
        } else {
            lastCoverLink = null;
        }

        if (j.cover_uri) {
            const url = normalizeCoverUri(j.cover_uri);
            setCoverSafe(coverEl, url, `${artists} — ${title}`);
        } else {
            setCoverSafe(coverEl, null, `${artists} — ${title}`);
        }
    } catch (err) {
        console.warn(err);
    }
};

ev.onerror = () => {
    console.warn('SSE connection error');
};
