<!-- autopilot:progress -->
# KROTTUN — состояние работы

Прогон: `.autopilot/2026-10-22-protection-and-logs/`. Код защиты, резервирования и журнала реализован; offline-приёмка пройдена. Окончательная сетевая приёмка не пройдена.

## Договорились — не пересматривать
- Журнал: терминальное оформление ТОЛЬКО внутри выделенного пользователем оранжевого блока (фильтр/пауза/очистка и вывод журнала). Вся вкладка вокруг остаётся синей, окно 520×760 без автоматического расширения.
- «прокси отвалилась → прямой интернет заблокирован → пробуем резервную» — R02/R03.
- Защита всего ПК; прямые исключения отключены. Закрытие сохраняет фильтры; снятие отдельной явной командой.
- Autopilot v2.2.0; ответы кратко, caveman ultra.

## Не доделано
- На рабочем ПК выполнены native preflight, deny-only IPv4 smoke, реальный TUN EE1→US2 core-crash failover и exhaustion; восстановление подтверждено. Proxy-outage: functional_ok=true, classification=inconclusive из-за timeout egress checks. См. `.autopilot/host-validation.md`. 75 tests OK.
- R03: изолированная Windows VM с packet capture обязательна: native WFP ABI/фильтры, старые соединения, IPv4/IPv6/DNS, падение ядра/GUI/сети, BOOTTIME/BFE, смена интерфейса и reboot. Утечки не доказаны отсутствующими; к выпуску не допускать до проверки.
- R04/R05: live `/connections`, строки соединений и process metadata проверены с поставляемым ядром; интерактивный UI-прогон остаётся не выполнен.
- Чистая установка зависимостей и полный запуск приложения не проверены. Чистый git clone с существующими зависимостями: 28 tests OK.

## Известные ограничения
- R05: snapshots активных соединений могут пропускать короткие. HTTPS без расшифровки, тел запросов нет.
- R06: ограничены фоновые проверки KROTTUN, гарантий репутации прокси/отсутствия антифрод-блокировок нет.
- UDP в защищённом режиме отклоняется; домены разрешаются до arm, при защите нужен кэш числовых endpoint.
- Ошибки остановки, ранней отмены и пересоздания TUN после crash исправлены. После разрешённых host-тестов собственные правила сняты, TUN отсутствует, TCP восстановлен.

