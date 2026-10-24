# IP и домены — исправление пользовательского отчёта

## Подтверждённые причины
- `_refresh_ip_async` отказывался обновлять IP при любой включённой защите; итогом могло оставаться «Загрузка…».
- Внешний IP helper наследовал environment/Windows proxy несмотря на proxies=None.
- Конфигурация не выполняла sniff до маршрутизации; журнал навсегда пропускал поздний hostname для уже известного connection ID.
- Таблица выводила длинный путь приложения и технические route/state с переносами внутри значений.

## Исправление
IP-запрос: один HTTPS через trust_env=False Session; только подходящий контекст, проверки generation/process/cancel/closing, независимый UI deadline4s, один реальный worker без неограниченных повторов. Late results не публикуются. При blocked состоянии запрос не выполняется.

Sniff HTTP/TLS/DNS выполняется перед DNS hijack и UDP reject без destination override и без MITM. Журнал обогащает существующую строку поздним hostname, ограничивает историю, показывает домен/IP и короткое имя процесса; raw route/state заменены понятными подписями. HTTP bodies, credentials, HTTPS paths не записываются.

Windows ProxyEnable обнаружен true; настроенный системный endpoint не совпал с сохранёнными узлами. Это потенциальный внешний конфликт для браузера. Registry не менялся; приложение выводит предупреждение. Прямая причинность всех браузерных отказов без отдельного browser-side теста не заявляется.

## Проверка
- Полная suite: 83 tests OK; независимое ревью исправлений SAFE.
- Bundled sing-box offline schema check с sniff/DNS order пройден; JavaScript syntax и PowerShell parser пройдены.
- Визуальное browser QA не выполнено: локальный file URL отклонён политикой встроенного браузера; обходы не использовались. Проверка интерфейса ограничена статическими проверками и реальным backend flow.
- Live UiCheck run13676072-a738-4af0-8f6b-b48864249b90: ok=true, functional_ok=true, classification=passed, phase=ui-protected-IP-and-TLS-domain. IP валиден и отличается от baseline; TLS example.com найден в journal, 6 connection rows; предупреждение system proxy присутствует. Реальные IP и endpoints в отчёты не выводились.
- cleanup_ok=true, no_tun=true, restored_tcp=true. Windows proxy и сохранённые настройки/список узлов не менялись.

## Сборка
`python -m PyInstaller KROTTUN.spec --noconfirm --distpath dist/fixed --workpath build/fixed` — exit0.
Файл: `D:/Projects/KROTTUN/dist/fixed/KROTTUN.exe`, 42.0 MiB.
SHA256: `88dea1eadb1d99464c1846b4d27f5c8760c6ecbab9a0d762c3f507d9d8ff5a17`.
Проверены вложенные sing-box/Wintun/HTML по hash, модули protection/journal/IP и manifest requireAdministrator. Сам собранный GUI EXE не запускался; headless UiCheck использовал тот же исходный backend.

Для проверки в Chrome: закрыть старую сборку, запустить исправленную, подключить рабочую прокси; после подтверждённого TUN отключить прежний системный proxy Windows (и browser proxy extension, если пользователь его использует). Полная packet/DNS/IPv6/reboot leak-proof приёмка по-прежнему не заявляется.
