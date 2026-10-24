# 02 — Явная очередь резервов

**Требования:** R03, R04
**Зависит от:** 01
**Зона:** `gui/app_webview.py` · `gui/web/index.html` · `tests/test_fallback_controls.py`
**Волна:** 2
**Ревью:** да — защита и целостность настроек
**Модель:** сильная

## Что должно заработать
Пользователь задаёт включённые резервы и порядок; старт и watchdog честно используют фиксированный набор, без исключённых узлов и без циклического failover.

## Из брифа, дословно
> «Управление резервами»
> «через скил автопилот»

## Разделы спецификации
Резервы (R03); общие ограничения Решения по реализации и Доставка (R04). interfaces.md и notes.md первыми.

## Критерии приёмки
- [ ] Диалог выбора/исключения и вверх/вниз, понятный основной сервер, пустая очередь и сообщение о применении со следующего подключения.
- [ ] Persist ordered IDs: legacy default all existing, explicit empty preserved, new servers after explicit save opt-out, duplicates normalized/read, malformed/unknown IDs on write rejected, disk failure rollback.
- [ ] Primary first, same ID not repeated. Снимок копий primary+reserves строится на каждый ручной start; правки списка/импорт/удаление не меняют активный снимок.
- [ ] И старт, и watchdog используют одну очередь сессии; исключённые не пробуются, после последовательных отказов exhaustion без циклов, защита остаётся.
- [ ] Cancel/release/shutdown/generation существующего lifecycle сохранены; offline тесты initial start и watchdog с fake protection подтверждают маршрут кандидатов.
- [ ] Полный suite зелёный; API settings не содержит credentials; существующее редактирование работает.
