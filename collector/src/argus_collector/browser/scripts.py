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

# mailto:/tel: links the page does not render now (a closed tab, accordion or
# reveal): their values are taken when the section is opened, not before.
HIDDEN_LINKS_JS = """
() => Array.from(document.querySelectorAll('a[href^="mailto:" i], a[href^="tel:" i]'))
  .filter(a => !a.getClientRects().length || getComputedStyle(a).visibility === 'hidden')
  .map(a => (a.getAttribute('href') || '').trim())
"""

# Resolves once the DOM had no mutation for `quiet` ms (or after `max` ms): the
# page is ready by its content, not by a fixed wait (0.4.8.0: 2 x 800 ms before).
QUIET_DOM_JS = """
([quiet, max]) => new Promise(resolve => {
  const start = Date.now();
  let timer = null;
  const done = () => { observer.disconnect(); clearTimeout(timer); resolve(Date.now() - start); };
  const observer = new MutationObserver(() => {
    clearTimeout(timer);
    timer = setTimeout(done, quiet);
  });
  observer.observe(document.documentElement,
                   {subtree: true, childList: true, attributes: true, characterData: true});
  timer = setTimeout(done, quiet);
  setTimeout(done, max);
})
"""

# The selected tabs and the visible text of their panels: a tab labelled with a
# country (`Germany`) makes its panel that country's section (Beckhoff, 0.4.8.0).
TAB_PANELS_JS = """
() => Array.from(document.querySelectorAll('[role="tab"][aria-selected="true"]')).map(tab => {
  const id = tab.getAttribute('aria-controls');
  const panel = id ? document.getElementById(id) : null;
  if (!panel || !panel.getClientRects().length) return null;
  return {label: (tab.innerText || '').trim(), text: panel.innerText || ''};
}).filter(item => item && item.label && item.text.trim())
"""

# The page's text and its tab panels as the HTML writes them: CSS `text-transform`
# is off while innerText is read (owner 06.10.2026, Blåkläder: names in capitals).
PLAIN_TEXT_JS = """
() => {
  const style = document.createElement('style');
  style.textContent = '*, *::before, *::after { text-transform: none !important; }';
  (document.head || document.documentElement).appendChild(style);
  try {
    return {text: document.body ? document.body.innerText : '', panels: (PANELS)()};
  } finally {
    style.remove();
  }
}
""".replace("(PANELS)", "(" + TAB_PANELS_JS.strip() + ")")

# Status and final URL of a same-origin URL, asked through the page's own network
# (Chrome resolves `*.localhost`, sends the context's cookies and Accept-Language).
PROBE_JS = """
async ([url, ms]) => {
  const stop = new AbortController();
  const timer = setTimeout(() => stop.abort(), ms);
  try {
    const resp = await fetch(url, {redirect: 'follow', credentials: 'include',
                                   signal: stop.signal});
    return [resp.status, resp.url];
  } catch (e) {
    return [0, ''];
  } finally {
    clearTimeout(timer);
  }
}
"""

# A visible cookie-consent banner and its buttons (OneTrust, Cookiebot, generic
# dialogs and bars that talk about cookies); `service.consent_choice` picks one.
CONSENT_JS = """
() => {
  const visible = el => {
    const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
  };
  const boxes = Array.from(document.querySelectorAll(
    '#onetrust-banner-sdk, #onetrust-consent-sdk, #CybotCookiebotDialog, #cookiebanner, ' +
    '#cookie-banner, #cookie-consent, .cookie-banner, .cookie-consent, .cc-window, ' +
    '[role="dialog"], [aria-modal="true"], [id*="cookie" i], [class*="cookie" i], ' +
    '[id*="consent" i], [class*="consent" i]'));
  const words = /cookie|eväste|kakor|evästeet|consent|suostumus|datenschutz|privacy/i;
  const clickable = 'button, a[role="button"], [role="button"], input[type="button"]';
  const box = boxes.find(b => visible(b) && words.test(b.innerText || '')
    && (b.innerText || '').length < 4000 && b.querySelector(clickable));
  if (!box) return null;
  const buttons = Array.from(box.querySelectorAll(clickable)).filter(visible).slice(0, 12);
  buttons.forEach((b, i) => b.setAttribute('data-argus-consent', String(i)));
  const label = b => (b.innerText || b.value || b.getAttribute('aria-label') || '');
  return buttons.map((b, i) => ({index: i, text: label(b).replace(/\\s+/g, ' ').trim()}));
}
"""
