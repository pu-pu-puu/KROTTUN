"""One-time migration of approved vector icons into the single-file UI."""
from pathlib import Path
import ast
import json

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
tree = ast.parse((OUT / 'build.py').read_text(encoding='utf-8'))
shapes = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'shapes' for t in n.targets))
shapes['warning'] = '<path d="m12 3 10 18H2L12 3Z"/><path d="M12 9v5m0 3v.1"/>'
shapes['more'] = '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>'
def icon(name):
    return f'<svg class="ui-icon" data-icon="{name}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{shapes[name]}</svg>'

target = ROOT / 'gui/web/index.html'
source = target.read_text(encoding='utf-8')
if 'function uiIcon(' in source:
    raise SystemExit('Icons are already installed')
markup, scripts = source.split('  <script data-world-map>', 1)
for text, name in [('🛡️','shield'),('⚙️','gear'),('🚀','network'),('⚡','pulse'),('📥','download'),('⇄','swap'),('↑','up'),('↓','down'),('✓','check'),('✕','close')]:
    markup = markup.replace(text, icon(name))
markup = markup.replace('>+ Добавить', '>'+icon('plus')+' Добавить')
css = '''
    /* Approved outline icon family; icons inherit semantic button/status colors. */
    .ui-icon { width:16px; height:16px; flex-shrink:0; vertical-align:-3px; color:#91d0ff; display:inline-block; }
    .info-title > span { display:inline-flex; align-items:center; gap:8px; }
    .info-title .ui-icon { width:18px; height:18px; }
    .header-action-btn, .action-btn { display:inline-flex; align-items:center; justify-content:center; gap:6px; }
    .action-btn > span:has(.ui-icon) { display:inline-flex; }
    .btn-primary .ui-icon, .btn-danger .ui-icon { color:currentColor; }
    .arrow-badge .ui-icon, #statusIcon .ui-icon { color:currentColor; width:13px; height:13px; }
'''
markup = markup.replace('  </style>', css+'  </style>')
helper = '    const UI_ICON_SHAPES = Object.freeze('+json.dumps(shapes)+');\n'+'''    function uiIcon(name) {
      if (!Object.prototype.hasOwnProperty.call(UI_ICON_SHAPES, name)) return '';
      return `<svg class="ui-icon" data-icon="${name}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${UI_ICON_SHAPES[name]}</svg>`;
    }
'''
scripts = scripts.replace('  <script>\n', '  <script>\n'+helper, 1)
for text, name in [('⚠','warning'),('✓','check'),('⋯','more'),('✕','close')]:
    scripts = scripts.replace(f"sIcon.innerText = '{text}';", f"sIcon.innerHTML = uiIcon('{name}');")
scripts = scripts.replace("btnDel.innerText = '✕';", "btnDel.innerHTML = uiIcon('close');\n        btnDel.setAttribute('aria-label', 'Удалить сервер');\n        btnDel.title = 'Удалить сервер';")
scripts = scripts.replace("btn.innerHTML = '<span>⚡</span> Проверить пинг';", "btn.innerHTML = uiIcon('pulse') + ' Проверить пинг';")
scripts = scripts.replace("btn.innerText = '⚡ Замерить все';", "btn.innerHTML = uiIcon('pulse') + ' Замерить все';")
scripts = scripts.replace("btn.innerText = 'Замер...';", "btn.innerHTML = uiIcon('more') + ' Замер...';")
scripts = scripts.replace("badge.innerText = '⏳ ...';", "badge.innerHTML = uiIcon('more') + ' ...';")
target.write_text(markup+'  <script data-world-map>'+scripts, encoding='utf-8')
print('Applied approved icons to static markup and dynamic status/ping/server controls.')
