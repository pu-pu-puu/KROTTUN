// Mock modal design alternatives. No production or Windows changes.
const fs=require('fs'),path=require('path');
const root=path.resolve(__dirname,'../..');
const source=fs.readFileSync(path.join(root,'gui/web/index.html'),'utf8')
 .replaceAll("'https://flagcdn.com/w40/' + safeCode.toLowerCase() + '.png'",'demoFlag(safeCode)');
const old=fs.readFileSync(path.join(root,'prototypes/info-refresh/a.html'),'utf8');
const scripts=[...old.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m=>m[1]);
const bootstrap=scripts.find(s=>s.includes('function demoFlag'));
const fixture=scripts.find(s=>s.includes('const demoNodes=')).split('switchTab(\'info\');')[0];
const shield=`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6Z"/><rect x="9" y="10" width="6" height="6" rx="1"/><path d="M10 10V8a2 2 0 0 1 4 0v2"/></svg>`;
const css=`
#modalDiagnostics .modal-card{width:420px;max-width:calc(100vw - 32px);}
.blocked-title{font-size:15px;font-weight:800;margin:0 0 16px;}
.blocked-banner{padding:13px;background:#1c2331;border:1px solid #6e5c35;border-radius:12px;margin-bottom:14px;}
.blocked-banner-head{display:flex;gap:8px;align-items:center;color:#f1d295;}
.blocked-banner-head svg{width:20px;height:22px;flex-shrink:0;}
.blocked-banner strong{font-size:12px;line-height:1.5;}
.blocked-banner p{font-size:11px;line-height:1.65;color:#c2d2e9;margin:7px 0 0;}
.blocked-rows{margin:0;}
.blocked-row{display:flex;justify-content:space-between;gap:12px;padding:10px 0;border-bottom:1px solid #233551;font-size:12px;line-height:1.45;}
.blocked-row:last-child{border-bottom:0;}
.blocked-row dt{color:#d8e5f9;}
.blocked-row dd{margin:0;text-align:right;color:#a8bedc;font-size:11px;}
.blocked-row .blocked-warm{color:#efd296;}
.blocked-row .blocked-muted{color:#b0c8e7;}
.blocked-foot{font-size:10px;line-height:1.6;color:#9bb4d9;margin:14px 0 0;padding-top:11px;border-top:1px solid #233551;}
.blocked-actions{display:flex;gap:8px;margin-top:16px;}
.blocked-actions button{font:700 12px "Segoe UI",sans-serif;padding:10px 8px;border-radius:10px;flex:1;cursor:pointer;}
.blocked-primary{background:#175ecc;border:1px solid #3784f0;color:#fff;}
.blocked-primary:hover{background:#2472e3;}
.blocked-secondary{background:#09152c;border:1px solid #2d4770;color:#a9c9f4;}
.blocked-secondary:hover{background:#10254a;color:#fff;}
.blocked-actions button:focus-visible,.blocked-details summary:focus-visible{outline:2px solid #9fd0ff;outline-offset:3px;}
.blocked-hero{text-align:center;margin:3px 0 18px;}
.blocked-hero-icon{display:grid;place-items:center;width:58px;height:62px;margin:0 auto 13px;background:#16243d;border:1px solid #42536c;border-radius:16px;color:#efd296;}
.blocked-hero-icon svg{width:34px;height:36px;}
.blocked-hero h3{font-size:21px;font-weight:800;line-height:1.25;margin:0 0 10px;letter-spacing:-.3px;}
.blocked-hero p{font-size:12px;line-height:1.65;color:#b5c9e6;margin:0;}
.blocked-summary{border-top:1px solid #263b5b;border-bottom:1px solid #263b5b;padding:13px 0;margin:0;}
.blocked-summary strong{font-size:12px;display:block;}
.blocked-summary p{font-size:11px;color:#a7c1e4;margin:6px 0 0;line-height:1.5;}
.blocked-system{font-size:11px;color:#aac2e3;margin-top:13px;display:flex;align-items:center;justify-content:space-between;gap:12px;}
.blocked-system strong{color:#d5e5ff;font-size:11px;}
.blocked-caption{font-size:11px;color:#a9c6ec;margin:-7px 0 12px;line-height:1.5;}
.blocked-ledger{margin:0;padding:0 13px;background:#09162d;border:1px solid #2a4165;border-radius:12px;}
.blocked-explain{font-size:12px;line-height:1.7;color:#bdcfe8;margin:13px 0;}
.blocked-details{border-top:1px solid #263b5b;margin-top:10px;padding-top:2px;}
.blocked-details summary{display:flex;align-items:center;gap:7px;list-style:none;cursor:pointer;font-size:11px;color:#b4d3fc;min-height:36px;}
.blocked-details summary::after{content:'+';margin-left:auto;font-size:18px;}
.blocked-details[open] summary::after{content:'−';}
.blocked-details summary::-webkit-details-marker{display:none;}
.blocked-details .blocked-row{font-size:11px;padding:7px 0;}
[data-state="unknown"] .blocked-banner{background:#0d203a;border-color:#3a5f8d;}
[data-state="unknown"] .blocked-banner-head,[data-state="unknown"] .blocked-hero-icon{color:#b7d7ff;}
`;
const rows=`<dl class="blocked-rows">${['Прокси / туннель','DNS','HTTPS','Внешний IP'].map(name=>`<div class="blocked-row"><dt>${name}</dt><dd>Не выполнялась</dd></div>`).join('')}</dl>`;
const system=`<div class="blocked-system"><span>Системный прокси Windows</span><strong>Выключен</strong></div>`;
const foot=`<p class="blocked-foot">Открытие этого окна не меняет подключение и защиту.</p>`;
const actions=`<div class="blocked-actions"><button type="button" class="blocked-secondary" onclick="closeModals()">Закрыть</button><button type="button" class="blocked-primary" onclick="demoGoHome()" data-home-action>К подключению</button></div>`;
const variants={
 a:{title:'Баннер и результаты',description:'Привычный список проверок остаётся. Причина блокировки объясняется один раз сверху.',content:`<h2 class="blocked-title">Диагностика подключения</h2><section class="blocked-banner" role="status"><div class="blocked-banner-head">${shield}<strong data-reason>Интернет заблокирован защитой</strong></div><p data-explanation></p></section>${rows}${system}${foot}${actions}`},
 b:{title:'Отдельное состояние',description:'Сразу отвечает, почему нет интернета. Вместо четырёх пропусков — одна понятная сводка.',content:`<h2 class="blocked-title">Диагностика подключения</h2><section class="blocked-hero" role="status"><div class="blocked-hero-icon">${shield}</div><h3 data-reason>Интернет заблокирован</h3><p data-explanation></p></section><section class="blocked-summary"><strong>Сетевые проверки не запускались</strong><p>Прокси / туннель · DNS · HTTPS · Внешний IP</p></section>${system}${foot}${actions}`},
 c:{title:'Сводка состояния',description:'Показывает отдельно туннель, блокировку и Windows proxy. Список проверок раскрывается.',content:`<h2 class="blocked-title">Диагностика подключения</h2><p class="blocked-caption">Сетевые проверки не запускались</p><dl class="blocked-ledger"><div class="blocked-row"><dt>Туннель</dt><dd>Отключён</dd></div><div class="blocked-row"><dt>Прямой интернет</dt><dd class="blocked-warm" data-reason>Заблокирован защитой</dd></div><div class="blocked-row"><dt>Прокси Windows</dt><dd class="blocked-muted">Выключен</dd></div></dl><p class="blocked-explain" data-explanation></p><details class="blocked-details"><summary>Какие проверки пропущены</summary>${rows}</details>${foot}${actions}`}
};
const setup=`
switchTab('home');isConnected=false;activeProxy=null;applyToggleState('inactive');updateProtectionStrip('blocked');document.getElementById('liveTimer').textContent='00:00:00';
let demoBlockedState='blocked';
function demoGoHome(){closeModals();switchTab('home');}
function showBlockedDemo(state='blocked'){
demoBlockedState=state;
const modal=document.getElementById('modalDiagnostics');modal.querySelector('.modal-card').innerHTML=DEMO_CONTENT;modal.classList.add('open');modal.dataset.state=state;
const unknown=state==='unknown';
const labels=DEMO_KEY==='a'?(unknown?'Состояние защиты неизвестно':'Интернет заблокирован защитой'):DEMO_KEY==='b'?(unknown?'Нет данных о защите':'Интернет заблокирован'):(unknown?'Нет данных':'Заблокирован защитой');
modal.querySelector('[data-reason]').textContent=labels;
modal.querySelector('[data-explanation]').textContent=unknown?'Не удалось определить состояние защиты. Сетевые проверки не запускались. Вернитесь на главную и дождитесь обновления статуса.':DEMO_KEY==='c'?'Прокси отключён, но защита Windows остаётся включённой и блокирует прямой доступ. Подключите прокси, чтобы выполнить диагностику.':'Прокси отключён. Защита Windows блокирует прямой доступ в интернет. Подключите прокси, чтобы выполнить диагностику.';
modal.querySelector('[data-home-action]').textContent=unknown?'На главную':'К подключению';
updateProtectionStrip(unknown?'unknown':'blocked');
}
openDiagnostics=async()=>showBlockedDemo(demoBlockedState);
window.addEventListener('message',event=>{if(event.source===parent&&event.data?.type==='blocked-demo-state'&&['blocked','unknown'].includes(event.data.state))showBlockedDemo(event.data.state)});
showBlockedDemo();
`;
for(const [key,v] of Object.entries(variants)){
const html=source.replace('</head>',`<style>${css}</style><script>${bootstrap}</script></head>`).replace('</body>',`<script>${fixture}\nconst DEMO_CONTENT=${JSON.stringify(v.content)},DEMO_KEY=${JSON.stringify(key)};${setup}</script></body>`);
fs.writeFileSync(path.join(__dirname,`${key}.html`),html.replace(/[ \t]+$/gm,''));
}
const panels=Object.entries(variants).map(([key,v])=>`<article><div class="caption"><b>${key.toUpperCase()}</b><div><h2>${v.title}</h2><p>${v.description}</p></div><a href="${key}.html" target="_blank">Открыть ↗</a></div><iframe src="${key}.html" title="${v.title}"></iframe></article>`).join('');
fs.writeFileSync(path.join(__dirname,'index.html'),`<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>KROTTUN — диагностика при блокировке</title><style>*{box-sizing:border-box}body{margin:0;padding:28px;background:#080f20;color:#e7efff;font-family:"Segoe UI",sans-serif}h1{font-size:23px;margin:0 0 7px}header p{font-size:12px;line-height:1.6;color:#acc2e5;margin:0}label{display:flex;gap:10px;align-items:center;margin-top:14px;font-size:12px;color:#acc2e5}select{background:#10274b;color:#def0ff;border:1px solid #3e6292;border-radius:6px;padding:7px;font:12px "Segoe UI"}main{display:flex;gap:24px;overflow-x:auto;margin-top:24px;padding-bottom:20px;align-items:start}article{flex:0 0 522px}.caption{display:flex;gap:12px;min-height:100px}.caption>b{display:grid;place-items:center;flex-shrink:0;width:29px;height:29px;border:1px solid #456b9b;border-radius:8px;color:#badaff}.caption h2{font-size:16px;margin:2px 0 7px}.caption p{font-size:12px;line-height:1.5;color:#a8bfe3;margin:0;max-width:350px}.caption a{margin-left:auto;color:#a7d2ff;font-size:11px;white-space:nowrap;margin-top:7px}iframe{display:block;width:522px;height:762px;border:1px solid #294677;border-radius:14px;background:#031c77}</style><header><h1>Диагностика, когда прокси отключён</h1><p>Блокировка защиты — отдельное состояние, а не успешная диагностика.<br>Все значения демонстрационные. Кнопка «К подключению» только возвращает на главную.</p><label>Сценарий <select id="scenario"><option value="blocked">Блокировка подтверждена</option><option value="unknown">Состояние защиты неизвестно</option></select></label></header><main>${panels}</main><script>document.getElementById('scenario').onchange=event=>document.querySelectorAll('iframe').forEach(frame=>frame.contentWindow.postMessage({type:'blocked-demo-state',state:event.target.value},'*'))</script></html>`);
console.log('Built diagnostic blocked prototypes A/B/C');