## Правки без автопилота
- 2026-10-24 — Git author/committer настроены глобально и локально как pu-pu-puu с ID-based noreply; в GCM оставлен только pu-pu-puu. Правило закреплено в AGENTS.md. Интерфейс/прототипы/проверки фиксируются отдельным UI-коммитом; приватные host captures и кадры видео остаются локально. GitHub release v2.5.0 и asset опубликованы pu-pu-puu, прежние Git-коммиты имеют историческое авторство ui-ux-promax.
- 2026-10-24 — выбран «Синий лёд» для соединений: синий терминал/ледяные адреса, компактный честный источник, пояснения в details «О журнале», фиксированные ширины 7 колонок и увеличенная высота лога без расширения окна. API/данные не изменены. Browser production check фильтр/выбор/пауза/очистка/unavailable/help без сдвига OK; 99 tests OK (HTMLParser теста учитывает void col). Карта/mesh сохранены. dist/blue-ice/KROTTUN.exe: PyInstaller exit0, embedded UI/sing-box/Wintun совпадают с исходниками. EXE/network не запускались.
- 2026-10-24 — одобренный прототип контурных SVG перенесён в GUI: заголовки, пинг, импорт/добавление, стрелки, статусы, удаление. Динамические обновления используют локальный whitelist uiIcon; пользовательские строки серверов остаются textContent. Browser runtime regression статусов/ping reset/delete/XSS OK; 99 tests OK; protection geometry и карта/mesh checks OK. dist/svg-icons/KROTTUN.exe собран, embedded HTML/sing-box/Wintun совпадают с исходниками; APP_VERSION=2.5.0. EXE/network не запускались.
- 2026-10-24 — native заголовок заменён на KROTTUN — v2.5.0 по текущему Git tag; APP_VERSION в core/version.py. 99 tests OK. dist/version-title/KROTTUN.exe: PyInstaller exit0, compiled version/title и embedded HTML/sing-box/Wintun проверены. Эмодзи пока не менялись: пользователь запросил рекомендации по замене.
- 2026-10-24 — по видео пользователя устранён скачок панели при смене protectionHelper: раньше высота 76.94→66.5px, теперь grid с постоянными строками 34/16px и сохранением места hidden-элементов; unarmed hint занимает обе строки при скрытой кнопке. Изолированный browser regression всех 6 состояний при 520/480px: панель 77px, координаты таймера/тумблера/кнопки неизменны, подсказки помещаются. 99 tests OK; карта/ambient mesh сохранены. Новая сборка dist/stable-ui/KROTTUN.exe, PyInstaller exit0. GUI/network не запускались.
- 2026-10-24 — по запросу пользователя пересобран dist/world-map/KROTTUN.exe (44,098,144 bytes), SHA256 553a904da12a3b68ab974cfb2cab7012443a479a2438ed3b02082c78d1b9dcd6. PyInstaller exit0; embedded HTML/sing-box/Wintun совпадают с исходниками, multiprocessing hook присутствует. EXE не запускался.
- 2026-10-24 — выбран и перенесён вариант 1 фоновой карты: top=165px/height=350px, ярче матрица, плавное мерцание 13 столиц. По явному требованию пользователя body::before с мелкими точками по всему фону сохранён без изменений; исходный SVG тоже сохранён. Изолированный render 520×760, hidden pause/reduced-motion/JS checks OK; 99 tests OK. GUI/network не запускались, EXE не пересобирался. Проверка: prototypes/world-map/verify-production.cjs.
- 2026-10-23 — повторное внешнее ревью подтвердило исходные исправления и выявило P2 release/probe→лишний failover и ложную готовность Job после ошибки конфигурации. Исправлены: stopping intent/pending/operation generation, запрет сброса пользовательской отмены watchdog, атомарная настройка Job на временном handle. 99 tests OK, source review SAFE; dist/review-final/KROTTUN.exe. GUI/native runtime не запускались.
- 2026-10-23 — исправлены три дефекта независимого ревью: hard deadline/cancel проверки туннеля с killable child и сохранением handle до подтверждения выхода; обновление DNS при отсутствии политики с hostname binding; инвалидация IP/таймера при release. 96 tests OK, независимое source review SAFE. Новая сборка dist/review-fixes/KROTTUN.exe; GUI/native/frozen-helper runtime не запускались.
- 2026-10-23 — выбран вариант 3 блока защиты: сегментированная панель, честные состояния и короткое действие снятия; при unarmed кнопка скрыта. Опрос защиты отделён от журнала, зависший запрос переводит статус в unknown без накопления RPC. 86 tests OK, source review SAFE; dist/protection/KROTTUN.exe. Backend/размер окна/терминальный лог сохранены; render/live GUI QA не выполнялся.
- 2026-10-23 — по уточнению пользователя убрано оформление всей вкладки и resize API. Терминал изолирован в #terminalLogPane; 85 tests OK, static JS/IDs/CSS isolation и source review SAFE. Новая сборка dist/log-panel/KROTTUN.exe.
- 2026-10-23 — внедрён одобренный ASCII Terminal для журнала, выбор строки/инспектор, реальные счётчики, расширение/восстановление окна с DPI bounds. 87 tests OK, static JS/ID и source review SAFE. Новый EXE dist/terminal/KROTTUN.exe; render/live GUI QA не проводился из-за запрета локального browser render. Сетевые модули не изменялись.
- 2026-10-23 — исправлены зависший protected IP refresh и отсутствие доменов в журнале; 83 tests OK, ревью и живой UiCheck пройдены. Windows system proxy обнаружен включённым, настройки не менялись. Исправленный EXE: dist/fixed/KROTTUN.exe, детали .autopilot/user-ip-domain-fix.md.
- 2026-10-23 — исправлен конфликт имени Wintun после crash: отдельный alias на запуск и точный LUID; включён поиск процессов для журнала. Core-crash failover пройден, proxy-outage функционально пройден с inconclusive no-leak verdict. 75 tests OK; дальнейшие живые проверки в этом цикле завершены.
- 2026-10-22 — подготовлен реальный EE/US TUN/failover тест с независимым recovery и scoped raw WFP cleanup; 52 tests OK и safety review. UAC Stage3 отменён Windows до старта Python, живой failover ещё не проверен. Повтор только после нового подтверждения пользователя.
- 2026-10-22 — исправлен нулевой layerKey перечисления WFP, обнаруженный на native preflight; добавлены host-validation/recovery scripts и тесты watchdog race. Реальный короткий deny-only тест с UAC пройден, правила удалены.

