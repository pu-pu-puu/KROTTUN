# Исправления независимого ревью

Источник: Codex thread 01a16972-d38b-7bb0-be4c-548005f5c168; пользователь разрешил исправления («делай», «продолжай»).

Область: hard deadline и отмена проверки туннеля; обновление DNS доменных прокси при отсутствии активной политики; немедленная инвалидация IP/времени подключения при явном снятии защиты.

Проверка: регрессии на зависший запрос/поздний успех/отмену и ограничение фоновой работы; DNS refresh при unarmed без прямого DNS при защищённом состоянии; IP invalidation и отбрасывание устаревшего результата. Полный offline suite, независимое source review, затем отдельная EXE-сборка.

Не запускать приложение и не менять WFP/TUN на хосте. Визуальный scope и существующие требования защиты сохраняются. Offline-тесты не доказывают отсутствие сетевых утечек.

Результат: 96 tests passed (baseline86 +10 lifecycle regressions); независимое source review SAFE. Probe — один spawn worker с ready barrier после привязки к kill-on-close Job; deadline/cancel/stop подтверждают выход, ошибка cleanup сохраняет handle и блокирует новый worker/release. 204 не читает тело, Firefox читает максимум64 decoded bytes. Ранний freeze_support до импортов GUI.

DNS обновляется на каждом policy-absent snapshot без fallback к старому ответу; protected cache привязан к hostname, numeric candidate сбрасывает прежнюю привязку. Старые recovery markers без hostname metadata отвергаются для доменных подключений при активной защите: снять защиту явно и переподключить, чтобы обновить DNS. Прямой DNS при активной политике не добавлен.

Release инвалидирует IP до ожидания lifecycle lock, после успешного снятия очищает IP/connected_since; устаревший IP worker не публикуется.

Проверка Windows Job semantics: https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-assignprocesstojobobject . Exact-job membership проверяется до assignment. Реальные native Job действия в тестах mocked; spawned stalled helpers не выполняют сеть. При первоначальном RED-прогоне старой inline-реализации был выполнен обычный probe до исправления тестового seam; последующие focused/full runs используют offline helper/request mocks. Firewall/TUN не менялись.

Frozen-helper runtime smoke и запуск GUI не выполнены. Сборка и проверка embedded assets/bytecode не заменяют эту проверку.

EXE: dist/review-fixes/KROTTUN.exe, 44,095,488 bytes; SHA256 7e4b3a1de7fa7481bb8154bc0c01a5d3d9b5cfe821767ea055a57b6e7b6d5f3b. Проверены совпадение embedded HTML/sing-box/Wintun, точное равенство bytecode всех четырёх изменённых core/gui modules и main.py исходникам, multiprocessing runtime hook и requireAdministrator manifest.
