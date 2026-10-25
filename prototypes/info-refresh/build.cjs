// Read-only design exploration: production UI and backend remain unchanged.
const fs=require('fs'),path=require('path');
const root=path.resolve(__dirname,'../..');
const version=fs.readFileSync(path.join(root,'core/version.py'),'utf8').match(/APP_VERSION\s*=\s*"([^"]+)"/)[1];
let source=fs.readFileSync(path.join(root,'gui/web/index.html'),'utf8')
 .replace(/\r\n/g,'\n')
 .replaceAll("'https://flagcdn.com/w40/' + safeCode.toLowerCase() + '.png'",'demoFlag(safeCode)');
const old=fs.readFileSync(path.join(root,'prototypes/diagnostic-placement/c.html'),'utf8');
const scripts=[...old.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m=>m[1]);
const bootstrap=scripts.find(s=>s.includes('function demoFlag'));
const fixture=scripts.find(s=>s.includes('const demoNodes=')).split("document.getElementById('btnDiagnostics').remove()")[0];
const svg=(type)=>`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${({shield:'<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6Z"/><path d="m8 12 3 3 5-6"/>',box:'<rect x="4" y="4" width="16" height="16" rx="3"/><path d="M8 9h8M8 13h5M8 17h3"/>',route:'<circle cx="5" cy="6" r="2"/><circle cx="19" cy="18" r="2"/><path d="M7 6h8a4 4 0 0 1 0 8H9a4 4 0 0 0 0 8h6"/>',info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7v.1"/>',chevron:'<path d="m9 5 7 7-7 7"/>'})[type]}</svg>`;
const styles=`
#viewInfo{padding-right:2px;gap:10px;color:#e3efff;}
#viewInfo svg{width:18px;height:18px;flex-shrink:0;color:#94ccff;}
#viewInfo h2,#viewInfo h3,#viewInfo p{margin:0;}
.about-panel{padding:16px;background:rgba(7,18,46,.94);border:1px solid #25416e;border-radius:15px;flex-shrink:0;}
.about-head{display:flex;align-items:center;justify-content:space-between;gap:12px;}
.about-brand{font-size:22px;letter-spacing:-.4px;font-weight:800;}
.about-version{font:700 12px Consolas,monospace;color:#c1ddff;background:#102d5c;border:1px solid #365f96;border-radius:7px;padding:5px 8px;white-space:nowrap;}
.about-description{font-size:11px;line-height:1.6;color:#9bb9e4;margin-top:7px!important;}
.about-heading{display:flex;gap:8px;align-items:center;font-size:13px;font-weight:750;margin-bottom:10px!important;}
.about-rows{margin:0;}
.about-row{display:flex;align-items:center;justify-content:space-between;gap:15px;min-height:32px;font-size:12px;line-height:1.4;border-bottom:1px solid #1d365e;padding:6px 0;}
.about-row:last-child{border-bottom:0;}
.about-row dt{color:#a6bee3;flex-shrink:0;}
.about-row dd{margin:0;text-align:right;color:#e0edff;font-weight:650;}
.about-row small{display:block;font-size:10px;color:#a6bee3;margin-top:2px;font-weight:400;}
.about-ok{color:#76ddbc!important;}
.about-note{padding:12px 14px;background:rgba(12,31,65,.95);border:1px solid #355983;border-radius:12px;flex-shrink:0;}
.about-note strong{display:flex;align-items:center;gap:7px;font-size:11px;margin-bottom:5px;}
.about-note p{font-size:11px;line-height:1.6;color:#b0c8e9;}
.about-note svg{width:15px!important;height:15px!important;}
.about-rule-note{font-size:10px;line-height:1.5;color:#a8c3e8;margin-top:9px!important;}
.flat-title{display:flex;justify-content:space-between;align-items:center;padding:4px 2px 11px;}
.flat-title h2{font-size:20px;letter-spacing:-.3px;}
.flat-subtitle{color:#a4bfe8;font-size:11px;margin-top:4px!important;}
.flat-section{padding:0 3px 7px;flex-shrink:0;}
.flat-section h3{font-size:12px;font-weight:750;display:flex;gap:8px;align-items:center;padding:5px 0 6px;}
.flat-section .about-row{min-height:34px;}
.flat-section .about-row dd{font-weight:600;}
.about-details{border:1px solid #294974;border-radius:12px;background:rgba(7,20,48,.93);padding:0 14px;flex-shrink:0;}
.about-details summary{cursor:pointer;display:flex;align-items:center;gap:8px;list-style:none;min-height:43px;font-size:12px;font-weight:700;}
.about-details summary::-webkit-details-marker{display:none;}
.about-details summary::after{content:'+';margin-left:auto;font-size:18px;font-weight:400;color:#9cc5f6;}
.about-details[open] summary::after{content:'−';}
.about-details[open] summary{border-bottom:1px solid #24416d;margin-bottom:5px;}
.about-details p{font-size:11px;line-height:1.6;color:#abc5e8;padding-bottom:12px;}
.about-details summary:focus-visible{outline:2px solid #94caff;outline-offset:3px;border-radius:4px;}
.status-top{display:flex;align-items:center;gap:10px;}
.status-seal{width:36px;height:40px;display:grid;place-items:center;background:#102d56;border-radius:10px;}
.status-seal svg{width:24px!important;height:26px!important;}
.status-top h2{font-size:15px;}
.status-top p{font-size:11px;color:#a7c2e8;margin-top:4px!important;}
.status-bottom{display:flex;align-items:center;justify-content:space-between;border-top:1px solid #28446d;margin-top:13px;padding-top:10px;font-size:11px;}
.status-bottom span:first-child{color:#a6bee3;}
.version-compact{display:flex;align-items:baseline;gap:9px;padding:2px 2px 4px;}
.version-compact strong{font-size:17px;}.version-compact span{font:700 12px Consolas,monospace;color:#b7d8ff;}
#viewInfo.variant-b{background:rgba(5,17,45,.9);border:1px solid #29466f;border-radius:14px;padding:12px;gap:8px;}
.variant-b .about-row{min-height:30px;padding:5px 0;}
.variant-b .flat-section{padding-bottom:0;}
.variant-b .flat-section h3{padding:2px 0 5px;}
.variant-b .flat-title{padding:0 2px 8px;}
.variant-b .about-note{padding:10px 12px;}
.variant-b .about-rule-note{margin-top:6px!important;}
`;
const row=(label,value,attrs='')=>`<div class="about-row"><dt>${label}</dt><dd ${attrs}>${value}</dd></div>`;
const note=`<aside class="about-note"><strong>${svg('info')}О проверках безопасности</strong><p>Состояние защиты не является проверкой на утечки. Полная проверка IPv4, IPv6 и DNS в изолированной Windows VM ещё не завершена.</p></aside>`;
const routes=`${row('Telegram','Через TUN<small>Прямые исключения отключены</small>')}${row('DNS','Через прокси<small>DoH · резерв TCP DNS</small>')}${row('IPv6 и UDP','Отклоняются правилами')}`;
const versions=`${row('Приложение',`KROTTUN ${version}`)}${row('Сетевое ядро','sing-box')}${row('Драйвер TUN','Wintun 0.14')}`;
const variants={
a:{title:'Паспорт приложения',description:'Знакомые карточки: версия, права, правила подключения. Всё видно сразу.',content:`<section class="about-panel"><div class="about-head"><h2 class="about-brand">KROTTUN</h2><span class="about-version">v${version}</span></div><p class="about-description">Системный TUN-клиент для Windows</p><dl class="about-rows">${row('Права администратора','Есть','class="about-ok" data-demo-admin')}${row('Соединение','Туннель работает','data-demo-connection')}</dl></section><section class="about-panel"><h3 class="about-heading">${svg('route')}Правила защищённого подключения</h3><dl class="about-rows">${routes}</dl><p class="about-rule-note">Это правила режима. Текущее состояние защиты показано выше.</p></section><section class="about-panel"><h3 class="about-heading">${svg('box')}Компоненты</h3><dl class="about-rows">${row('Ядро','sing-box')}${row('Драйвер','Wintun 0.14')}</dl></section>${note}`},
b:{title:'Коротко и понятно',description:'Без лишних карточек. Основное — в строках, технические сведения раскрываются.',content:`<header class="flat-title"><div><h2>О приложении</h2><p class="flat-subtitle">KROTTUN для Windows</p></div><span class="about-version">v${version}</span></header><section class="flat-section"><h3>${svg('shield')}Состояние</h3><dl class="about-rows">${row('Соединение','Туннель работает','data-demo-connection')}${row('Администратор','Права есть','data-demo-admin class="about-ok"')}</dl></section><section class="flat-section"><h3>${svg('route')}Что идёт через туннель</h3><dl class="about-rows">${row('Telegram','Через TUN')}${row('DNS','Через прокси')}${row('Прямые исключения','Отключены')}${row('IPv6 и UDP','Отклоняются')}</dl><p class="about-rule-note">Правила применяются при защищённом подключении. Для Telegram нет отдельного переключателя.</p></section><details class="about-details"><summary>${svg('box')}Технические сведения</summary><dl class="about-rows">${versions}${row('DNS','DoH · TCP-резерв')}</dl></details>${note}`},
c:{title:'Состояние и подробности',description:'Сначала текущий статус. Правила, компоненты и ограничения — в раскрывающихся разделах.',content:`<header class="version-compact"><strong>KROTTUN</strong><span>v${version}</span></header><section class="about-panel"><div class="status-top"><span class="status-seal">${svg('shield')}</span><div><h2 data-demo-connection>Туннель работает</h2><p data-demo-explanation>Подключение через выбранный прокси</p></div></div><div class="status-bottom"><span>Права администратора</span><strong class="about-ok" data-demo-admin>Есть</strong></div></section><details class="about-details" open><summary>${svg('route')}Правила подключения</summary><dl class="about-rows">${routes}</dl><p>Правила защищённого режима. Telegram следует общему маршруту; прямого исключения нет.</p></details><details class="about-details"><summary>${svg('box')}Версия и компоненты</summary><dl class="about-rows">${versions}</dl></details><details class="about-details"><summary>${svg('info')}Что ещё требует проверки</summary><p>Статус защиты показывает состояние приложения, а не результат проверки на утечки. Полная проверка IPv4, IPv6 и DNS в изолированной Windows VM ещё не завершена.</p></details>`}
};
const stateScript=`
switchTab('info');
function setDemoState(state){
const running=state==='running',unknown=state==='unknown';
document.querySelectorAll('[data-demo-connection]').forEach(el=>el.textContent=running?'Туннель работает':unknown?'Нет данных о подключении':'Туннель не подключён');
document.querySelectorAll('[data-demo-explanation]').forEach(el=>el.textContent=running?'Подключение через выбранный прокси':unknown?'Не удалось получить состояние приложения':'Для работы через прокси включите подключение');
document.querySelectorAll('[data-demo-admin]').forEach(el=>el.textContent=unknown?'Нет данных':'Права есть');
document.querySelectorAll('[data-demo-admin]').forEach(el=>el.classList.toggle('about-ok',!unknown));
updateProtectionStrip(running?'protected':unknown?'unknown':'unarmed');
}
window.addEventListener('message',event=>{if(event.source===parent&&event.data?.type==='info-demo-state'&&['running','unarmed','unknown'].includes(event.data.state))setDemoState(event.data.state)});
setDemoState('running');
`;
const start=source.indexOf('    <div class="view-content hidden" id="viewInfo">');
const end=source.indexOf('\n  </div>\n\n  <!-- Toast Notification -->',start);
if(start<0||end<0)throw Error('Info source boundary missing');
// Keep the complete passport, including its caveat, inside the initial viewport.
variants.a.content=variants.a.content
 .replace('Системный TUN-клиент для Windows','Windows · sing-box · Wintun 0.14')
 .replace(`<section class="about-panel"><h3 class="about-heading">${svg('box')}Компоненты</h3><dl class="about-rows">${row('Ядро','sing-box')}${row('Драйвер','Wintun 0.14')}</dl></section>`,'');
