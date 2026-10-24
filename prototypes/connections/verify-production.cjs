const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const {chromium}=require('C:/Users/010726Admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 try{
  const page=await browser.newPage({viewport:{width:520,height:760}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.evaluate(()=>{window.setInterval=()=>0});
  let html=fs.readFileSync(path.resolve(__dirname,'../../gui/web/index.html'),'utf8');
  const banner=fs.readFileSync(path.resolve(__dirname,'../../gui/web/krottun_banner.png')).toString('base64');
  html=html.replace(/src="krottun_banner[^"\s]*\.png"/g,`src="data:image/png;base64,${banner}"`);
  await page.setContent(html);
  await page.evaluate(async()=>{
   const names=['cmp2-fra1.steamserver.net','api.knock.app','codex-cloud-backend.chatgpt.com','cmp1-sto1.steamserver.net','example.com','api.telegram.org','1.1.1.1'];
   window.pywebview={api:{get_connections:async()=>({cursor:1,source:'snapshot',rows:names.map((destination,i)=>({kind:'connection',connection_key:String(i),timestamp:1792811549-i,destination,address:'192.0.2.'+(i+1),port:443,process:i%2?'C:\\Apps\\chrome.exe':'ChatGPT.exe',protocol:'tcp',route:'proxy-out'}))}),clear_connections:async()=>({})}};
   switchTab('connections');updateProtectionStrip('protected');await pollConnections();selectConnection('2');
  });
  assert.equal(await page.locator('#connectionSource').textContent(),'Источник: снимки ядра');
  assert.equal(await page.locator('#connectionRows tr').count(),7);
  assert.equal(await page.locator('.terminal-table th').count(),7);
  assert.equal(await page.locator('#terminalLogPane').evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(7, 24, 46)');
  assert.equal(await page.locator('#connectionInspectorHost').textContent(),'codex-cloud-backend.chatgpt.com');
  await page.screenshot({path:path.join(__dirname,'production.png')});
  const before=await page.locator('#terminalLogPane').boundingBox();await page.locator('.journal-help summary').click();
  assert.equal((await page.locator('#terminalLogPane').boundingBox()).y,before.y);
  assert(await page.locator('.journal-help p').last().isVisible());await page.locator('.journal-help summary').click();
  await page.locator('#connectionFilter').fill('knock');assert.equal(await page.locator('#connectionRows tr').count(),1);
  await page.locator('#connectionPause').click();assert.equal(await page.locator('#connectionPause').textContent(),'Продолжить');
  await page.locator('.terminal-toolbar button:last-child').click();assert(await page.locator('#connectionEmpty').isVisible());
  await page.evaluate(async()=>{window.pywebview.api.get_connections=async()=>{throw Error('offline')};toggleConnectionPause();await pollConnections()});
  assert.equal(await page.locator('#connectionSource').textContent(),'Источник: недоступен');
  assert.deepEqual(errors,[]);console.log('PASS: production palette, real render/selection/filter/pause/clear, truthful unavailable status, 7 columns and help without layout shift.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
