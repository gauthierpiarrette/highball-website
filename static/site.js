(() => {
  'use strict';
  const config = JSON.parse(document.getElementById('site-config').textContent);
  const t = config.translations;
  const language = document.querySelector('#language-select');
  language.addEventListener('change', () => {
    try { localStorage.setItem('highball-language', language.value); sessionStorage.setItem('highball-language-checked', '1'); } catch {}
    location.assign(`${config.root}/${language.value === 'en' ? '' : language.value + '/'}${config.route}${location.search}${location.hash}`);
  });
  const menu = document.querySelector('.menu-button');
  menu.addEventListener('click', () => {
    const open = menu.getAttribute('aria-expanded') !== 'true';
    menu.setAttribute('aria-expanded', String(open));
    document.querySelector('.main-nav').classList.toggle('is-open', open);
  });
  const closeMenu = () => { menu.setAttribute('aria-expanded', 'false'); document.querySelector('.main-nav').classList.remove('is-open'); };
  document.querySelectorAll('.main-nav a').forEach(link => link.addEventListener('click', closeMenu));
  document.addEventListener('keydown', event => { if (event.key === 'Escape') closeMenu(); });
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  if (!reduced.matches && 'IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => entries.forEach(entry => {
      if (entry.isIntersecting) { entry.target.classList.add('is-visible'); observer.unobserve(entry.target); }
    }), { threshold: .08 });
    document.querySelectorAll('.reveal').forEach(el => { el.classList.add('will-reveal'); observer.observe(el); });
  }
  const stage = document.querySelector('[data-parallax]');
  if (stage && !reduced.matches && matchMedia('(pointer:fine)').matches) {
    let frame;
    stage.addEventListener('pointermove', event => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const rect = stage.getBoundingClientRect();
        stage.style.setProperty('--pointer-x', `${((event.clientX - rect.left) / rect.width - .5) * 8}px`);
        stage.style.setProperty('--pointer-y', `${((event.clientY - rect.top) / rect.height - .5) * 6}px`);
      });
    });
    stage.addEventListener('pointerleave', () => { cancelAnimationFrame(frame); stage.style.setProperty('--pointer-x', '0px'); stage.style.setProperty('--pointer-y', '0px'); });
  }
  const comparison = document.querySelector('#comparison-slider');
  comparison?.addEventListener('input', () => comparison.closest('.comparison').style.setProperty('--split', `${comparison.value}%`));

  const wall = document.querySelector('.game-wall');
  if (wall && 'IntersectionObserver' in window) {
    let visible = false;
    const update = () => wall.classList.toggle('is-paused', !visible || document.hidden);
    new IntersectionObserver(entries => {
      visible = entries[0].isIntersecting;
      update();
    }).observe(wall);
    document.addEventListener('visibilitychange', update);
  }

  // Covers keep the abstract artwork underneath until a real image loads.
  function enhanceArtwork(img) {
    const art = img.closest('.game-art');
    const fallbacks = JSON.parse(img.dataset.fallbacks || '[]');
    const loaded = () => { art?.classList.add('has-image'); };
    const failed = () => {
      art?.classList.remove('has-image');
      if (fallbacks.length) img.src = fallbacks.shift();
      else { img.hidden=true; img.removeAttribute('src'); if(art?.classList.contains('prediction-artwork')) art.hidden=true; }
    };
    img.addEventListener('load',loaded);
    img.addEventListener('error',failed);
    if (img.complete) { if (img.naturalWidth) loaded(); else failed(); }
  }
  function steamCovers(game) {
    const urls=game.cover ? [`${config.root}/static/${game.cover}`] : [];
    if (game.steam_appid && /^\d+$/.test(String(game.steam_appid))) {
      const base=`https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/${game.steam_appid}`;
      urls.push(`${base}/library_600x900_2x.jpg`,`${base}/library_600x900.jpg`);
      if (game.catalog?.header) urls.push(game.catalog.header);
      urls.push(`${base}/header.jpg`);
    }
    return [...new Set(urls)];
  }
  document.querySelectorAll('[data-artwork]').forEach(enhanceArtwork);
  document.querySelectorAll('[data-optional-image]').forEach(img => {
    const hide=() => { const tile=img.closest('.screenshot-button') || img.closest('.overview-image'); if (tile) tile.hidden=true; };
    img.addEventListener('error',hide);
    if (img.complete && !img.naturalWidth) hide();
  });
  const lightbox=document.querySelector('#screenshot-dialog');
  if (lightbox) {
    const shots=[...document.querySelectorAll('[data-screenshot]')];
    const image=lightbox.querySelector('.lightbox-image');
    const previous=lightbox.querySelector('.screenshot-prev');
    const next=lightbox.querySelector('.screenshot-next');
    let index=0;
    const show = value => {
      index=value; image.src=shots[index].dataset.screenshot;
      image.alt=`${t.imageCount} ${index+1}`;
      lightbox.querySelector('.screenshot-counter').textContent=`${index+1} / ${shots.length}`;
      previous.disabled=index===0; next.disabled=index===shots.length-1;
    };
    shots.forEach((shot,i)=>shot.addEventListener('click',()=>{show(i);lightbox.showModal();}));
    previous.addEventListener('click',()=>{if(index>0)show(index-1);});
    next.addEventListener('click',()=>{if(index<shots.length-1)show(index+1);});
    lightbox.querySelector('.screenshot-close').addEventListener('click',()=>lightbox.close());
    lightbox.addEventListener('keydown',event=>{
      if(event.key==='ArrowRight' && index<shots.length-1){event.preventDefault();show(index+1);}
      if(event.key==='ArrowLeft' && index>0){event.preventDefault();show(index-1);}
    });
    lightbox.addEventListener('click',event=>{if(event.target===lightbox)lightbox.close();});
  }

  const form = document.querySelector('#database-search');
  if (!form) return;
  const input = form.querySelector('input');
  const results = document.querySelector('#game-results');
  const count = document.querySelector('#result-count');
  const more = document.querySelector('#load-more');
  const retry = document.querySelector('#retry');
  const filters = [...document.querySelectorAll('[data-filter]')];
  const params = new URLSearchParams(location.search);
  const predictionsMode = config.searchMode === 'predictions';
  // Keep links shared before the collections were separated working.
  if (!predictionsMode && (params.get('filter') === 'prediction' || params.has('game'))) {
    if (params.get('filter') === 'prediction') params.delete('filter');
    location.replace(`${config.database}predictions/${params.size ? '?' + params : ''}${location.hash}`);
    return;
  }
  const modeLinks = [...document.querySelectorAll('[data-search-mode]')];
  function updateModeLinks() {
    const query = new URLSearchParams();
    if (input.value.trim()) query.set('q', input.value.trim());
    modeLinks.forEach(link => {
      const path = link.dataset.searchMode === 'predictions' ? `${config.database}predictions/` : config.database;
      link.href = `${path}${query.size ? '?' + query : ''}`;
    });
  }
  let status = filters.some(f => f.dataset.filter === params.get('filter')) ? params.get('filter') : 'all';
  let games = [], visible = 24, ready = false, timer, pendingGame = params.get('game');
  input.value = params.get('q') || '';
  updateModeLinks();
  const normalize = value => value.normalize('NFKD').replace(/\p{Diacritic}/gu, '').toLocaleLowerCase();
  const statusName = game => game.status === 'community' ? t.communityStatus : t[game.status];
  function element(tag, className, text) {
    const node = document.createElement(tag); if (className) node.className = className; if (text !== undefined) node.textContent = text; return node;
  }
  function card(game, index) {
    const predicted = game.status === 'prediction';
    const styles = ['ember', 'forest', 'portal', 'violet'];
    const symbols = ['✦', '◈', '◌', '✧'];
    const node = element(predicted ? 'button' : 'a', `game-card ${styles[index % 4]}`);
    if (predicted) { node.type = 'button'; node.addEventListener('click', () => openPrediction(game)); }
    else node.href = `${config.home}games/${game.id}/`;
    const art = element('div', 'game-art');
    for (const name of ['card-grain','art-orb','art-landscape']) art.append(element('span', name));
    const symbol = element('span', 'art-symbol', symbols[index % 4]); symbol.setAttribute('aria-hidden', 'true'); art.append(symbol);
    art.append(element('span','placeholder-label',t.placeholder),element('span','game-art-title',game.title),element('span','game-card-arrow','↗'));
    const meta = element('div','game-card-meta');
    meta.append(element('h3','',game.title));
    const pill = element('span',`status-pill ${game.status}`);
    pill.append(element('i')); pill.append(document.createTextNode(statusName(game))); meta.append(pill);
    if (predicted) meta.append(element('small', 'prediction-verdict', t[game.prediction] || t.maybe));
    if (game.catalog?.genres?.length) {
      const genres=element('small','card-genres',game.catalog.genres.slice(0,2).join(' · '));
      genres.lang=game.catalog.language || 'en'; meta.append(genres);
    }
    const urls=steamCovers(game);
    if (urls.length) {
      const img=element('img','game-cover'); img.src=urls.shift(); img.alt='';img.loading='lazy';img.decoding='async';img.width=600;img.height=900;img.referrerPolicy='no-referrer';
      img.dataset.artwork='';img.dataset.fallbacks=JSON.stringify(urls);art.prepend(img);
      enhanceArtwork(img);
    }
    node.append(art,meta); return node;
  }
  function render(updateURL = true) {
    updateModeLinks();
    filters.forEach(f => { const active = f.dataset.filter === status; f.classList.toggle('active',active); f.setAttribute('aria-pressed',String(active)); });
    if (!ready) return;
    const words = normalize(input.value.trim()).split(/\s+/).filter(Boolean);
    const matches = games.filter(g => (status === 'all' || status === (predictionsMode ? g.prediction : g.status)) && words.every(word => g.search.includes(word)));
    count.textContent = `${new Intl.NumberFormat(config.lang).format(matches.length)} ${matches.length === 1 ? t.resultOne : t.results}`;
    const fragment = document.createDocumentFragment();
    matches.slice(0,visible).forEach((g,i) => fragment.append(card(g,i)));
    if (!matches.length) fragment.append(element('p','empty-state',t.empty));
    results.replaceChildren(fragment); more.hidden = matches.length <= visible;
    if (updateURL) {
      const next = new URLSearchParams(); if (input.value.trim()) next.set('q',input.value.trim()); if (status !== 'all') next.set('filter',status);
      if (pendingGame) next.set('game',pendingGame);
      history.replaceState(null,'',`${location.pathname}${next.size ? '?' + next : ''}${location.hash}`);
    }
  }
  async function load() {
    count.textContent = t.loading; retry.hidden = true;
    try {
      const catalogRequest=fetch(`${config.root}/data/catalog/${config.lang}.json`).then(response=>{if(!response.ok)throw Error('Catalog unavailable');return response.json();}).catch(()=>({games:{}}));
      const dataset = predictionsMode ? 'predictions' : 'games';
      const response = await fetch(`${config.root}/data/${dataset}.json`);
      if (!response.ok) throw new Error('Game data unavailable');
      const data = await response.json();
      const catalog = await catalogRequest;
      // predictions.json keeps its historical app-id keyed `games` object for external
      // consumers; `items` carries the richer records used by this interface.
      const records = data.items || (Array.isArray(data.games) ? data.games : Object.values(data.games));
      games = records.map(g => ({...g, catalog:catalog.games[String(g.steam_appid)] || null, search:normalize(g.title)}));
      ready = true; render(false);
      if (pendingGame) { const game = games.find(g => g.status === 'prediction' && String(g.steam_appid) === pendingGame); if (game) openPrediction(game); }
    } catch { count.textContent = t.error; retry.hidden = false; }
  }
  input.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(() => { visible=24;pendingGame=null;render(); },120); });
  form.addEventListener('submit',event => { event.preventDefault(); clearTimeout(timer);visible=24;render(); });
  filters.forEach(filter => filter.addEventListener('click',() => { status=filter.dataset.filter;visible=24;render(); }));
  more.addEventListener('click',() => { const previous=visible;visible+=24;render(false); results.children[previous]?.focus({preventScroll:true}); });
  retry.addEventListener('click',load);
  addEventListener('popstate',() => { const p=new URLSearchParams(location.search);input.value=p.get('q')||'';status=filters.some(f=>f.dataset.filter===p.get('filter')) ? p.get('filter') : 'all';visible=24;render(false); });
  const dialog = document.querySelector('#prediction-dialog');
  function openPrediction(game) {
    document.querySelector('#prediction-title').textContent=game.title;
    document.querySelector('#prediction-verdict').textContent=`${t[game.prediction] || t.maybe} · ProtonDB: ${game.protonTier || '—'} · ${game.reports} ${t.reports}`;
    document.querySelector('#prediction-anticheat').textContent=game.anticheat?.length ? `Anti-cheat: ${game.anticheat.join(', ')}` : '';
    const artwork=document.querySelector('#prediction-artwork');
    artwork.replaceChildren();artwork.classList.remove('has-image');
    const urls=steamCovers(game);
    if (urls.length) {
      const img=element('img','game-cover');img.src=urls.shift();img.alt='';img.width=600;img.height=900;img.dataset.fallbacks=JSON.stringify(urls);img.referrerPolicy='no-referrer';
      artwork.append(img);enhanceArtwork(img);artwork.hidden=false;
    } else artwork.hidden=true;
    document.querySelector('#prediction-store').href=`https://store.steampowered.com/app/${encodeURIComponent(game.steam_appid)}/`;
    document.querySelector('#prediction-source').href=`https://www.protondb.com/app/${encodeURIComponent(game.steam_appid)}`;
    dialog.showModal();
  }
  document.querySelector('.dialog-close').addEventListener('click',() => dialog.close());
  dialog.addEventListener('click',event => { if (event.target===dialog) { const r=dialog.getBoundingClientRect();if (event.clientX<r.left || event.clientX>r.right || event.clientY<r.top || event.clientY>r.bottom) dialog.close(); } });
  render(false); load();
})();