for(const [key,v]of Object.entries(variants)){
const html=(source.slice(0,start)+`<div class="view-content hidden variant-${key}" id="viewInfo">${v.content}</div>\n`+source.slice(end))
 .replace('</head>',`<style>${styles}</style><script>${bootstrap}</script></head>`)
 .replace('</body>',`<script>${fixture}\n${stateScript}</script></body>`);
fs.writeFileSync(path.join(__dirname,`${key}.html`),html.replace(/[ \t]+$/gm,''));
}
const panels=Object.entries(variants).map(([key,v])=>`<article><div class="caption"><b>${key.toUpperCase()}</b><div><h2>${v.title}</h2><p>${v.description}</p></div><a href="${key}.html" target="_blank">Открыть ↗</a></div><iframe src="${key}.html" title="${v.title}" width="520" height="760"></iframe></article>`).join('');
fs.writeFileSync(path.join(__dirname,'index.html'),`<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>KROTTUN — Инфо / UAC</title><style>*{box-sizing:border-box}body{margin:0;padding:28px;background:#080f20;color:#e7efff;font-family:"Segoe UI",sans-serif}h1{font-size:23px;margin:0 0 7px}header p{font-size:12px;line-height:1.6;color:#acc2e5;margin:0}label{display:flex;gap:10px;align-items:center;margin-top:14px;font-size:12px;color:#acc2e5}select{background:#10274b;color:#def0ff;border:1px solid #3e6292;border-radius:6px;padding:7px;font:12px "Segoe UI"}main{display:flex;gap:24px;overflow-x:auto;margin-top:24px;padding-bottom:20px;align-items:start}article{flex:0 0 522px}.caption{display:flex;gap:12px;min-height:100px}.caption>b{display:grid;place-items:center;flex-shrink:0;width:29px;height:29px;border:1px solid #456b9b;border-radius:8px;color:#badaff}.caption h2{font-size:16px;margin:2px 0 7px}.caption p{font-size:12px;line-height:1.5;color:#a8bfe3;margin:0;max-width:350px}.caption a{margin-left:auto;color:#a7d2ff;font-size:11px;white-space:nowrap;margin-top:7px}iframe{display:block;width:522px;height:762px;border:1px solid #294677;border-radius:14px;background:#031c77}</style><header><h1>Обновлённый «Инфо / UAC»</h1><p>Версия из APP_VERSION · Telegram без ложного переключателя · правила отдельно от результатов проверки<br>Это прототипы с демонстрационным состоянием. Реальная сеть и настройки Windows не используются.</p><label>Состояние для сравнения <select id="scenario"><option value="running">Туннель работает</option><option value="unarmed">Не подключено, защита снята</option><option value="unknown">Нет данных</option></select></label></header><main>${panels}</main><script>document.getElementById('scenario').onchange=event=>document.querySelectorAll('iframe').forEach(frame=>frame.contentWindow.postMessage({type:'info-demo-state',state:event.target.value},'*'))</script></html>`);
console.log('Built A/B/C Info prototypes; APP_VERSION='+version);
