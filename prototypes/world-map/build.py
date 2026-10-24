"""Build offline visual alternatives; never import the application or its bridge."""
from pathlib import Path
import base64
import re

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
source = (ROOT / 'gui/web/index.html').read_text(encoding='utf-8-sig')
source = re.sub(r'<script\b[^>]*>.*?</script>', '', source, flags=re.S | re.I)
source = re.sub(r'\s+on\w+="[^"]*"', '', source)
for name in ('krottun_banner.png', 'krottun_banner_dark.png', 'krottun_banner_light.png'):
    data = base64.b64encode((ROOT / 'gui/web' / name).read_bytes()).decode()
    source = source.replace(f'src="{name}"', f'src="data:image/png;base64,{data}"')
source = source.replace('Статус неизвестен', 'Включена').replace('Проверьте подключение', '')
source = source.replace('data-state="unknown"', 'data-state="protected"')
source = source.replace('00:00:00', '00:08:19').replace('Загрузка...', '203.0.113.24')
source = source.replace('toggle-track inactive', 'toggle-track active').replace('toggle-knob inactive', 'toggle-knob active').replace('power-icon inactive', 'power-icon active')
source = source.replace('status-pill disconnected', 'status-pill connected').replace('Disconnected', 'Connected').replace('id="statusIcon">✕', 'id="statusIcon">✓')
source = source.replace('</head>', '<link rel="stylesheet" href="map.css"></head>')
source = source.replace('</body>', '<script src="map.js"></script></body>')
(OUT / 'preview.html').write_text(source, encoding='utf-8')
print('Built preview.html from current UI; original scripts and event handlers removed.')
