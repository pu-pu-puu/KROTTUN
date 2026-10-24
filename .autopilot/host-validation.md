# Проверка на рабочем ПК — 2026-10-22

Пользователь согласился на временную потерю интернета и сообщил «ок я готов». Уточнён порядок: сначала noncommitting native WFP preflight; реальные блокировки только после готового локального восстановления. Перезагрузка не выполняется.

Текущий процесс не elevated. BFE/MpsSvc running, pktmon присутствует. Native preflight запущен отдельным elevated Python через UAC.

## Первый результат
Отчёт tools/host-validation/reports/stage1.json: ok=false, phase=existing-policy-read, native_codes=[0x80320004], committed=false, abort_attempted=false, close_ok=true. До транзакции и добавления фильтров не дошло. Системная сеть не изменена.

Причина: production _owned() создаёт непустой FWPM_FILTER_ENUM_TEMPLATE0 с нулевым layerKey. Microsoft описывает layerKey как слой перечисления; NULL template перечисляет все фильтры. Исправление должно сохранять охват boot/disabled собственных фильтров.

Источники: [FWPM_FILTER_ENUM_TEMPLATE0](https://learn.microsoft.com/en-us/windows/win32/api/fwpmtypes/ns-fwpmtypes-fwpm_filter_enum_template0), [FwpmFilterCreateEnumHandle0](https://learn.microsoft.com/en-us/windows/win32/api/fwpmu/nf-fwpmu-fwpmfiltercreateenumhandle0).

Далее: regression test + fix, затем повтор noncommitting preflight. Live commit блокировки/пакетная приёмка ещё не выполнялись.

## Исправление и повтор
_owned() перечисляет шесть конкретных layer GUID с сохранением INCLUDE_BOOTTIME/INCLUDE_DISABLED. 35 tests OK. Native повтор: ok=true, phase=transaction-readback, rule_count=26, committed=false, abort_attempted=true, abort_ok=true, close_ok=true. Фильтры не применены. Это подтверждает native создание/чтение/отмену, но не сетевую защиту.

## Следующий этап
Короткий deny-only smoke без настоящих прокси/TUN: сначала baseline TCP и пустая собственная политика, затем независимый локальный watchdog, dry-run создания/удаления в отменяемой транзакции, пятисекундная блокировка и явная очистка. Никакой перезагрузки. Фактическое отсутствие packet leaks по-прежнему не доказано без capture.

## Stage 2 — реальный host smoke пройден
Перед запуском независимое ревью обнаружило гонку: watchdog мог завершиться до отложенного arm родителя. Исправлено: по expiry сначала подтверждается завершение точного родительского тестового процесса (PID/create time/executable/helper path/nonce), затем выполняется scoped cleanup. Неподтверждённое завершение/cleanup не выдаёт успех. Дополнительные mock-тесты покрывают гонку и PID reuse. 45 tests OK.

UAC live запуск tools/host-validation/stage2.ps1: exit0. Отчёт stage2.json: ok=true, classification=passed, blocked_checks=[firewall-denied-10013], ipv6=unavailable, cleanup_ok=true, restored_tcp=connected, run=90147a2e-4dd4-4980-b6fc-c886614e37d1. До теста TCP 1.1.1.1:443 работал, при production deny-only WFP политике новый connect отвергнут Windows 10013, после удаления собственных правил снова connected. Тестовые правила не оставлены; чужие правила не удалялись.

Это connectivity smoke: IPv4 блокировка и восстановление подтверждены на реальном ПК. IPv6 baseline отсутствовал, тест не засчитан. DNS, существующие TCP/UDP-потоки, TUN, реальные прокси/failover, packet capture, перезапуск и BFE/boot не проверены. Готовность к выпуску по-прежнему не подтверждена. Секреты прокси не читались и в отчёты не выводились.

## Stage 3 — подготовка
Пользователь: «да, там эстонская и американская прокся». Для теста выбраны EE primary и US reserve; пользовательский список/настройки не переписывать. Прокси читаются только локально из существующего защищённого хранилища; отчёт содержит страны, счётчики и логические результаты, без адресов, идентификаторов и credentials.

Сценарий: реальные TUN + production bridge watchdog, принудительное завершение только тестового ядра, автоматический переход EE → US, отказ всех кандидатов при изменении списка только в памяти, сохранение deny и явное локальное восстановление. Watchdog запускается до Job Object тестового процесса; обязан оставаться вне него. Recovery должен удалять только фильтры OWNER по raw sublayer GUID, не зависеть от разбора metadata и не снимать защиту до подтверждённого завершения тестового ядра. Сначала подготовка, offline tests и независимое ревью; затем UAC запуск.

## Stage 3 — подготовлен, запуск UAC отменён
Добавлены proxy_failover.py и stage3.ps1 (также InspectOnly). 52 tests OK, независимое ревью после исправления residual-TUN проверки: SAFE FOR BOUNDED LIVE SMOKE. Watchdog не снимает защиту/marker и не сообщает success, пока ядро и sing-tun не исчезнут; начальный собственный policy/TUN/marker отвергаются. Пользовательские настройки/список не переписываются.

Попытка реального запуска stage3.ps1 остановилась в Start-Process -Verb RunAs. Windows: “The operation was canceled by the user.” Elevated Python не стартовал; stage3.json не создан. Ни WFP, ни TUN этим запуском не менялись, доступ к сохранённым прокси в нём не выполнялся. Не повторять UAC автоматически после отмены; требуется новое подтверждение пользователя.

Следующий запуск при подтверждении: `powershell -NoProfile -ExecutionPolicy Bypass -File D:\Projects\KROTTUN\tools\host-validation\stage3.ps1`. Сначала читать sanitized stage3.json; не выводить credentials/полный get_state/engine logs. Сессия ожидания 81684 завершилась exit1.

## Повтор после подтверждения и диагностика
Пользователь: «да повтори. я отходил от компа». UAC принят. Обнаружено EE2/US2; selector изменён на первый сохранённый EE/US без перезаписи списка. Первый live a28a1c00-cf15-4487-b414-26f1a8ac61b6: EE работает, exit отличается от baseline, journal15rows, corekill deny10013; US-first failover timeout, cleanup/no_tun/restored=true.

Пользователь: «там помоему одна прокся не работает. которая лос анджелес. бери другую». Выбран US index2, Лос-Анджелес больше не тестируется. Прямой AvailabilityOnly для EE1/US2: обе success=true. Live95d8fda7-c14a-4dcf-b29f-b7ff33ca81a7: EE работает, USsecond start `_wait_ready`15s false при живом процессе; cleanup/no_tun/restored=true. Обратный порядок US2→EE1 (0b0cbcda-1985-4247-a3db-e33be4f78258) подтвердил: US работает первой, EE не пересоздаётся. Вторая попытка не имеет ни sing-tun*, ни адреса TUN на других интерфейсах. Процессы в live journal пока unavailable.

Memory-only debug capture прошёл независимое ревью, raw logs не сохраняются. Прогон6f131538-93f0-4272-a19e-84867e207884: второй старт FATAL configure-interface/create-adapter “cannot create a file when that file already exists”; затем ошибка открытия прежнего адаптера. Все cleanup/no_tun/restored=true. 62 tests OK до исправления продукта.

## D02: причина и исправление повторного TUN
sing-tun выводит GUID адаптера из его имени; при ErrExist пробует OpenAdapter с тем же именем. Аварийно завершённый Wintun может оставить конфликт при имени sing-tun, хотя адаптер уже не виден в psutil. План: отдельное принадлежащее KROTTUN имя для каждого запуска ядра, точное имя в готовности/stop/telemetry и точный LUID в WFP; helper recovery учитывает legacy и новый префикс. Чужие адаптеры не удаляются; разрешение WFP по произвольному префиксу запрещено.

Первичный источник: [sing-tun Windows New/configure](https://raw.githubusercontent.com/SagerNet/sing-tun/main/tun_windows.go); схожая ошибка описана в [SagerNet/sing-box #716](https://github.com/SagerNet/sing-box/issues/716). Фактическая причина на ПК подтверждена native logs, а не выведена только из issue.

## D02: native исправление подтверждено
Manager создаёт sing-tun-UUID после подтверждённого завершения старого процесса и исчезновения старого точного адаптера. Config/readiness/stop/telemetry привязаны к interface_name. ProtectionSession передаёт текущее имя в lookup, WFP разрешает точный LUID; prefix-разрешений нет. Harness recovery учитывает legacy и новые имена. Независимое safety review: SAFE; 68 tests OK до следующего дополнения.

Native прогон ded35224-6006-44df-a996-7a0efcde3879: ok=true, phase=reserve-exhaustion. EE1 работает, exit отличается от baseline; journal9rows/source available. EE core kill: local TCP10013. Автоматический переход US2 успешен, exit отличается от baseline и EE. При исчерпании кандидатов blocked=true. cleanup_ok=true, no_tun=true, restored_tcp=true. Список кандидатов менялся только в памяти, реальные записи/настройки не переписывались.

## Следующая complementary проверка
Только отказ прокси при живом ядре: снять endpoint exception в собственном WFP policy, сохранив текущий точный TUN LUID; production health watchdog сам обнаруживает отказ и переключается. Не убивать ядро и не подменять probe result. `-FaultMode Proxy -UsIndex 2`, независимое восстановление сохранено. Таймауты и HTTP errors не считать доказанной блокировкой. Packet/DNS/IPv6/reboot остаются вне этой проверки.

R05: наблюдались соединения без process fields. Причина в конфигурации: protected rules не требуют поиска процесса, find_process по умолчанию false. Включён find_process=true, поле принято offline sing-box check; реальная доступность имён будет оценена следующим прогоном. [Документация find_process](https://sing-box.sagernet.org/configuration/route/#find_process).

## Итог host-проверки — 2026-10-23
75 unit-тестов проходят; production исправление закоммичено dc54045. Живой журнал после find_process=true возвращает process metadata (4 наблюдавшихся соединения в последнем прогоне), без вывода пользовательских данных в отчёт.

Proxy-mode 52495b76-b114-4790-939f-9170ada97fca: functional_ok=true. Ядро оставалось живым при локальном удалении endpoint exception. Production watchdog сам обнаружил сбой и сменил EE1 на US2; оба proxy exit отличаются от baseline и друг от друга. После отказа резерва и исчерпания списка exhaustion-blocked=true. cleanup_ok=true, no_tun=true, restored_tcp=true; дополнительная проверка psutil: 0 legacy/owned-prefix адаптеров.

Обе отрицательные egress-проверки дали timeout-inconclusive. Поэтому overall ok=false, classification=inconclusive, exit1 — намеренно, несмотря на функциональный успех. Таймаут не принят за доказательство отсутствия утечки. Полная packet/DNS/IPv6/существующие потоки/boot/BFE/reboot приёмка остаётся отдельной работой; выпуск как доказанной leak-proof защиты не подтверждён.

Использованы EE index1 и US index2; Лос-Анджелес исключён по указанию пользователя. Сохранённые записи/настройки не менялись. После тестов реальная сеть восстановлена. Других live-тестов в этом цикле не планируется.
