"""Create isolated, offline icon comparison from the current interface."""
from pathlib import Path
import re
import base64

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
source = (ROOT / 'gui/web/index.html').read_text(encoding='utf-8-sig')
source = re.sub(r'<script\b([^>]*)>.*?</script>', lambda m: m[0] if 'data-world-map' in m[1] else '', source, flags=re.S)
source = re.sub(r'\s+on\w+="[^"]*"', '', source)
for name in ['krottun_banner.png', 'krottun_banner_dark.png', 'krottun_banner_light.png']:
    data = base64.b64encode((ROOT / 'gui/web' / name).read_bytes()).decode()
    source = source.replace(f'src="{name}"', f'src="data:image/png;base64,{data}"')
source = source.replace('data-state="unknown"', 'data-state="protected"').replace('Статус неизвестен', 'Включена').replace('Проверьте подключение', '')
source = source.replace('Загрузка...', '203.0.113.24').replace('00:00:00', '00:08:19')
source = source.replace('toggle-track inactive', 'toggle-track active').replace('toggle-knob inactive', 'toggle-knob active').replace('power-icon inactive', 'power-icon active')
source = source.replace('status-pill disconnected', 'status-pill connected').replace('Disconnected', 'Connected').replace('id="statusIcon">✕', 'id="statusIcon">✓')
shapes = {
    'shield': '<path d="M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6l-8-3Z"/><path d="m8 12 3 3 5-6"/>',
    'gear': '<path d="m9 3-.7 3-2 .9-2.7-.8-2 3.5L4 11.7v2.6l-2.4 2.1 2 3.5 2.7-.8 2 .9.7 3h4l.7-3 2-.9 2.7.8 2-3.5-2.4-2.1v-2.6l2.4-2.1-2-3.5-2.7.8-2-.9L13 3Z" transform="translate(1 -1) scale(.94)"/><circle cx="12" cy="12" r="3"/>',
    'network': '<rect x="9" y="3" width="6" height="5" rx="1"/><rect x="2" y="16" width="6" height="5" rx="1"/><rect x="16" y="16" width="6" height="5" rx="1"/><path d="M12 8v4M5 16v-4h14v4"/>',
    'pulse': '<path d="M2 12h5l3-8 4 16 3-8h5"/>',
    'swap': '<path d="M3 7h17m-4-4 4 4-4 4M21 17H4m4-4-4 4 4 4"/>',
    'download': '<path d="M12 3v12m-5-5 5 5 5-5M4 15v5h16v-5"/>',
    'plus': '<path d="M12 5v14M5 12h14"/>',
    'up': '<path d="M12 20V4m-6 6 6-6 6 6"/>',
    'down': '<path d="M12 4v16m-6-6 6 6 6-6"/>',
    'check': '<path d="m5 12 4 4L19 6"/>',
    'close': '<path d="m6 6 12 12M6 18 18 6"/>',
}
def icon(name):
    return f'<svg class="ui-icon" data-icon="{name}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{shapes[name]}</svg>'

extra = '''<style>
.ui-icon{width:16px;height:16px;flex-shrink:0;vertical-align:-3px;color:#91d0ff;display:inline-block}
.info-title>span{display:inline-flex;align-items:center;gap:8px}
.info-title .ui-icon{width:18px;height:18px}
.header-action-btn,.action-btn{display:inline-flex;align-items:center;justify-content:center;gap:6px}
.action-btn>span:has(.ui-icon){display:inline-flex}
.btn-primary .ui-icon{color:currentColor}
.arrow-badge .ui-icon{color:currentColor;width:13px;height:13px}
#statusIcon .ui-icon{color:currentColor;width:13px;height:13px}
.prototype-empty{margin:24px 0;color:#a8c7ed;font-size:12px;text-align:center}
</style>'''
control = '''<script>
function showView(view){
 for(const name of ['Home','Servers','Info','Connections']){
  document.getElementById('view'+name).classList.toggle('hidden',name.toLowerCase()!==view);
  document.getElementById('tab'+name).classList.toggle('active',name.toLowerCase()===view);
 }
}
showView('info');
document.getElementById('serversListContainer').innerHTML='<p class="prototype-empty">Здесь показаны только кнопки списка серверов.</p>';
for(const name of ['Home','Servers','Info']) document.getElementById('tab'+name).onclick=()=>showView(name.toLowerCase());
addEventListener('message',e=>{if(e.source===parent && e.data?.view)showView(e.data.view)});
</script>'''
for variant in ['before', 'after']:
    doc = source
    if variant == 'after':
        for text, name in [('🛡️','shield'),('⚙️','gear'),('🚀','network'),('⚡','pulse'),('📥','download'),('⇄','swap'),('↑','up'),('↓','down'),('✓','check'),('✕','close')]:
            doc = doc.replace(text, icon(name))
        doc = doc.replace('>+ Добавить', '>'+icon('plus')+' Добавить')
    doc = doc.replace('</head>', extra+'</head>').replace('</body>', control+'</body>')
    (OUT/f'{variant}.html').write_text(doc,encoding='utf-8')
print('Built offline before/after icon prototypes; application code unchanged.')
