"""Apply the selected first journal prototype without changing data contracts."""
from pathlib import Path
import re

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
target=ROOT/'gui/web/index.html'
html=target.read_text(encoding='utf-8')
if 'class="journal-heading"' in html:
    raise SystemExit('Journal prototype is already applied')
css=(OUT/'themes.css').read_text(encoding='utf-8')
css=re.sub(r'^body\[data-theme="[23]"\].*\n','',css,flags=re.M)
css=css.replace('body{--log-bg:', '#terminalLogPane{--log-bg:',1)
html=html.replace('  </style>',css+'\n  </style>')
header='''<div class="journal-heading">
        <div><h2>Соединения</h2><p id="connectionSource" role="status">Источник: недоступен</p></div>
        <details class="journal-help"><summary>О журнале</summary><div>
          <strong>Что здесь показано</strong>
          <p>Снимки соединений ядра. В памяти — до 1000 строк.</p>
          <p>Имена сайтов берутся из HTTP/TLS, когда приложение их передаёт. HTTPS не расшифровывается. Короткие подключения могут не попасть в журнал.</p>
        </div></details>
      </div>
'''
html=re.sub(r'<h2>Соединения</h2>.*?(?=      <div id="terminalLogPane")',header,html,count=1,flags=re.S)
html=html.replace('placeholder="> Фильтр"','placeholder="Сайт или программа"')
html=html.replace('[ Пауза ]','Пауза').replace('[ Продолжить ]','Продолжить').replace('[ Очистить ]','Очистить')
html=html.replace('Имя сайта показывается только когда его передаёт приложение.','Адрес, программа и маршрут выбранной строки.')
html=html.replace('Снимки · без расшифровки HTTPS','До 1000 строк')
html=html.replace('Источник недоступен','Источник: недоступен').replace('Снимки ядра; максимум 1000 строк в памяти','Источник: снимки ядра')
html=html.replace('<table class="terminal-table">','''<table class="terminal-table">
          <colgroup><col style="width:18px"><col style="width:64px"><col style="width:216px"><col style="width:112px"><col style="width:74px"><col style="width:100px"><col style="width:166px"></colgroup>''',1)
target.write_text(html,encoding='utf-8')
print('Applied Blue Ice palette, compact truthful source status and expandable journal explanation.')
