const {chromium}=require('C:/Users/010726Admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const path=require('path'),assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 try{
  const page=await browser.newPage({viewport:{width:1700,height:1140}});const errors=[];
  page.on('pageerror',e=>errors.push(e.message));await page.goto('http://127.0.0.1:8770/');
  const frames=page.frames().filter(f=>/variant-\d.html$/.test(f.url()));assert.equal(frames.length,3);
  await page.screenshot({path:path.join(__dirname,'comparison.png'),fullPage:true});
  for(const frame of frames){
   assert.equal(await frame.locator('#connectionRows tr').count(),9);
   const bounds=await frame.locator('#terminalLogPane').boundingBox();assert(bounds.height>300);
   await frame.locator('.journal-help summary').click();assert(await frame.locator('.journal-help[open]').count());await frame.locator('.journal-help summary').click();
   await frame.locator('#connectionFilter').fill('knock');assert.equal(await frame.locator('#connectionRows tr').count(),1);
   await frame.locator('#connectionRows tr').click();assert.equal(await frame.locator('#connectionInspectorHost').textContent(),'api.knock.app');
   await frame.locator('#connectionPause').click();assert.equal(await frame.locator('#connectionPause').getAttribute('aria-pressed'),'true');
   await frame.locator('.terminal-toolbar button:last-child').click();assert(await frame.locator('#connectionEmpty').isVisible());
   assert.equal(await frame.evaluate(()=>typeof window.pywebview),'undefined');
  }
  await page.locator('#reset').click();for(const frame of frames)await frame.locator('#connectionRows tr').first().waitFor();
  await page.setViewportSize({width:390,height:844});assert(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth));
  assert.deepEqual(errors,[]);console.log('PASS: 3 palettes, help, filtering, selection, pause, clear/reset, mobile and bridge isolation.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
