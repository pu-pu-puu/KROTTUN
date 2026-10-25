// Standalone mock prototypes. No Python bridge, network, or app launch.
const fs=require('fs'),path=require('path');
const root=path.resolve(__dirname,'../..');
const source=fs.readFileSync(path.join(root,'gui/web/index.html'),'utf8')
 .replaceAll("'https://flagcdn.com/w40/' + safeCode.toLowerCase() + '.png'",'demoFlag(safeCode)')
 .replaceAll("'https://flagcdn.com/w40/' + rawCode.toLowerCase() + '.png'",'demoFlag(rawCode)');
const bootstrap=`window.setInterval=()=>0;function demoFlag(code){const colors=code==='EE'?['#4891d9','#101820','#ffffff']:['#ae1c28','#ffffff','#21468b'];return 'data:image/svg+xml,'+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="30" height="20" viewBox="0 0 30 20">'+colors.map((fill,i)=>'<rect width="30" height="7" y="'+(i*20/3)+'" fill="'+fill+'"/>').join('')+'</svg>')}`;
const icon=`<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 12h4l3-7 4 14 3-7h4"/><path d="M3 4v3m0 10v3M21 4v3m0 10v3"/></svg>`;
const arrow=`<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m9 5 7 7-7 7"/></svg>`;
const styles=`
.diag-trigger{display:inline-flex;align-items:center;justify-content:center;gap:7px;flex-shrink:0;min-height:32px;padding:6px 10px;border:1px solid #345d9c;border-radius:9px;color:#c4e0ff;background:#0b2552;font:700 11px "Segoe UI",sans-serif;cursor:pointer;transition:background .15s,border-color .15s;}
.diag-trigger:hover{background:#12376d;border-color:#73b5ff;color:white;}
.diag-trigger:focus-visible{outline:2px solid #a4d4ff;outline-offset:3px;}
.diag-trigger svg{flex-shrink:0;}
.diag-head-actions{display:flex;align-items:center;gap:8px;min-width:0;}
.diag-head-actions .ip-pill{padding:7px 10px;font-size:11px;gap:4px;}
.diag-status-row{display:flex;align-items:center;justify-content:center;gap:10px;}
.diag-status-row .diag-trigger{background:rgba(7,25,58,.9);color:#b2d5ff;}
.diag-utility{display:flex;width:100%;flex:0 0 auto;align-items:center;text-align:left;gap:12px;margin-top:12px;padding:13px 15px;background:rgba(7,21,51,.92);border:1px solid #254c85;border-radius:12px;color:#cde5ff;cursor:pointer;font-family:"Segoe UI",sans-serif;}
.diag-utility:hover{border-color:#69a9ef;background:#0c2a5b;}
.diag-utility:focus-visible{outline:2px solid #a4d4ff;outline-offset:3px;}
.diag-utility-icon{display:grid;place-items:center;color:#8bc9ff;width:32px;height:32px;background:#113263;border-radius:8px;flex-shrink:0;}
.diag-utility-copy{display:flex;flex:1;flex-direction:column;gap:3px;}
.diag-utility strong{font-size:12px;font-weight:700;}
.diag-utility small{font-size:10px;color:#99bae6;}
@media(max-width:490px){.diag-head-actions{gap:6px}.diag-head-actions .ip-pill{font-size:10px;padding:7px 8px}.diag-head-actions .diag-trigger{padding:6px 8px;font-size:10px}}
`;
const setup=`
const demoNodes=[{id:'ee',host:'192.0.2.10',port:1080,tag:'Эстония · Основной',protocol:'socks5',country_code:'EE',latency_ms:42,latency_mode:'tun_https',last_status:'alive'},{id:'nl',host:'192.0.2.20',port:8080,tag:'Нидерланды · Резерв',protocol:'http',country_code:'NL',latency_ms:64,latency_mode:'tun',last_status:'alive'}];
proxyList=demoNodes;selectedProxy=demoNodes[0];activeProxy=demoNodes[0];isConnected=true;
updateSelectedServerCard();renderServersList();applyToggleState('active',true);updateProtectionStrip('protected');
document.getElementById('liveTimer').textContent='00:18:42';document.getElementById('valUpload').textContent='0.4 Mb/s';document.getElementById('valDownload').textContent='3.8 Mb/s';
document.getElementById('ipValue').textContent='203.0.113.42';
window.pywebview={api:{
start_diagnostics:async()=>({success:true,run_id:'demo'}),
get_diagnostics:async()=>({run_id:'demo',status:'done',checks:['proxy','dns','https','ip','system_proxy'].map(id=>({id,status:'pass',detail:'Демонстрационный результат прототипа. Реальная сеть не проверяется.'}))}),
cancel_diagnostics:async()=>({success:true}),
get_state:async()=>({state:'running',is_running:true,proxy_reachable:true,proxies:demoNodes,selected_proxy:demoNodes[0],active_proxy:demoNodes[0],protection:{state:'protected'},is_admin:true,settings:{}}),
select_proxy:async()=>({success:true}),refresh_ip:async()=>({success:true}),
get_telemetry:async()=>({state:'running',proxy_reachable:true,system_ip:{ip:'203.0.113.42',status:'ready'}})
}};
document.getElementById('btnDiagnostics').remove();
const diagButton=document.createElement('button');diagButton.type='button';diagButton.id='btnDiagnostics';diagButton.onclick=()=>openDiagnostics();
`;
const variants={
 a:{title:'В шапке',description:'Постоянное место рядом с внешним IP. Доступна на любой вкладке.',code:`const group=document.createElement('div');group.className='diag-head-actions';const ip=document.getElementById('ipPill');ip.before(group);group.append(ip);diagButton.className='diag-trigger';diagButton.innerHTML=${JSON.stringify(icon+'<span>Диагностика</span>')};group.append(diagButton);`},
 b:{title:'Рядом со статусом',description:'Проверка рядом с Connected / Disconnected. Связь с подключением сразу понятна.',code:`const row=document.querySelector('.status-pill-box');row.classList.add('diag-status-row');diagButton.className='diag-trigger';diagButton.innerHTML=${JSON.stringify(icon+'<span>Диагностика</span>')};row.append(diagButton);`},
 c:{title:'Под карточкой сервера',description:'Отдельная заметная строка с составом проверки: DNS, HTTPS и внешний IP.',code:`diagButton.className='diag-utility';diagButton.innerHTML=${JSON.stringify('<span class="diag-utility-icon">'+icon+'</span><span class="diag-utility-copy"><strong>Диагностика подключения</strong><small>DNS · HTTPS · Внешний IP</small></span>'+arrow)};document.querySelector('#viewHome .server-card').after(diagButton);`}
};
for(const [key,v]of Object.entries(variants)){
const html=source.replace('</head>',`<style>${styles}</style><script>${bootstrap}</script></head>`).replace('</body>',`<script>${setup}\n${v.code}</script></body>`);
fs.writeFileSync(path.join(__dirname,`${key}.html`),html.replace(/[ \t]+$/gm,''));
}
const panels=Object.entries(variants).map(([key,v])=>`<article><div class="caption"><span class="letter">${key.toUpperCase()}</span><div><h2>${v.title}</h2><p>${v.description}</p></div><a href="${key}.html" target="_blank">Открыть ↗</a></div><iframe src="${key}.html" title="${v.title}" width="520" height="760"></iframe></article>`).join('');
fs.writeFileSync(path.join(__dirname,'index.html'),`<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>KROTTUN — размещение диагностики</title><style>*{box-sizing:border-box}body{margin:0;padding:28px;background:#080f20;color:#e7efff;font-family:"Segoe UI",sans-serif}h1{font-size:23px;margin:0 0 8px}header p{color:#a6bade;font-size:13px;line-height:1.6;margin:0}main{display:flex;gap:24px;align-items:start;margin-top:24px;overflow-x:auto;padding-bottom:20px}article{flex:0 0 522px}.caption{min-height:104px;display:flex;gap:12px;align-items:flex-start;padding:0 0 16px}.letter{display:grid;place-items:center;flex-shrink:0;width:29px;height:29px;border:1px solid #3e669f;border-radius:8px;color:#badaff;font-weight:700}.caption h2{margin:2px 0 8px;font-size:16px}.caption p{margin:0;color:#a6bade;font-size:12px;line-height:1.5;max-width:350px}.caption a{font-size:11px;color:#a7d2ff;margin-left:auto;white-space:nowrap;margin-top:6px}iframe{display:block;border:1px solid #294677;border-radius:14px;width:522px;height:762px;background:#031c77}</style><header><h1>Куда перенести диагностику</h1><p>Три варианта в существующем интерфейсе KROTTUN · окно 520 × 760<br>Демонстрационные данные. Кнопки открывают макет диагностики без обращения к сети.</p></header><main>${panels}</main></html>`);
console.log('Built a.html, b.html, c.html and index.html');
