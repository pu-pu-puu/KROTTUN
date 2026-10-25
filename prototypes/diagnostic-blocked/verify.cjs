const path=require('path'),assert=require('node:assert/strict');
const {pathToFileURL}=require('url');
const {chromium}=require('C:/Users/010726Admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{const browser=await chromium.launch({headless:true,channel:'msedge'});try{
for(const key of ['a','b','c']){
const page=await browser.newPage({viewport:{width:520,height:760}}),errors=[];
page.on('pageerror',e=>errors.push(e.message));await page.route('**/*',r=>r.request().url().startsWith('file:')?r.continue():r.abort());
await page.goto(pathToFileURL(path.join(__dirname,`${key}.html`)).href);
for(const width of [520,480]){
await page.setViewportSize({width,height:760});
for(const state of ['blocked','unknown']){
await page.evaluate(state=>showBlockedDemo(state),state);
const modal=page.locator('#modalDiagnostics .modal-card'),text=await modal.innerText();
assert.doesNotMatch(text,/Проверка завершена/);
if(state==='unknown'){assert.match(text,/Нет данных|неизвестно/);assert.doesNotMatch(text,/Заблокирован|заблокирован|блокирует/);}else assert.match(text,/Заблокирован|заблокирован/);
const b=await modal.boundingBox();assert(b.x>=0&&b.x+b.width<=width&&b.y>=19&&b.y+b.height<=741,JSON.stringify(b));
assert(await modal.evaluate(el=>el.scrollHeight<=el.clientHeight&&el.scrollWidth<=el.clientWidth));
await page.screenshot({path:path.join(__dirname,`${key}-${state}-${width}.png`)});
await page.locator('[data-home-action]').focus();await page.keyboard.press('Enter');
assert.equal(await page.locator('#modalDiagnostics.open').count(),0);assert(await page.locator('#viewHome').isVisible());
await page.locator('#btnDiagnostics').click();assert(await page.locator('#modalDiagnostics.open').count());
}
}
if(key==='c'){
await page.locator('.blocked-details summary').focus();await page.keyboard.press('Enter');
assert(await page.locator('.blocked-details').evaluate(el=>el.open));
}
assert.deepEqual(errors,[]);await page.close();
}
const gallery=await browser.newPage({viewport:{width:1680,height:1090}});
await gallery.route('**/*',r=>r.request().url().startsWith('file:')?r.continue():r.abort());
await gallery.goto(pathToFileURL(path.join(__dirname,'index.html')).href);
await gallery.screenshot({path:path.join(__dirname,'comparison.png'),fullPage:true});
await gallery.locator('#scenario').selectOption('unknown');
for(const frame of gallery.frames().slice(1))await frame.locator('#modalDiagnostics[data-state="unknown"]').waitFor();
console.log('PASS A/B/C 480/520: confirmed/unknown copy, modal bounds, keyboard home/details, reopen and gallery selector; external requests aborted');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
