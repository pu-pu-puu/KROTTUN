// All rows below are illustrative. No bridge, polling or network calls.
const sample=[
 ['19:12:29','cmp2-fra1.steamserver.net','155.133.250.20:27022','steam.exe','UDP','Прокси'],
 ['19:12:29','api.knock.app','18.216.121.136:443','chrome.exe','TCP','Прокси'],
 ['19:12:29','codex-cloud-backend.chatgpt.com','162.125.40.209:443','ChatGPT.exe','TCP','Прокси'],
 ['19:12:28','cmp1-sto1.steamserver.net','162.254.198.68:27029','steam.exe','UDP','Прокси'],
 ['19:12:27','example.com','93.184.215.14:443','chrome.exe','TCP','Прокси'],
 ['19:12:26','api.telegram.org','149.154.167.220:443','Telegram.exe','TCP','Прокси'],
 ['19:12:25','1.1.1.1','1.1.1.1:53','sing-box.exe','DNS','Прокси'],
 ['19:12:24','cdn.example.net','192.0.2.5:443','chrome.exe','TCP','Прокси'],
 ['19:12:23','updates.example.org','198.51.100.7:443','updater.exe','TCP','Прокси']
];
let rows=sample.slice(),selected=-1;
const get=id=>document.getElementById(id);
const table=document.querySelector('.terminal-table');
table.insertAdjacentHTML('afterbegin','<colgroup><col style="width:18px"><col style="width:64px"><col style="width:216px"><col style="width:112px"><col style="width:74px"><col style="width:100px"><col style="width:166px"></colgroup>');
function select(index){selected=index;render();const r=rows[index];get('connectionInspectorHost').textContent=r[1];get('connectionInspectorDetails').textContent=`${r[3]} · ${r[4]} · ${r[5]} · ${r[2]}`}
function render(){
 const filter=get('connectionFilter').value.trim().toLowerCase();get('connectionRows').replaceChildren();let count=0;
 rows.forEach((r,i)=>{if(!r.join(' ').toLowerCase().includes(filter))return;count++;
  const tr=document.createElement('tr');tr.tabIndex=0;tr.classList.toggle('selected',i===selected);
  tr.onclick=()=>select(i);tr.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();select(i)}};
  ['›',r[0],r[1],r[3],r[4],r[5],'Зафиксировано'].forEach((text,n)=>{
   const td=document.createElement('td');td.textContent=text;td.title=text;
   if(n===0)td.className='connection-marker';
   if(n===2){td.className='connection-domain';const small=document.createElement('small');small.textContent=r[2];td.append(small)}
   if(n===4)td.className='connection-protocol';if(n===6)td.className='connection-status';tr.append(td);
  });get('connectionRows').append(tr);
 });get('connectionCount').textContent=`${count} / ${rows.length}`;get('connectionEmpty').hidden=count>0;
}
get('connectionFilter').oninput=render;
get('connectionPause').onclick=()=>{const pause=get('connectionPause').getAttribute('aria-pressed')!=='true';get('connectionPause').setAttribute('aria-pressed',pause);get('connectionPause').textContent=pause?'Продолжить':'Пауза';get('connectionPollStatus').textContent=pause?'Опрос на паузе':'Опрос включён'};
document.querySelector('.terminal-toolbar button:last-child').onclick=()=>{rows=[];selected=-1;render();get('connectionInspectorHost').textContent='Выберите строку';get('connectionInspectorDetails').textContent='Адрес, программа и маршрут выбранной строки.'};
addEventListener('message',e=>{if(e.source===parent&&e.data?.type==='reset'){rows=sample.slice();selected=-1;get('connectionFilter').value='';render()}});
render();select(2);
