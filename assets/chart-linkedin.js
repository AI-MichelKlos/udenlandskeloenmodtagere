(function(){
  'use strict';
  const ROOT="https://ai-michelklos.github.io/udenlandskeloenmodtagere/";
  const CARD_SELECTOR="main section";
  const ALLOWED=[];
  const FIGURE_IDS=new Set(["timeChart","shareChart","nationalityChart","branchChart","residenceChart","permitChart","regionChart","retentionChart"]);
  // This is captured before the senior dashboard rewrites its own query string.
  const paramsAtLoad=new URLSearchParams(location.search);
  const targetFigure=paramsAtLoad.get('figure')||(location.hash.startsWith('#graf-')?decodeURIComponent(location.hash.slice(6)):'');
  function linkFor(id){
    const target=new URL('share/'+encodeURIComponent(id)+'/',ROOT);
    const params=new URLSearchParams(location.search);
    for(const key of ALLOWED){
      const control=document.getElementById(key);
      const val=control&&!control.disabled?control.value:params.get(key);
      if(val!==null && val!=='')target.searchParams.set(key,val);
    }
    return target.href;
  }
  function addButtons(card){
    const visual=card.querySelector('canvas[id],svg#map');
    if(!visual||!FIGURE_IDS.has(visual.id)||card.querySelector('.mk-social-actions'))return;
    const heading=card.querySelector('h2');
    if(!heading)return;
    const row=document.createElement('div');row.className='mk-social-actions';
    const li=document.createElement('button');li.type='button';li.className='mk-linkedin-btn';
    li.textContent='Del på LinkedIn';
    li.setAttribute('aria-label','Del '+heading.textContent.trim()+' på LinkedIn');
    li.addEventListener('click',()=>window.open('https://www.linkedin.com/sharing/share-offsite/?url='+encodeURIComponent(linkFor(visual.id)),'_blank','noopener,noreferrer'));
    const copy=document.createElement('button');copy.type='button';copy.className='mk-copy-btn';
    copy.textContent='Kopiér link';copy.setAttribute('aria-label','Kopiér direkte link til '+heading.textContent.trim());
    copy.addEventListener('click',async()=>{
      const url=linkFor(visual.id);
      try{await navigator.clipboard.writeText(url);copy.textContent='Link kopieret';setTimeout(()=>copy.textContent='Kopiér link',2200);}
      catch(_){window.prompt('Kopiér link til grafen:',url);}
    });
    row.append(li,copy);
    heading.insertAdjacentElement('afterend',row);
  }
  function focusSharedFigure(){
    if(!FIGURE_IDS.has(targetFigure))return;
    let attempts=0;
    const timer=setInterval(()=>{
      const visual=document.getElementById(targetFigure);
      const card=visual?.closest('article.card, section.map-card, section');
      if(!visual||!card){if(++attempts>70)clearInterval(timer);return;}
      const chart=visual.tagName.toLowerCase()==='canvas'?window.Chart?.getChart(visual):null;
      const ready=visual.id==='map'?visual.querySelectorAll('path').length>20:!!(chart&&chart.data.datasets?.length);
      if(!ready&&attempts++<50)return;
      clearInterval(timer);
      card.classList.add('mk-share-highlight');
      card.scrollIntoView({behavior:'smooth',block:'start'});
      setTimeout(()=>card.classList.remove('mk-share-highlight'),6500);
    },220);
  }
  const style=document.createElement('style');
  style.textContent='.mk-social-actions{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:8px 0 15px}' +
    '.mk-social-actions button{min-height:37px;border:1px solid #c9bcae;border-radius:7px;padding:8px 12px;font:700 13px Arial,sans-serif;cursor:pointer;background:#fff;color:#4a3428}' +
    '.mk-social-actions .mk-linkedin-btn{background:#0a66c2;color:#fff;border-color:#0a66c2}' +
    '.mk-social-actions .mk-linkedin-btn:hover{background:#084e96;color:#fff}' +
    '.mk-social-actions .mk-copy-btn:hover{background:#f7f1ea}' +
    '.mk-social-actions button:focus-visible{outline:3px solid #146298;outline-offset:2px}' +
    '.mk-share-highlight{outline:3px solid #6B9E78!important;outline-offset:4px;scroll-margin-top:18px}' +
    '@media(max-width:550px){.mk-social-actions button{flex:1 1 42%}}';
  document.head.appendChild(style);
  function init(){
    const root=document.querySelector('main')||document.body;
    const attach=()=>document.querySelectorAll(CARD_SELECTOR).forEach(addButtons);
    attach();
    new MutationObserver(attach).observe(root,{childList:true,subtree:true});
    focusSharedFigure();
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);
  else init();
})();