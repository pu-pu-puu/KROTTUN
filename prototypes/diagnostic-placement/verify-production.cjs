const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const {chromium}=require('C:/Users/010726Admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{const browser=await chromium.launch({headless:true,channel:'msedge'});try{
const page=await browser.newPage({viewport:{width:520,height:760}}),errors=[];
page.on('pageerror',e=>errors.push(e.message));await page.route('**/*',r=>r.abort());
// Reuse only demo state/bridge from the approved prototype; CSS/DOM are production.
const prototype=fs.readFileSync(path.join(__dirname,'c.html'),'utf8');
const scripts=[...prototype.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m=>m[1]);
const bootstrap=scripts.find(s=>s.includes('function demoFlag'));
const fixture=scripts.find(s=>s.includes('const demoNodes=')).split("document.getElementById('btnDiagnostics').remove()")[0];
let html=fs.readFileSync(path.resolve(__dirname,'../../gui/web/index.html'),'utf8')
 .replaceAll("'https://flagcdn.com/w40/' + safeCode.toLowerCase() + '.png'",'demoFlag(safeCode)')
 .replace('</head>',`<script>${bootstrap}</script></head>`).replace('</body>',`<script>${fixture}</script></body>`);
await page.setContent(html);
for(const width of [480,520]){
await page.setViewportSize({width,height:760});
for(const connected of [true,false]){
await page.evaluate(connected=>{isConnected=connected;applyToggleState(connected?'active':'inactive',connected);updateProtectionStrip(connected?'protected':'unarmed')},connected);
const geometry=await page.locator('#btnDiagnostics').evaluate(el=>{const r=el.getBoundingClientRect(),card=el.previousElementSibling.getBoundingClientRect();return {parent:el.parentElement.id,card:el.previousElementSibling.className,x:r.x,y:r.y,width:r.width,bottom:r.bottom,gap:r.y-card.bottom}});
assert.equal(geometry.parent,'viewHome');assert.match(geometry.card,/server-card/);
// Approved C retains the card's 8px bottom margin plus the utility's 12px top margin.
assert.equal(geometry.gap,20);assert(geometry.x>=0&&geometry.x+geometry.width<=width&&geometry.bottom<744,JSON.stringify(geometry));
assert.equal(await page.locator('#btnDiagnostics').count(),1);
await page.locator('#btnDiagnostics').focus();assert(await page.locator('#btnDiagnostics').evaluate(el=>el.matches(':focus-visible')));
await page.keyboard.press('Enter');await page.locator('#diagnosticStatus').filter({hasText:'Проверка завершена'}).waitFor();
await page.evaluate(()=>closeModals());
if(connected)await page.screenshot({path:path.join(__dirname,`production-c-${width}.png`)});
}
}
assert.deepEqual(errors,[]);console.log('PASS production C: placement/gap/viewport 480+520; protected/unarmed; keyboard opens existing diagnostic modal; no console errors; all external requests aborted');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
