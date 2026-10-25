const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const {chromium}=require('C:/Users/010726Admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{const browser=await chromium.launch({headless:true,channel:'msedge'});try{
const page=await browser.newPage({viewport:{width:520,height:760}}),errors=[];
page.setDefaultTimeout(1500);page.on('pageerror',e=>errors.push(e.message));await page.route('**/*',r=>r.abort());
await page.evaluate(()=>{window.setInterval=()=>0;window.demoReason='protection_blocked';window.demoStatus='done';window.winFlag='pass';window.demoCalls=[];window.pywebview={api:{
 start_diagnostics:async()=>({success:true,run_id:'fixture'}),cancel_diagnostics:async()=>({success:true}),
 get_diagnostics:async()=>({run_id:'fixture',status:demoStatus,availability_reason:demoReason,checks:['proxy','dns','https','ip','system_proxy'].map(id=>({id,status:id==='system_proxy'?winFlag:demoReason?'skipped':'pass',detail:'Fixture result'}))}),
 toggle_tun:async()=>{demoCalls.push('connect')},release_protection:async()=>{demoCalls.push('release')}
}}});
await page.setContent(fs.readFileSync(path.resolve(__dirname,'../../gui/web/index.html'),'utf8'));
for(const width of [480,520]){
await page.setViewportSize({width,height:760});await page.evaluate(()=>openDiagnostics());
assert.match(await page.locator('#diagnosticAvailabilityTitle').innerText(),/Интернет заблокирован защитой/);
assert.equal(await page.locator('#diagnosticStatus').isVisible(),false);
assert.equal(await page.locator('#diagnosticRows').getByText('Не выполнялась',{exact:true}).count(),4);
const bounds=await page.locator('#modalDiagnostics .modal-card').boundingBox();assert(bounds.y>=19&&bounds.y+bounds.height<=741&&bounds.x>=0&&bounds.x+bounds.width<=width);
await page.screenshot({path:path.join(__dirname,`production-a-${width}.png`)});
await page.locator('#diagnosticHome').focus();await page.keyboard.press('Enter');
assert.equal(await page.locator('#modalDiagnostics.open').count(),0);assert(await page.locator('#viewHome').isVisible());assert.deepEqual(await page.evaluate(()=>demoCalls),[]);
}
for(const [reason,expected] of [['protection_unknown','Состояние защиты неизвестно'],['no_proxy','Сервер не выбран'],['unavailable','Диагностика сейчас недоступна']]){
await page.evaluate(reason=>{demoReason=reason;return openDiagnostics()},reason);
assert.equal(await page.locator('#diagnosticAvailabilityTitle').innerText(),expected);
assert.doesNotMatch(await page.locator('#modalDiagnostics').innerText(),/заблокирован|блокирует/);
if(reason==='no_proxy'){await page.locator('#diagnosticHome').click();assert(await page.locator('#viewServers').isVisible());}else await page.evaluate(()=>closeModals());
}
for(const flag of ['pass','warning','skipped']){
await page.evaluate(flag=>{winFlag=flag;demoReason='protection_blocked';return openDiagnostics()},flag);
const label=await page.locator('#diagnosticRows .diagnostic-row').last().innerText();assert.match(label,flag==='pass'?/Выключен/:flag==='warning'?/Включён/:/Не удалось определить/);
await page.evaluate(()=>closeModals());
}
for(const status of ['done','cancelled']){
await page.evaluate(status=>{demoStatus=status;demoReason=status==='cancelled'?'protection_blocked':null;return openDiagnostics()},status);
assert.equal(await page.locator('#diagnosticAvailability').isVisible(),false);
assert.equal(await page.locator('#diagnosticHome').isVisible(),false);
assert.equal(await page.locator('#diagnosticStatus').innerText(),status==='done'?'Проверка завершена':'Подключение изменилось. Запустите проверку снова.');
await page.evaluate(()=>closeModals());
}
await page.evaluate(()=>{demoStatus='done';pywebview.api.start_diagnostics=async()=>{throw Error('offline')};return openDiagnostics()});
assert.equal(await page.locator('#diagnosticAvailability').isVisible(),false);assert.match(await page.locator('#diagnosticStatus').innerText(),/Нет ответа/);
assert.deepEqual(errors,[]);console.log('PASS production blocked A 480/520; explicit reason/unknown/no-proxy/transition/cancel/error; OS proxy variants; home action never changes network; normal diagnostics reset; external requests aborted');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
