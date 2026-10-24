// Regression: real protection state rendering must never shift the main controls.
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const {chromium}=require('C:/Users/010726Admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const html=fs.readFileSync(path.resolve(__dirname,'../../gui/web/index.html'),'utf8');
 const updater=html.match(/let protectionState='unknown'[\s\S]*?(?=    async function releaseProtection)/)[0];
 let clean=html.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,'').replace(/\s+on\w+="[^"]*"/g,'');
 const banner=fs.readFileSync(path.resolve(__dirname,'../../gui/web/krottun_banner.png')).toString('base64');
 clean=clean.replace(/src="krottun_banner[^"\s]*\.png"/g,`src="data:image/png;base64,${banner}"`);
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 try {
  const page=await browser.newPage({viewport:{width:520,height:760}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.setContent(clean);await page.addScriptTag({content:updater});
  for(const width of [520,480]){
   await page.setViewportSize({width,height:760});const states=[];
   for(const state of ['unknown','connecting','switching','protected','blocked','unarmed','protected']){
    await page.evaluate(state=>updateProtectionStrip(state),state);
    states.push(await page.evaluate(state=>{
     const box=id=>{const r=document.getElementById(id).getBoundingClientRect();return {top:r.top,height:r.height}};
     const hint=document.getElementById('protectionHelper');
     return {state,strip:box('protectionStrip'),timer:box('liveTimer'),toggle:box('toggleTrack'),button:box('protectionRelease'),hintFits:hint.scrollHeight<=hint.clientHeight,buttonVisible:getComputedStyle(document.getElementById('protectionRelease')).visibility!=='hidden'};
    },state));
   }
   console.log(JSON.stringify({width,states}));
   for(const value of states){
    for(const id of ['strip','timer','toggle','button'])assert.deepEqual(value[id],states[0][id],`${width}: ${id} moved in ${value.state}`);
    assert(value.hintFits,`${width}: clipped helper in ${value.state}`);
    assert.equal(value.buttonVisible,value.state!=='unarmed','release visibility');
   }
  }
  await page.setViewportSize({width:520,height:760});
  await page.evaluate(()=>updateProtectionStrip('switching'));
  await page.screenshot({path:path.join(__dirname,'protection-layout-fixed.png')});
  assert.deepEqual(errors,[]);console.log('PASS: stable geometry across every protection state; helper fits; unarmed action hidden.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e.message);process.exitCode=1});
