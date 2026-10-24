// Full production HTML, isolated fake bridge; every external request is aborted.
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const {chromium}=require('C:/Users/010726Admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 try {
  const page=await browser.newPage({viewport:{width:520,height:760}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',route=>route.abort());
  await page.evaluate(()=>{
   window.setInterval=()=>0;
   const originalTimeout=window.setTimeout.bind(window);
   window.setTimeout=(fn,ms,...args)=>originalTimeout(fn,ms===12000&&window.fastDeadline?50:ms,...args);
   window.fixtureProxies=[{id:'a',tag:'Основной',host:'primary.invalid',port:1080,protocol:'socks5',username:'',location_name:'Test',latency_ms:12},{id:'b',tag:'Резерв B',host:'reserve.invalid',port:1080,protocol:'http',username:'',location_name:'Test'},{id:'c',tag:'<img src=x onerror=window.__xss=1>',host:'third.invalid',port:1080,protocol:'socks5',username:'',location_name:'Test'}];
   window.calls=[]; window.editSuccess=false; window.fallbackIds=['a','b','c']; window.diagMode='mixed'; window.diagCounter=0; window.pollCount=0;window.pendingPolls=0;window.maxPending=0;
   window.diagnosticFixture=()=>({run_id:window.diagMode==='stale'?'old':window.currentRun,status:window.diagMode==='running'?'running':'done',checks:['proxy','dns','https','ip','system_proxy'].map((id,i)=>({id,label:['Доступность прокси (TCP)','DNS через прокси (DoH)','HTTPS','Внешний IP','Системный прокси Windows'][i],status:window.diagMode==='running'?'running':['pass','fail','pass','skipped','warning'][i],detail:i===0?'TCP доступен; авторизация проверяется HTTPS.':i===1?'Нет DNS-ответа. Проверьте выбранный сервер.':i===4?'Возможен конфликт с TUN. Проверьте Windows вручную.':'Результат проверки'}))});
   window.pywebview={api:{
    get_state:async()=>({is_running:false,active_proxy:null,selected_proxy:window.fixtureProxies[0],proxies:window.fixtureProxies,is_admin:true,settings:{},network_warning:'',protection_state:'unarmed'}),
    edit_proxy:async(...args)=>{window.calls.push(['edit',...args]);return window.editSuccess?{success:true}:{success:false,error:'Ошибка записи. Повторите попытку.'}},
    get_fallbacks:async()=>({success:true,proxies:window.fixtureProxies,fallback_proxy_ids:window.fallbackIds}),
    set_fallbacks:async(ids)=>{window.calls.push(['fallback',ids]);window.fallbackIds=ids;return {success:true}},
    start_diagnostics:async()=>{window.calls.push(['start']);if(window.diagMode==='start-error')throw Error('private');window.currentRun='run'+(++window.diagCounter);return {success:true,run_id:window.currentRun}},
    get_diagnostics:async()=>{window.pollCount++;window.pendingPolls++;window.maxPending=Math.max(window.maxPending,window.pendingPolls);try{if(window.diagMode==='get-error')throw Error('private');if(window.diagMode==='hang')return await new Promise(resolve=>window.releasePoll=resolve);return window.diagnosticFixture()}finally{window.pendingPolls--}},
    cancel_diagnostics:async()=>{window.calls.push(['cancel']);return {success:true}},
    get_connections:async()=>({rows:[],source:'snapshot',available:true}),get_telemetry:async()=>({state:'idle',protection_state:'unarmed'})
   }};
  });
  const root=path.resolve(__dirname,'../..'); let html=fs.readFileSync(path.join(root,'gui/web/index.html'),'utf8');
  const banner=fs.readFileSync(path.join(root,'gui/web/krottun_banner.png')).toString('base64');
  html=html.replace(/src="krottun_banner[^"\s]*\.png"/g,`src="data:image/png;base64,${banner}"`);
  const baseline=require('child_process').execFileSync('git',['show','78821d8:gui/web/index.html'],{cwd:root,encoding:'utf8'});
  for(const pattern of [/body::before\s*\{[^}]+\}/,/<div class="world-map-layer"[^>]*>\s*(<svg[\s\S]*?<\/svg>)/])assert.equal(html.match(pattern)[0].replace(/\r\n/g,'\n'),baseline.match(pattern)[0].replace(/\r\n/g,'\n'));
  await page.setContent(html);await page.evaluate(()=>refreshState());
  const capture=async name=>{await page.waitForTimeout(320);await page.screenshot({path:path.join(__dirname,name+'.png')})};
  const fits=async(selector)=>{const b=await page.locator(selector).boundingBox();assert(b&&b.x>=0&&b.y>=19&&b.x+b.width<=521&&b.y+b.height<=741,JSON.stringify(b));};
  await page.evaluate(()=>{switchTab('servers');openEditModal('a')});
  assert.equal(await page.locator('#addPass').inputValue(),'');
  await page.locator('#addPort').fill('0');await page.locator('#saveProxyButton').click();
  assert.equal(await page.evaluate(()=>calls.length),0);
  await page.locator('#addPort').fill('1081');await page.locator('#addTag').fill('<svg onload=window.__xss=1>');
  await page.locator('#addPass').fill('synthetic replacement');await page.locator('#saveProxyButton').click();
  assert.equal(await page.locator('#addPass').inputValue(),'synthetic replacement');
  await fits('#modalAdd .modal-card');await capture('edit-error');
  await page.evaluate(()=>closeModals());assert.equal(await page.locator('#addPass').inputValue(),'');
  await page.evaluate(()=>{editSuccess=true;openEditModal('a')});await page.locator('#saveProxyButton').click();
  assert.equal(await page.evaluate(()=>calls.filter(c=>c[0]==='edit').at(-1)[6]),'');
  await page.evaluate(()=>openEditModal('a'));await page.locator('#clearPassword').check();await page.locator('#saveProxyButton').click();
  assert.equal(await page.evaluate(()=>calls.filter(c=>c[0]==='edit').at(-1)[8]),true);
  await page.evaluate(()=>openFallbackModal());
  await page.locator('#fallbackRows .fallback-row').nth(1).getByRole('button',{name:/Поднять/}).click();
  await page.locator('#saveFallbackButton').click();assert.deepEqual(await page.evaluate(()=>fallbackIds),['c','b']);
  await page.evaluate(()=>openFallbackModal());
  for(const c of await page.locator('#fallbackRows input').all())await c.uncheck();
  assert.match(await page.locator('#fallbackEmpty').innerText(),/Без резервов/);
  await fits('#modalFallbacks .modal-card');await capture('fallback-empty');
  await page.locator('#saveFallbackButton').click();assert.deepEqual(await page.evaluate(()=>fallbackIds),[]);
  await page.evaluate(()=>{switchTab('home');openDiagnostics()});
  await page.waitForFunction(()=>document.querySelector('#diagnosticStatus').textContent==='Проверка завершена');
  assert.equal(await page.locator('#diagnosticRows .diagnostic-row').count(),5);
  for(const state of ['pass','fail','warning','skipped'])assert(await page.locator(`#diagnosticRows [data-status=${state}]`).count()>0);
  await fits('#modalDiagnostics .modal-card');await capture('diagnostics-results');
  await page.evaluate(()=>{closeModals();diagMode='running';openDiagnostics();openDiagnostics()});await page.waitForTimeout(460);
  assert.equal(await page.evaluate(()=>maxPending),1);const starts=await page.evaluate(()=>calls.filter(c=>c[0]==='start').length);
  await page.evaluate(()=>closeModals());const polls=await page.evaluate(()=>pollCount);await page.waitForTimeout(450);assert.equal(await page.evaluate(()=>pollCount),polls);
  for(const [mode,message]of [['stale','устарел'],['start-error','Нет ответа'],['get-error','Не удалось получить']]){
   await page.evaluate(m=>{diagMode=m;openDiagnostics()},mode);await page.waitForFunction(m=>document.querySelector('#diagnosticStatus').textContent.includes(m),message);
   await page.evaluate(()=>closeModals());
  }
  await page.evaluate(()=>{diagMode='hang';fastDeadline=true;openDiagnostics()});
  await page.waitForFunction(()=>document.querySelector('#diagnosticStatus').textContent.includes('Время проверки истекло'));
  await capture('diagnostics-timeout');
  await page.evaluate(()=>{closeModals();openDiagnostics()});await page.waitForFunction(()=>document.querySelector('#diagnosticStatus').textContent.includes('Нет ответа'));
  assert.equal(await page.evaluate(()=>maxPending),1);
  await page.evaluate(()=>{closeModals();releasePoll(diagnosticFixture());diagMode='mixed';fastDeadline=false});await page.waitForTimeout(20);
  await page.evaluate(()=>openDiagnostics());await page.waitForFunction(()=>document.querySelector('#diagnosticStatus').textContent==='Проверка завершена');
  // Hostile strings remain text in rendered rows, including diagnostics.
  await page.evaluate(()=>renderDiagnostics([{id:'dns',label:'<img src=x onerror=window.__xss=1>',status:'fail',detail:'<svg onload=window.__xss=1>'}]));
  assert.equal(await page.evaluate(()=>window.__xss||0),0);assert.equal(await page.locator('#diagnosticRows img,#diagnosticRows svg,#serversListContainer img[src=x]').count(),0);
  await page.evaluate(()=>{closeModals();switchTab('home')});await capture('home');
  assert.equal(await page.locator('.capital-light').count(),13);
  const geometry=[];
  for(const state of ['unknown','connecting','switching','protected','blocked','unarmed']){
   await page.evaluate(value=>updateProtectionStrip(value),state);
   geometry.push(await page.evaluate(()=>['protectionStrip','liveTimer','toggleTrack','protectionRelease'].map(id=>{const r=document.getElementById(id).getBoundingClientRect();return [r.top,r.height]})));
   assert(await page.evaluate(()=>{const h=document.getElementById('protectionHelper');return h.scrollHeight<=h.clientHeight}));
  }
  for(const state of geometry)assert.deepEqual(state,geometry[0]);
  // Compare all pre-existing terminal CSS rules and the log markup byte-for-byte.
  const terminalRules=s=>[...s.matchAll(/#terminalLogPane[^{}]*\{[^}]*\}/g)].map(m=>m[0].replace(/\r\n/g,'\n'));
  assert.deepEqual(terminalRules(html),terminalRules(baseline));
  await page.evaluate(()=>switchTab('connections'));await capture('connections-preserved');
  assert.deepEqual(errors,[]);
  console.log('PASS: 520x760 real production render; edit validation/storage-error/password preserve/clear; reserve reorder/exclude/empty; diagnostic mixed/progress/single-flight/close/reopen/stale/RPC-errors/timeout; XSS; map/mesh invariant. External browser requests aborted.');
 } finally {await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
