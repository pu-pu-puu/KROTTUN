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
