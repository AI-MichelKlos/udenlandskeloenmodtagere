'use strict';
const fs=require('node:fs');
const path=require('node:path');
const sharp=require('sharp');
const {chromium}=require('playwright');

const ROOT=path.resolve(__dirname,'..');
const IDS=["timeChart","shareChart","nationalityChart","branchChart","residenceChart","permitChart","regionChart","retentionChart"];
const SITE="Udenlandske lønmodtagere";
const HEADING="UDENLANDSKE LØNMODTAGERE";
const SOURCE="Kilde: Jobindsats.dk";
const IS_SENIOR=false;
const OUT=path.join(ROOT,'assets','share-previews');
fs.mkdirSync(OUT,{recursive:true});
const xml=x=>String(x).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
function heading(id){
  const page=fs.readFileSync(path.join(ROOT,'share',id,'index.html'),'utf8');
  const raw=page.match(/<meta property="og:title" content="([^"]+)"/)?.[1];
  if(!raw)throw Error('Missing OG title for '+id);
  return raw.replace(/&amp;/g,'&').replace(/&lt;/g,'<').replace(/&quot;/g,'"');
}
function lines(text,max=49){
  const words=text.split(/\s+/),out=[];let line='';
  for(const word of words){if(line && (line+' '+word).length>max){out.push(line);line=word;}else line=(line?line+' ':'')+word;}
  if(line)out.push(line);
  return out.slice(0,2);
}
async function renderCard(title,canvasBytes,isReal){
  const names=lines(title);
  const svg=`<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630">
    <rect width="1200" height="630" fill="#f7f1ea"/>
    <rect x="24" y="24" width="1152" height="582" rx="15" fill="#fff" stroke="#e6ddd2"/>
    <rect x="24" y="24" width="1152" height="9" fill="#6B9E78"/>
    <text x="60" y="79" fill="#4a3428" font-family="Arial" font-weight="700" font-size="20">${xml(HEADING)}</text>
    ${names.map((row,i)=>`<text x="60" y="${120+i*37}" fill="#2B211B" font-family="Arial" font-size="31" font-weight="700">${xml(row)}</text>`).join('')}
    ${isReal?'':`<text x="66" y="356" font-family="Arial" font-size="35" font-weight="700" fill="#4a3428">Se den interaktive graf</text><text x="66" y="399" font-family="Arial" font-size="22" fill="#6f6258">på Michel Klos' dashboard</text>`}
    <line x1="60" y1="541" x2="1137" y2="541" stroke="#e6ddd2" stroke-width="2"/>
    <text x="60" y="566" fill="#6f6258" font-family="Arial" font-size="16">${xml(SOURCE)}</text>
    <text x="60" y="588" fill="#4a3428" font-family="Arial" font-size="17" font-weight="700">Udarbejdet af Michel Klos</text>
    <text x="1137" y="588" text-anchor="end" fill="#6f6258" font-family="Arial" font-size="16">${IS_SENIOR?'Valgte aldersfiltre følger med linket':'Se seneste tal i dashboardet'}</text>
  </svg>`;
  const base=sharp(Buffer.from(svg));
  if(!isReal||!canvasBytes)return base.png().toBuffer();
  const resized=await sharp(canvasBytes).resize(1080,350,{fit:'contain',background:'#fff'}).png().toBuffer();
  return base.composite([{input:resized,left:60,top:180}]).png().toBuffer();
}
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1480,height:1020},deviceScaleFactor:1});
 const results=[];
 page.on('pageerror',e=>console.warn('Page JS:',e.message.split('\n')[0]));
 try {
  await page.goto('http://127.0.0.1:8765/',{waitUntil:'domcontentloaded',timeout:45000});
  for(const id of IDS){
   let bytes=null;
   try{
    if(id==='map'){
      await page.waitForFunction(()=>document.querySelectorAll('#map path').length>=60,null,{timeout:25000});
    }else{
      await page.waitForFunction(id=>{
        const canvas=document.getElementById(id);
        const graph=canvas&&window.Chart?.getChart(canvas);
        return !!(graph&&canvas.width>0&&canvas.height>0&&graph.data.datasets?.length);
      },id,{timeout:30000});
    }
    bytes=await page.locator('#'+id).screenshot({animations:'disabled',timeout:15000});
   }catch(e){console.warn('No rendered chart for',id,'using labelled fallback:',e.message.split('\n')[0]);}
   const png=await renderCard(heading(id),bytes,!!bytes);
   const dest=path.join(OUT,id+'.png');
   fs.writeFileSync(dest,png);
   const info=await sharp(dest).metadata();
   if(info.width!==1200||info.height!==630||info.format!=='png')throw Error('Invalid preview dimensions '+id);
   console.log((bytes?'REAL':'FALLBACK'),id,fs.statSync(dest).size,'bytes');
   results.push({id,real:!!bytes,bytes:fs.statSync(dest).size});
  }
 }finally{await browser.close();}
 const meta={generatedAt:new Date().toISOString(),dashboard:SITE,real:results.filter(r=>r.real).length,fallback:results.filter(r=>!r.real).length,files:results};
 fs.mkdirSync(path.join(ROOT,'status'),{recursive:true});
 fs.writeFileSync(path.join(ROOT,'status','share-previews.json'),JSON.stringify(meta,null,2)+'\n');
 console.log('RESULT',JSON.stringify(meta));
 if(meta.fallback)console.warn('Some images are branded fallback previews; consult status/share-previews.json');
})().catch(e=>{console.error(e);process.exitCode=1;});
