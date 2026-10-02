/* English is real static HTML. Redirect only a first visit to the English home;
   explicit language URLs and manual preferences always take priority. */
(() => {
  const config = JSON.parse(document.getElementById('site-config').textContent);
  if (!config.detectLanguage || /bot|crawler|spider|google|bing|lighthouse/i.test(navigator.userAgent)) return;
  try {
    const saved = localStorage.getItem('highball-language');
    if (!saved && sessionStorage.getItem('highball-language-checked')) return;
    sessionStorage.setItem('highball-language-checked', '1');
    const languages = saved ? [saved] : (navigator.languages || [navigator.language]);
    for (const language of languages) {
      const code = language.toLowerCase().split('-')[0];
      if (config.languages.includes(code)) {
        if (code !== 'en') location.replace(`${config.root}/${code}/${location.search}${location.hash}`);
        return;
      }
    }
  } catch { /* Storage can be unavailable; the English page still works. */ }
})();
