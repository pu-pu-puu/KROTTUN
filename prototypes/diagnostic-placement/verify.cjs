const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const {chromium}=require('C:/Users/010726Admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{const browser=await chromium.launch({headless:true,channel:'msedge'});try{
for(const scale of [1,1.25,1.5,2]){
const page=await browser.newPage({deviceScaleFactor:scale,viewport:{width:520,height:760}});
await page.route('**/*',r=>r.abort());await page.evaluate(()=>{window.setInterval=()=>0;window.pywebview={api:{}}});
await page.setContent(fs.readFileSync(path.resolve(__dirname,'../../gui/web/index.html'),'utf8'));
for(const width of [480,520])for(const active of [false,true]){
await page.setViewportSize({width,height:760});
await page.evaluate(active=>{proxyList=[{id:'a',host:'192.0.2.1',port:1080,tag:'Эстония',protocol:'socks5',country_code:'EE',latency_ms:42}];selectedProxy=proxyList[0];isConnected=active;renderServersList();switchTab('servers')},active);
const geometry=await page.locator('.radio-circle').evaluate(el=>{const r=el.getBoundingClientRect(),d=el.firstElementChild.getBoundingClientRect();return {dx:d.x+d.width/2-r.x-r.width/2,dy:d.y+d.height/2-r.y-r.height/2,x:d.x,y:d.y}});
assert(Math.abs(geometry.dx)<.01&&Math.abs(geometry.dy)<.01,JSON.stringify(geometry));
if(scale===1){assert.equal(geometry.x,Math.round(geometry.x),'dot horizontal edge must lie on pixel grid');assert.equal(geometry.y,Math.round(geometry.y),'dot vertical edge must lie on pixel grid');}
}
await page.close();
}
console.log('PASS centered selected/active dots; pixel alignment at 1x; 480/520px and 100/125/150/200% density; requests aborted');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
