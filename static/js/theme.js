(function () {
    const btn = document.getElementById('themeToggle');
    const ROOT = document.documentElement;
    const KEY = 'theme_pref';

    function applyTheme(t) {
        if (t === 'dark') {
            ROOT.setAttribute('data-theme', 'dark');
            btn.textContent = 'Light';
            btn.setAttribute('aria-pressed', 'true');
        } else {
            ROOT.removeAttribute('data-theme');
            btn.textContent = 'Dark';
            btn.setAttribute('aria-pressed', 'false');
        }
    }

    const saved = localStorage.getItem(KEY);
    const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    let current = saved || (prefersDark ? 'dark' : 'light');
    applyTheme(current);

    btn.addEventListener('click', () => {
        current = (current === 'dark') ? 'light' : 'dark';
        localStorage.setItem(KEY, current);
        applyTheme(current);
    });
})();