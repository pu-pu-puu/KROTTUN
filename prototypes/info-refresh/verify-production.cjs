const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const {chromium}=require('C:/Users/010726Admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{const browser=await chromium.launch({headless:true,channel:'msedge'});try{
const page=await browser.newPage({viewport:{width:520,height:760}}),errors=[];
page.on('pageerror',e=>errors.push(e.message));await page.route('**/*',r=>r.abort());
await page.evaluate(()=>{window.setInterval=()=>0;window.demoState={app_version:'2.6.0',state:'running',is_running:true,proxy_reachable:true,is_admin:true,protection:'protected',proxies:[],settings:{bypass_telegram:true}};window.pywebview={api:{get_state:async()=>demoState,get_telemetry:async()=>demoState}}});
await page.setContent(fs.readFileSync(path.resolve(__dirname,'../../gui/web/index.html'),'utf8'));
await page.evaluate(()=>{switchTab('info');return refreshState()});
assert.equal(await page.locator('#infoAppVersion').innerText(),'v2.6.0');
assert.equal(await page.locator('#infoAdminStatus').innerText(),'Права есть');
assert.equal(await page.locator('#infoConnectionStatus').innerText(),'Туннель работает');
assert.equal(await page.locator('#viewInfo [onclick]').count(),0);
assert.equal(await page.evaluate(()=>typeof toggleBypassTelegram),'undefined');
assert.doesNotMatch(await page.locator('#viewInfo').innerText(),/ag_dns|возможны LAN|готов к работе|Напрямую/);
for(const width of [480,520]){
await page.setViewportSize({width,height:760});
const fit=await page.locator('#viewInfo').evaluate(el=>({w:el.scrollWidth<=el.clientWidth,h:el.scrollHeight<=el.clientHeight}));
assert(fit.w&&fit.h,JSON.stringify(fit));
await page.screenshot({path:path.join(__dirname,`production-a-${width}.png`)});
}
for(const [state,label] of [['starting','Подключение…'],['stopping','Отключение…'],['error','Ошибка подключения'],['idle','Туннель не подключён']]){
await page.evaluate(state=>{demoState.state=state;return pollTelemetry()},state);
assert.equal(await page.locator('#infoConnectionStatus').innerText(),label);
}
await page.evaluate(()=>{demoState.state='running';demoState.proxy_reachable=false;return refreshState()});
assert.equal(await page.locator('#infoConnectionStatus').innerText(),'Выход не подтверждён');
await page.evaluate(()=>{demoState.is_admin=false;demoState.app_version='9.8.7';return refreshState()});
assert.equal(await page.locator('#infoAppVersion').innerText(),'v9.8.7');
assert.equal(await page.locator('#infoAdminStatus').innerText(),'Нет прав');
await page.evaluate(()=>{demoState={};return refreshState()});
assert.equal(await page.locator('#infoAppVersion').innerText(),'Версия недоступна');
assert.equal(await page.locator('#infoAdminStatus').innerText(),'Нет данных');
assert.equal(await page.locator('#infoConnectionStatus').innerText(),'Нет данных о подключении');
await page.evaluate(()=>{pywebview.api.get_state=async()=>{throw Error('offline')};return refreshState()});
assert.deepEqual(errors,[]);
console.log('PASS production passport A: backend version, non-clickable Telegram, layout 480/520, truthful lifecycle/admin/unreachable/unknown states, no page errors or external requests');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
