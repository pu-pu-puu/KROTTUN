const {chromium} = require('C:/Users/010726Admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const path = require('path');
const {pathToFileURL} = require('url');
(async()=>{
  const browser = await chromium.launch({headless:true,channel:'msedge'});
  const page = await browser.newPage({viewport:{width:1700,height:1060},deviceScaleFactor:1});
  const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(pathToFileURL(path.join(__dirname,'index.html')).href);
  await page.waitForTimeout(900);
  await page.screenshot({path:path.join(__dirname,'comparison.png'),fullPage:true});
  const frames=page.frames().filter(f=>f.url().includes('preview.html'));
  for(const frame of frames){
    const info=await frame.evaluate(()=>({variant:document.body.dataset.variant,capitals:document.querySelectorAll('.capital').length,animations:document.getAnimations().length,bridge:typeof window.pywebview,top:getComputedStyle(document.querySelector('.world-map-layer')).top}));
    if(info.capitals!==13||!info.animations||info.bridge!=='undefined') throw Error(JSON.stringify(info));
    console.log(JSON.stringify(info));
  }
  await page.locator('#pause').click();
  await page.waitForTimeout(80);
  for(const frame of frames) if(!await frame.evaluate(()=>document.getAnimations().every(a=>a.playState==='paused'))) throw Error('pause failed');
  await page.locator('#focus').click();
  await page.waitForTimeout(80);
  if(!await frames[0].evaluate(()=>document.body.classList.contains('focus'))) throw Error('focus failed');
  await page.screenshot({path:path.join(__dirname,'maps-only.png'),fullPage:true});
  await page.locator('#focus').click();
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:path.join(__dirname,'mobile.png'),fullPage:true});
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)) throw Error('mobile overflow');
  await page.emulateMedia({reducedMotion:'reduce'});
  for(const frame of frames) if(await frame.evaluate(()=>document.getAnimations().length)) throw Error('reduced motion failed');
  if(errors.length) throw Error(errors.join('\n'));
  console.log('PASS: 3 variants; pause; map-only; mobile; reduced motion; no JS errors.');
  await browser.close();
})().catch(e=>{console.error(e);process.exitCode=1});
