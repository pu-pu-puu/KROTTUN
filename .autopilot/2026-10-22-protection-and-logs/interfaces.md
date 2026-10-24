# Контракты

## Правила проекта
Пользователь: «прокси отвалилась → прямой интернет заблокирован → пробуем резервную».
База v2.4.0; сохранять Python, pywebview, sing-box. Реальные системные настройки в ходе разработки не изменять.

## Границы
Реализованные публичные API: KillSwitch.arm(endpoints, app, interface=None), status(), disarm(); WindowsWfpBackend.replace/read/app_id; ProtectionSession.connect/stop/release; ConnectionJournal.append/read/clear; мост get_connections/clear_connections/release_protection.
Проверка: `python -m unittest discover -s tests` (база 15 passed). Один файл: `python -m unittest discover -s tests -p test_protection.py`. Установка существующих зависимостей: `python -m pip install -r requirements.txt`. Разрешены только стандартная библиотека и уже имеющиеся зависимости; без новых пакетов. Запуск приложения при разработке не выполнять, поскольку он меняет реальную сеть.

Один исполнитель владеет всей реализацией, поэтому внутренние сигнатуры выбирает согласованно после исследования notes.md.
core/kill_switch.py: системная фильтрация, инъекция backend для тестов; arm/endpoints/status/disarm; persistent, fail closed, только собственные правила; Windows ctypes WFP предпочтителен. Запрещено blanket firewall block + allow (Windows block overrides allow), отключение пользовательских правил, глобальный firewall reset.
core/singbox_manager.py: strict config, отсутствие прямого fallback, жизненный цикл ядра без снятия защиты при stop/start/error.
gui/app_webview.py: единственный сериализованный жизненный цикл и резервирование, видимые состояния защиты; мост журнала с ограниченным объёмом.
core/connection_log.py: память, санитаризация и источник записей ядра/событий.
gui/web/index.html: вкладка журнала и состояние защиты, явное снятие защиты. HTML rendering пользовательских строк через textContent/escaping.
Тестовые швы: mock firewall backend, fake process/tunnel, fake clock/log source; тесты не создают реальных правил/адаптеров и не обращаются к внешним сервисам.
