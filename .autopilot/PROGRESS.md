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
- 2026-10-23 — исправлены три дефекта независимого ревью: hard deadline/cancel проверки туннеля с killable child и сохранением handle до подтверждения выхода; обновление DNS при отсутствии политики с hostname binding; инвалидация IP/таймера при release. 96 tests OK, независимое source review SAFE. Новая сборка dist/review-fixes/KROTTUN.exe; GUI/native/frozen-helper runtime не запускались.
- 2026-10-23 — выбран вариант 3 блока защиты: сегментированная панель, честные состояния и короткое действие снятия; при unarmed кнопка скрыта. Опрос защиты отделён от журнала, зависший запрос переводит статус в unknown без накопления RPC. 86 tests OK, source review SAFE; dist/protection/KROTTUN.exe. Backend/размер окна/терминальный лог сохранены; render/live GUI QA не выполнялся.
- 2026-10-23 — по уточнению пользователя убрано оформление всей вкладки и resize API. Терминал изолирован в #terminalLogPane; 85 tests OK, static JS/IDs/CSS isolation и source review SAFE. Новая сборка dist/log-panel/KROTTUN.exe.
- 2026-10-23 — внедрён одобренный ASCII Terminal для журнала, выбор строки/инспектор, реальные счётчики, расширение/восстановление окна с DPI bounds. 87 tests OK, static JS/ID и source review SAFE. Новый EXE dist/terminal/KROTTUN.exe; render/live GUI QA не проводился из-за запрета локального browser render. Сетевые модули не изменялись.
- 2026-10-23 — исправлены зависший protected IP refresh и отсутствие доменов в журнале; 83 tests OK, ревью и живой UiCheck пройдены. Windows system proxy обнаружен включённым, настройки не менялись. Исправленный EXE: dist/fixed/KROTTUN.exe, детали .autopilot/user-ip-domain-fix.md.
- 2026-10-23 — исправлен конфликт имени Wintun после crash: отдельный alias на запуск и точный LUID; включён поиск процессов для журнала. Core-crash failover пройден, proxy-outage функционально пройден с inconclusive no-leak verdict. 75 tests OK; дальнейшие живые проверки в этом цикле завершены.
- 2026-10-22 — подготовлен реальный EE/US TUN/failover тест с независимым recovery и scoped raw WFP cleanup; 52 tests OK и safety review. UAC Stage3 отменён Windows до старта Python, живой failover ещё не проверен. Повтор только после нового подтверждения пользователя.
- 2026-10-22 — исправлен нулевой layerKey перечисления WFP, обнаруженный на native preflight; добавлены host-validation/recovery scripts и тесты watchdog race. Реальный короткий deny-only тест с UAC пройден, правила удалены.

