// Exercise the real UI script against an isolated fake bridge; never launch the app.
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const {chromium}=require('C:/Users/010726Admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 try{
  const page=await browser.newPage({viewport:{width:520,height:760}});const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.evaluate(()=>{window.setInterval=()=>0});
  let html=fs.readFileSync(path.resolve(__dirname,'../../gui/web/index.html'),'utf8');
  const banner=fs.readFileSync(path.resolve(__dirname,'../../gui/web/krottun_banner.png')).toString('base64');
  html=html.replace(/src="krottun_banner[^"\s]*\.png"/g,`src="data:image/png;base64,${banner}"`);
  await page.setContent(html);
  const result=await page.evaluate(async()=>{
   const icon=id=>document.getElementById(id).querySelector('.ui-icon')?.getAttribute('data-icon');
   const states=[];
   for(const [state,reachable]of [['active',true],['active',false],['connecting'],['disconnecting'],['inactive']]){applyToggleState(state,reachable);states.push(icon('statusIcon'))}
   window.pywebview={api:{ping_proxy:async()=>({latency:42}),ping_all:async()=>({})}};
   refreshState=async()=>{};
   selectedProxy={id:'sample'};
   await testSelectedPing();await testAllPings();
   proxyList=[{id:'sample',host:'example.test',port:1080,protocol:'socks5',location_name:'<img src=x onerror=evil()>',latency_ms:42}];
   renderServersList();
   const remove=document.querySelector('#serversListContainer [data-icon="close"]');
   return {states,ping:icon('btnTestPing'),all:icon('btnPingAll'),remove:!!remove,unsafe:!!document.querySelector('#serversListContainer img[src=x]')};
  });
  assert.deepEqual(result,{states:['check','warning','more','more','close'],ping:'pulse',all:'pulse',remove:true,unsafe:false});
  await page.evaluate(()=>switchTab('info'));await page.screenshot({path:path.join(__dirname,'production-info.png')});
  await page.evaluate(()=>switchTab('home'));await page.screenshot({path:path.join(__dirname,'production-home.png')});
  assert.deepEqual(errors,[]);console.log('PASS: live status changes, ping resets, server delete icon and safe server names.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
