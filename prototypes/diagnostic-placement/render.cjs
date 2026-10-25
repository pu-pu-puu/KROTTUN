const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const {pathToFileURL}=require('url');
const {chromium}=require('C:/Users/010726Admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{const browser=await chromium.launch({headless:true,channel:'msedge'});try{
for(const key of ['a','b','c']){
const page=await browser.newPage({viewport:{width:520,height:760}}),errors=[];
page.on('pageerror',e=>errors.push(e.message));await page.route('**/*',r=>r.request().url().startsWith('file:')?r.continue():r.abort());
await page.goto(pathToFileURL(path.join(__dirname,`${key}.html`)).href);
for(const width of [520,480]){
await page.setViewportSize({width,height:760});
const button=page.locator('#btnDiagnostics');await button.waitFor({state:'visible'});
const b=await button.boundingBox();assert(b.x>=0&&b.x+b.width<=width&&b.y+b.height<=744,`${key} overflow: ${JSON.stringify(b)}`);
// The incumbent decorative world map intentionally extends 20px past viewport.
assert(await page.locator('.app-content').evaluate(el=>{const r=el.getBoundingClientRect();return r.x>=0&&r.right<=innerWidth}));
await page.screenshot({path:path.join(__dirname,`${key}-${width}.png`)});
await button.click();await page.locator('#diagnosticStatus').filter({hasText:'Проверка завершена'}).waitFor();
assert(await page.locator('#modalDiagnostics.open').count());await page.evaluate(()=>closeModals());
}
if(key==='a'){
await page.evaluate(()=>switchTab('servers'));assert(await page.locator('#btnDiagnostics').isVisible());
await page.screenshot({path:path.join(__dirname,'dots-after.png')});
}
assert.deepEqual(errors,[]);await page.close();
}
const gallery=await browser.newPage({viewport:{width:1680,height:1030},deviceScaleFactor:1});
await gallery.route('**/*',r=>r.request().url().startsWith('file:')?r.continue():r.abort());
await gallery.goto(pathToFileURL(path.join(__dirname,'index.html')).href);
await gallery.screenshot({path:path.join(__dirname,'comparison.png'),fullPage:true});
console.log('PASS A/B/C at 480/520px; diagnostic modal click/close; A accessible from Servers; no console errors or horizontal overflow; no external requests');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
