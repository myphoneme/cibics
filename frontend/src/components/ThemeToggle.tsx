import { useEffect, useState } from 'react';

const THEME_KEY = 'cibics_theme';

export function ThemeToggle() {
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    const saved = localStorage.getItem(THEME_KEY);
    return saved === 'light' ? 'light' : 'dark';
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(THEME_KEY, theme);
  }, [theme]);

  const isDark = theme === 'dark';

  return (
    <button
      className="icon-btn theme-btn"
      onClick={() => setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'))}
      type="button"
      title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
    >
      {isDark ? <IconSun /> : <IconMoon />}
    </button>
  );
}

function IconSun() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="svg-icon">
      <circle cx="12" cy="12" r="4" stroke="currentColor" fill="none" strokeWidth="2" />
      <path
        d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M19.1 4.9L17 7M7 17l-2.1 2.1"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

function IconMoon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="svg-icon">
      <path
        d="M20 14.5A8.5 8.5 0 1 1 9.5 4a7 7 0 0 0 10.5 10.5Z"
        stroke="currentColor"
        fill="none"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
