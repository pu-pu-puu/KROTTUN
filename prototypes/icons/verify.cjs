const {chromium}=require('C:/Users/010726Admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const path=require('path');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 try{
  const page=await browser.newPage({viewport:{width:1160,height:1100}});const errors=[];
  page.on('pageerror',e=>errors.push(e.message));await page.goto('http://127.0.0.1:8769/');
  const after=page.frames().find(f=>f.url().endsWith('after.html'));
  if(await after.locator('.ui-icon').count()<10)throw Error('missing icons');
  for(const view of ['info','home','servers']){
   await page.locator(`[data-view="${view}"]`).click();
   for(const frame of page.frames().filter(f=>/\/(before|after)\.html$/.test(f.url()))){
    await frame.locator('#view'+view[0].toUpperCase()+view.slice(1)).waitFor({state:'visible'});
    if(await frame.evaluate(()=>typeof window.pywebview!=='undefined'))throw Error('app bridge loaded');
   }
   await page.screenshot({path:path.join(__dirname,view+'.png'),fullPage:true});
  }
  await page.setViewportSize({width:390,height:844});
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('overflow');
  if(errors.length)throw Error(errors.join('\n'));
  console.log('PASS: SVG icons, three comparison views, mobile width, no bridge or JS errors.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
