"""Page scripts of a walk session: actionable candidates and bot-check signals."""

from __future__ import annotations

MAX_TEXT_LEN = 120
MAX_OPTIONS = 80
IDX_ATTR = "data-argus-idx"

# Visible, actionable elements; mailto:/tel: links are values, not actions
# (TZ section 8.4), submit buttons of a form are never pressed (no forms here).
# Tabs and accordion headers are clicked even when they carry an href.
CANDIDATES_JS = """
() => {
  const out = [];
  const seen = new Set();
  const nodes = document.querySelectorAll(
    'a[href], button, [role="button"], [role="tab"], [aria-expanded], summary, ' +
    'input[type="button"], select');
  const clean = s => (s || '').replace(/\\s+/g, ' ').trim().slice(0, __MAX_TEXT_LEN__);
  const labelOf = el => {
    if (el.id) {
      const lab = document.querySelector('label[for="' + CSS.escape(el.id) + '"]');
      if (lab) return lab.innerText;
    }
    return el.getAttribute('aria-label') || el.name || '';
  };
  let idx = 0;
  for (const el of nodes) {
    const style = window.getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    if (style.display === 'none' || style.visibility === 'hidden') continue;
    if (rect.width === 0 && rect.height === 0) continue;
    if (el.disabled || (el.type === 'submit' && el.form)) continue;
    const isSelect = el.tagName === 'SELECT';
    const role = el.getAttribute('role') === 'tab' ? 'tab'
      : (el.hasAttribute('aria-expanded') || el.tagName === 'SUMMARY') ? 'expand' : '';
    let state = '';
    if (role === 'tab') state = el.getAttribute('aria-selected') === 'true' ? 'on' : 'off';
    if (role === 'expand') {
      const open = el.tagName === 'SUMMARY' ? el.parentElement && el.parentElement.open
        : el.getAttribute('aria-expanded') === 'true';
      state = open ? 'on' : 'off';
    }
    const text = clean(isSelect ? labelOf(el)
      : (el.innerText || el.value || el.getAttribute('aria-label') || el.title || ''));
    const rawHref = el.tagName === 'A' ? el.href : '';
    const href = typeof rawHref === 'string' ? rawHref : '';
    if (/^(mailto|tel):/i.test(href)) continue;
    const kind = isSelect ? 'select' : (role || !/^https?:/i.test(href)) ? 'button' : 'link';
    const options = isSelect ? Array.from(el.options).map(o => clean(o.text)).filter(t => t)
      .slice(0, __MAX_OPTIONS__) : [];
    if (isSelect) state = el.selectedIndex >= 0 ? clean(el.options[el.selectedIndex].text) : '';
    if (kind === 'button' && !text) continue;
    if (isSelect && !options.length) continue;
    const key = kind + '|' + text + '|' + href + '|' + options.join(',');
    if (seen.has(key)) continue;
    seen.add(key);
    el.setAttribute('__IDX_ATTR__', String(idx));
    out.push({index: idx, kind, text, href: kind === 'link' ? href : '', role, state, options});
    idx += 1;
  }
  return out;
}
""".replace("__MAX_TEXT_LEN__", str(MAX_TEXT_LEN)).replace(
    "__MAX_OPTIONS__", str(MAX_OPTIONS)
).replace("__IDX_ATTR__", IDX_ATTR)

# Signals of an interstitial bot check (Cloudflare, WAF JS challenges, captchas);
# the classification itself is `service.is_challenge` (several signals needed).
CHALLENGE_JS = """
() => {
  const markers = [
    '#challenge-running', '#challenge-form', '#challenge-stage', '#cf-challenge-running',
    '.cf-browser-verification', '[id^="cf-chl"]', '#turnstile-wrapper', '.cf-turnstile',
    'iframe[src*="challenges.cloudflare.com"]', 'script[src*="/cdn-cgi/challenge-platform/"]',
    '.g-recaptcha', 'iframe[src*="recaptcha"]', '.h-captcha', 'iframe[src*="hcaptcha"]',
  ].filter(s => document.querySelector(s) !== null);
  const text = document.body ? document.body.innerText : '';
  return {title: document.title || '', text: text.slice(0, 800), length: text.length, markers};
}
"""
