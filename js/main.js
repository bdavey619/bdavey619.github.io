/* ============================================
   main.js — Dark mode + scroll entrance
   ============================================ */

(function () {
  // ---- Theme ----
  // The pre-paint bootstrap in each page's <head> has already stamped
  // data-theme if the visitor made a deliberate choice. Everything here is
  // about keeping the toggle honest and only persisting real decisions.
  const root = document.documentElement;
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)');
  const THEME_COLORS = { light: '#dbe3e8', dark: '#0d2a31' };

  // One-time migration. The previous version wrote localStorage on every
  // load, including when it was only reflecting the OS — so a first visit
  // permanently pinned the theme and the site stopped following the OS
  // afterwards. Those values were never deliberate; drop them.
  try { localStorage.removeItem('theme'); } catch (e) { /* private mode */ }

  const effectiveTheme = () =>
    root.getAttribute('data-theme') || (prefersDark.matches ? 'dark' : 'light');

  // Keep mobile browser chrome in step. With a stored choice both meta tags
  // carry the chosen colour, so whichever the browser matches is correct;
  // otherwise each keeps the colour its own media query implies.
  const paintThemeColor = () => {
    const stamped = root.getAttribute('data-theme');
    document.querySelectorAll('meta[name="theme-color"]').forEach((meta) => {
      const isDarkMeta = (meta.getAttribute('media') || '').includes('dark');
      meta.setAttribute('content', stamped
        ? THEME_COLORS[stamped]
        : THEME_COLORS[isDarkMeta ? 'dark' : 'light']);
    });
  };

  const toggle = document.querySelector('.theme-toggle');

  const paintToggle = () => {
    if (!toggle) return;
    const isDark = effectiveTheme() === 'dark';
    toggle.textContent = isDark ? '☀' : '☽';
    toggle.setAttribute('aria-label', isDark ? 'Switch to light mode' : 'Switch to dark mode');
  };

  paintToggle();
  paintThemeColor();

  if (toggle) {
    toggle.addEventListener('click', () => {
      const next = effectiveTheme() === 'dark' ? 'light' : 'dark';
      root.setAttribute('data-theme', next);
      // Only a click is a deliberate choice, so only a click is stored.
      try { localStorage.setItem('theme-choice', next); } catch (e) { /* private mode */ }
      paintToggle();
      paintThemeColor();
    });
  }

  // No stored choice means the page is unstamped and CSS is driving, so the
  // OS can change under us — keep the toggle glyph in sync when it does.
  const onSchemeChange = () => {
    if (!root.hasAttribute('data-theme')) {
      paintToggle();
      paintThemeColor();
    }
  };
  if (prefersDark.addEventListener) {
    prefersDark.addEventListener('change', onSchemeChange);
  } else if (prefersDark.addListener) {
    prefersDark.addListener(onSchemeChange); // Safari < 14
  }

  // ---- Scroll entrance ----
  const reveals = document.querySelectorAll('[data-reveal]');
  if (reveals.length) {
    const noMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (noMotion || !('IntersectionObserver' in window)) {
      reveals.forEach((el) => el.classList.add('in'));
    } else {
      const io = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('in');
            io.unobserve(entry.target);
          }
        });
      }, { rootMargin: '0px 0px -8% 0px', threshold: 0.05 });
      reveals.forEach((el) => io.observe(el));
    }
  }

})();
