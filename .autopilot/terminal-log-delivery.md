# ASCII Terminal — поставка

План: docs/superpowers/plans/2026-10-23-terminal-logs.md. Одобренный макет и промпты сохранены в design/log-prototypes-2026-10-23/. Реализованный язык: design/logs-terminal.md.

Изменено: только журнал frontend и UI-only geometry bridge set_log_view(bool). Выбор/upsert/filter/pause/clear/XSS защищены non-rendering DOM test; idempotent expansion/restore и 150% DPI/смешанные мониторы проверены fake-window tests. Полная suite: 87 passed (база83).

Независимое source review нашло DPI mismatch, исправление повторно проверено: SAFE. Visual render не выполнялся; screenshot pass не заявляется. Новых live сетевых/административных тестов не было.

Сборка: python -m PyInstaller KROTTUN.spec --noconfirm --distpath dist/terminal --workpath build/terminal — exit0.
Файл: D:/Projects/KROTTUN/dist/terminal/KROTTUN.exe, 42.1 MiB.
SHA256: 16642d29db0db21f55189e5188935eb24d4dd9a10f31d5e9d27e706675569d98.
Archive check: HTML/binary hashes совпадают с source, terminal markup и inspector присутствуют, embedded set_log_view найден, protection modules и requireAdministrator manifest присутствуют.

Предыдущий dist/fixed/KROTTUN.exe сохранён. Никакие пользовательские процессы не завершались и настройки не переписывались.
