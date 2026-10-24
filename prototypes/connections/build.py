"""Offline color and copy exploration; no application or native bridge imports."""
from pathlib import Path
import re
import base64

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
source = (ROOT / 'gui/web/index.html').read_text(encoding='utf-8')
source = re.sub(r'<script\b([^>]*)>.*?</script>', lambda m: m[0] if 'data-world-map' in m[1] else '', source, flags=re.S)
source = re.sub(r'\s+on\w+="[^"]*"', '', source)
for name in ['krottun_banner.png','krottun_banner_dark.png','krottun_banner_light.png']:
    data=base64.b64encode((ROOT/'gui/web'/name).read_bytes()).decode()
    source=source.replace(f'src="{name}"',f'src="data:image/png;base64,{data}"')
source=source.replace('class="view-content hidden" id="viewConnections"','class="view-content" id="viewConnections"').replace('class="view-content" id="viewHome"','class="view-content hidden" id="viewHome"')
source=source.replace('class="nav-btn active" id="tabHome"','class="nav-btn" id="tabHome"').replace('class="nav-btn" id="tabConnections"','class="nav-btn active" id="tabConnections"')
source=source.replace('data-state="unknown"','data-state="protected"').replace('Статус неизвестен','Включена').replace('Проверьте подключение','').replace('Загрузка...','203.0.113.24')
header='''<div class="journal-heading">
<div><h2>Соединения</h2><p id="connectionSource">Источник: снимки ядра</p></div>
<details class="journal-help"><summary>О журнале</summary><div><strong>Что здесь показано</strong><p>Снимки соединений ядра. В памяти — до 1000 строк.</p><p>Имена сайтов берутся из HTTP/TLS, когда приложение их передаёт. HTTPS не расшифровывается. Короткие подключения могут не попасть в журнал.</p></div></details>
</div>
'''
source=re.sub(r'<h2>Соединения</h2>.*?(?=      <div id="terminalLogPane")',header,source,flags=re.S)
source=source.replace('placeholder="> Фильтр"','placeholder="Сайт или программа"')
source=source.replace('[ Пауза ]','Пауза').replace('[ Очистить ]','Очистить')
source=source.replace('Имя сайта показывается только когда его передаёт приложение.','Адрес, программа и маршрут выбранной строки.')
source=source.replace('Снимки · без расшифровки HTTPS','До 1000 строк')
source=source.replace('</head>','<link rel="stylesheet" href="themes.css"></head>')
source=source.replace('</body>','<script src="preview.js"></script></body>')
for n in [1,2,3]:
    (OUT/f'variant-{n}.html').write_text(source.replace('<body>',f'<body data-theme="{n}">'),encoding='utf-8')
print('Created three isolated connection journal variants.')
