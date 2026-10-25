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
assert(await page.locator('#viewInfo').isVisible());
const text=await page.locator('#viewInfo').innerText();assert.match(text,/2\.6\.0/);assert.match(text,/Telegram/);assert.doesNotMatch(text,/возможны LAN|ag_dns|via stdin/);
assert.equal(await page.locator('#viewInfo [onclick]').count(),0,'no pretend settings');
assert(await page.locator('#viewInfo').evaluate(el=>el.scrollWidth<=el.clientWidth));
await page.screenshot({path:path.join(__dirname,`${key}-${width}.png`)});
console.log(key,width,await page.locator('#viewInfo').evaluate(el=>({height:el.clientHeight,content:el.scrollHeight})));
for(const state of ['unarmed','unknown','running']){
await page.evaluate(state=>setDemoState(state),state);
const expected=state==='unarmed'?'Туннель не подключён':state==='unknown'?'Нет данных о подключении':'Туннель работает';
assert.equal(await page.locator('[data-demo-connection]').innerText(),expected);
if(state==='unknown')assert.equal(await page.locator('[data-demo-admin]').innerText(),'Нет данных');
}
}
for(const details of await page.locator('#viewInfo details').all()){
const before=await details.evaluate(el=>el.open);
await details.locator('summary').focus();await page.keyboard.press('Enter');
assert.equal(await details.evaluate(el=>el.open),!before);
}
assert.deepEqual(errors,[]);await page.close();
}
const gallery=await browser.newPage({viewport:{width:1680,height:1090},deviceScaleFactor:1});
await gallery.route('**/*',r=>r.request().url().startsWith('file:')?r.continue():r.abort());
await gallery.goto(pathToFileURL(path.join(__dirname,'index.html')).href);
await gallery.screenshot({path:path.join(__dirname,'comparison.png'),fullPage:true});
await gallery.locator('#scenario').selectOption('unknown');
for(const frame of gallery.frames().slice(1))await frame.locator('[data-demo-connection]').filter({hasText:'Нет данных о подключении'}).waitFor();
console.log('PASS three Info variants 480/520; version, truthful routing copy, no fake switch, demo states and keyboard details; gallery selector; no external requests or page errors');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
