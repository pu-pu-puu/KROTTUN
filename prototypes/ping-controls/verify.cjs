const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const {chromium}=require('C:/Users/010726Admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{const browser=await chromium.launch({headless:true,channel:'msedge'});try{
const page=await browser.newPage();await page.route('**/*',r=>r.abort());
await page.evaluate(()=>{window.setInterval=()=>0;window.pywebview={api:{}}});
await page.setContent(fs.readFileSync(path.resolve(__dirname,'../../gui/web/index.html'),'utf8'));
for(const width of [480,520]){await page.setViewportSize({width,height:760});for(const active of [false,true]){
await page.evaluate(active=>{proxyList=[{id:'a',host:'extremely-long-hostname-for-a-proxy.example.invalid',tag:'extremely-long-hostname-for-a-proxy.example.invalid:65535',port:65535,protocol:'socks5',latency_ms:9999},{id:'b',host:'198.51.100.100',port:1080,protocol:'http',tag:'198.51.100.100:1080',latency_ms:null}];selectedProxy=proxyList[0];isConnected=active;renderServersList();switchTab('servers')},active);
await page.screenshot({path:path.join(__dirname,`rows-${width}-${active}.png`)});
const rows=await page.locator('.server-item').evaluateAll(rows=>rows.map(row=>{const rect=s=>{const r=row.querySelector(s).getBoundingClientRect();return {left:r.left,right:r.right,width:r.width}};return {proto:rect('.proto-badge'),right:rect('.item-right'),name:rect('.item-name'),left:rect('.item-left')}}));
for(const r of rows){assert(r.proto.right<=r.right.left-4,JSON.stringify(r));assert(r.name.right<=r.proto.left,JSON.stringify(r));}
}}
await page.evaluate(()=>{
 window.pingCalls=0;window.pingScenario='ok';window.pendingPing=null;
 const invoke=async()=>{window.pingCalls++;if(window.pingScenario==='error')throw Error('Bridge unavailable');
 if(window.pingScenario==='reject')return {success:false,error:'Состояние подключения изменилось'};
 if(window.pingScenario==='hang')return new Promise(resolve=>window.pendingPing=resolve);
 if(window.pingScenario==='undefined')return {success:true,mode:'tun',results:[],status:'notchecked'};
 return {success:true,mode:'tun',latency:null,status:'timeout',results:proxyList.map(p=>({id:p.id,latency:null,status:'timeout'})),proxies:proxyList.map(p=>({...p,latency_ms:null,latency_mode:'tun'}))};};
 window.pywebview.api.ping_proxy=invoke;window.pywebview.api.ping_all=invoke;
 const original=window.setTimeout.bind(window);window.setTimeout=(fn,ms,...args)=>original(fn,ms===10000?50:ms,...args);
});
for(const scenario of ['error','reject','undefined','ok','hang']){
 await page.evaluate(async scenario=>{pingScenario=scenario;await testSelectedPing()},scenario);
 assert.equal(await page.locator('#btnTestPing').isDisabled(),false);assert.equal(await page.locator('#btnPingAll').isDisabled(),false);
 assert(!/undefined|NaN/.test(await page.locator('#cardPingBadge').innerText()));
 if(scenario==='undefined')assert.equal(await page.locator('#cardPingBadge').innerText(),'\u041d\u0435 \u043f\u0440\u043e\u0432\u0435\u0440\u0435\u043d');
}
await page.evaluate(()=>{pendingPing({success:false});});await page.waitForTimeout(0);
await page.evaluate(()=>{pingScenario='hang';testAllPings();testAllPings()});
const calls=await page.evaluate(()=>pingCalls);await page.waitForTimeout(70);
assert.equal(await page.evaluate(()=>pingCalls),calls);assert.equal(await page.locator('#btnPingAll').isDisabled(),false);
await page.evaluate(()=>testAllPings());assert.equal(await page.evaluate(()=>pingCalls),calls);
await page.evaluate(()=>pendingPing({success:false}));await page.waitForTimeout(0);
await page.evaluate(async()=>{pingScenario='ok';await testAllPings();renderServersList()});
assert.match(await page.locator('.item-right .ping-badge').first().getAttribute('title'),/TUN/);
await page.evaluate(()=>{proxyList[0].latency_mode='tcp';proxyList[1].latency_mode='tun';renderServersList()});
assert.match(await page.locator('.item-right .ping-badge').nth(0).getAttribute('title'),/TCP/);
assert.match(await page.locator('.item-right .ping-badge').nth(1).getAttribute('title'),/TUN/);
await page.evaluate(()=>{selectedProxy={...proxyList[0],latency_ms:null,latency_mode:'tun',last_status:'dead'};updateSelectedServerCard()});
assert.equal(await page.locator('#cardPingBadge').innerText(),'\u0422\u0430\u0439\u043c\u0430\u0443\u0442');
assert.match(await page.locator('#cardPingBadge').getAttribute('title'),/TUN/);
for(const status of ['unknown','notchecked']){
 await page.evaluate(status=>{selectedProxy.last_status=status;updateSelectedServerCard()},status);
 assert.equal(await page.locator('#cardPingBadge').innerText(),'\u2014 ms');
 assert.match(await page.locator('#cardPingBadge').getAttribute('title'),/TUN/);
}
console.log('PASS selected card refresh preserves timeout/unknown and measurement mode; geometry 480/520 selected/active SOCKS5/HTTP 9999ms/unknown; bridge exceptions/rejection/undefined/all-timeout/hang/singleflight/finally; mixed stored modes; external requests aborted');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
