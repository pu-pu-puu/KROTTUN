# Исправление наложения бейджей и замера при включённом TUN

## Запрос
Исправить наложение SOCKS5/HTTP на пинг в строке сервера и неработающие кнопки замера при включённом туннеле.

## Причины до исправления
- После добавления «Изм.» правый блок расширился; flex-контейнер левой части и строка названия не выделяют независимое место протоколу. Текст обрезается, а содержимое строки выходит к пингу.
- ping_proxy/ping_all безусловно отклоняют state != unarmed. testAllPings игнорирует error; testSelectedPing не проверяет success и допускает undefined latency. Исключения не восстанавливают UI через finally.

## Ограничения решения
- Существующий дизайн/окно/фон/защиту сохранить; отдельное место для протокола, пинга и действий, ellipsis только для названия/подписи.
- Healthy protected RUNNING: замер ответа сервера через текущую маршрутизацию TUN, без новых прямых исключений WFP. Время включает текущий туннель; это не прямая задержка от ПК до сервера.
- Чтобы не принять локальный TCP handshake TUN за ответ удалённого сервера, защищённый замер ждёт ответ известного протокола SOCKS5/HTTP, без credentials. Это не проверка правильности пароля.
- Unarmed IDLE: прежний TCP connect замер. blocked/unknown/transitions: понятный отказ без сетевых проб.
- Один ограниченный spawn worker для пачки; Job до request gate, hard deadline, отмена/снятие защиты с подтверждением выхода, защита от stale results/edit/delete и повторных нажатий.
- Только offline/fake transport и browser rendering, без запуска main/EXE или изменения реальной сети. В конце новая локальная сборка, проверка embedded assets.

## Проверка после исправления
- Regression RED: защищённый ping отклонялся; release не ждал ping worker; на 480px протокол упирался в действия.
- Full unittest suite: 134 tests, 11.241s, OK. Focused ping tests: 14.
- Browser verifier: PASS, 480/520px, selected/active, SOCKS5/HTTP, длинные названия, 9999ms/unknown, ошибки RPC/rejection/undefined latency/all-timeout/hang, single-flight/finally и сохранение режима замера. Отдельный regression сохраняет «Таймаут» после refresh выбранной карточки. Внешние запросы браузера запрещены.
- Независимое ревью: Critical/Important замечаний нет. Minor о сбросе выбранного timeout исправлен с воспроизводящим тестом.
- Impeccable detector: прежние визуальные паттерны (mesh/glass/easing) сохранены согласно установленному оформлению. Геометрия подтверждена browser rect assertions и визуальным просмотром снимков.
- Защищённый замер ждёт ответ SOCKS5/HTTP без credentials; подтверждает доступность протокола, включая запрос авторизации, а не правильность пароля. Измерение включает маршрут текущего TUN. Тип latency_mode сохраняется; старые записи по умолчанию tcp.
- PyInstaller exit 0: dist/ping-layout-fix/KROTTUN.exe, 44 131 935 bytes, version2.5.0.
- SHA256: 8fb650c2e087bf8a8957804e3963da1dc5213e8699993cb721a6ccb1724c5a12.
- Архив: HTML, sing-box, Wintun, bytecode bridge/diagnostics/ping_service/proxy_model/version/main совпадают с source; multiprocessing hook и requireAdministrator подтверждены.
- Native GUI/EXE, реальный защищённый transport и frozen ping helper не запускались; WFP/маршруты/Windows proxy не менялись. VM/IPv6/reboot приёмка защиты остаётся открытой.
- Старые screenshots, перезаписанные тестовым verifier, восстановлены по HEAD; пользовательские host-capture/PROGRESS изменения не включены.
