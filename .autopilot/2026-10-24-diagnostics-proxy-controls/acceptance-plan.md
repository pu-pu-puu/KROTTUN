# План приёмки

## До изменений
- python -m unittest discover -s tests: 99 passed (2026-10-24).

## Изолированные проверки
- Полный unittest suite после каждого таска и после ремонта.
- Редактирование: сохранение id, blank password keep, explicit clear, special characters, bad fields, save rollback, running snapshot isolation, stale geo.
- Резервы: migration, explicit [], reorder/exclude, next-connect semantics, no excluded candidate in watchdog, bounded exhaustion, release/cancel regression.
- Диагностика: фиксированные пути, trust_env=False, no redirects, safe responses, blocked skip, unarmed explicit proxy, context invalidation, one worker, hard timeout, Job-before-gate, retain process ownership, UI single-flight/timeouts.
- Production HTML с fake pywebview: edit/password/reserve/diagnosis, 520x760 screenshots, no injection/overflow, existing map/mesh/protection/log regression.
- Чистый clone с существующими зависимостями: полный suite и слепая приёмка только по brief (без spec/manifest).
- PyInstaller EXE: output dist/proxy-controls/KROTTUN.exe; archive check UI/core binaries/version/multiprocessing hook. Не запускать.

## Сохраняющиеся ограничения
Нативная Windows VM/IPv6/reboot и live frozen-helper acceptance не закрываются offline-проверками. Не выполнять app launch, WFP/TUN/release, host capture, публикацию.
