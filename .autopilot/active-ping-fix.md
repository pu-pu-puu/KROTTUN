# Активный узел: замер HTTPS вместо обращения прокси к себе

## Наблюдение пользователя
Рабочий защищённый HTTP-туннель показывает внешний IP и Connected, но кнопка «Проверить пинг» выводит «Таймаут».

## Что установлено по коду
Защищённая проверка из предыдущей правки отправляет протокольный запрос к endpoint выбранной прокси через текущий TUN. Если проверяется активный endpoint, получается вложенное обращение через прокси обратно к ней же. Работоспособность обычного выхода не гарантирует доступность такого обращения. Конкретная причина отказа на рабочем сервере пакетным захватом не установлена; предыдущая классификация всех исключений как timeout также была слишком общей.

## Решение
Для фактически активного id: ограниченный HTTPS-замер через существующий TUN к фиксированному контрольному HTTPS-сервису, без обращения к собственному proxy endpoint. Trust_env=False, redirects=False, проверка статуса ответа, ограниченный stream/body/deadline. Для остальных узлов остаётся отдельный протокольный отклик через TUN. Прямых исключений или обхода защиты нет.
Числа разных типов не смешиваются: сохраняется tun_https/tun/tcp. Неудача активного HTTPS-замера означает «Нет замера», а не недоступную прокси; runtime health/failover не меняются. Ошибочный старый tun+dead у активного узла не должен переживать обновление UI как утверждение о неработающей прокси.
Существующий Job gate, ownership, deadlines, cancel/release и single-flight не переписываются. Проверки без запуска GUI/EXE и изменения сети.

## Проверено 2026-10-25
- Regression RED: активный HTTP-target вызывал собственный endpoint, результат timeout. После правки self-connect отсутствует.
- 21 focused ping tests; полный suite: 141 tests, 9.624s, OK (повторно после сброса лимитов).
- Browser verifier PASS: HTTPS-success/unavailable и legacy-active error при refresh, смешанные режимы, actual-active отличается от selected, прежняя геометрия 480/520 и ошибки UI.
- Контрольные HTTPS204: cp.cloudflare.com, затем www.gstatic.com при неудаче первого; только текущий TUN, без HTTP/direct fallback. Общий срок8s сохранён, latency считает только успешную попытку. Потоковый ответ ограничен1024 байт; env proxy отключён; redirect запрещён.
- Неудачный активный замер: unavailable/unknown и «Нет замера», без изменения runtime health или failover. Метрики tun_https/tun/tcp сохраняются отдельно.
- Контекст дополнительно удерживает actual active object/id; stale reply не публикуется после его замены.
- Независимое read-only ревью после возобновления: Critical/Important замечаний нет; worker ownership/release гарантии сохранены.
- PyInstaller exit0: dist/active-ping-fix/KROTTUN.exe, 44 134 445 bytes, version2.5.0.
- SHA256: 6b6d0ad20a9e38f607a9bfe9c2da44b7fbd510ad6f17872b42b08d0a328f481f.
- Archive/source equality: HTML/sing-box/Wintun, bytecode bridge/diagnostics/ping_service/proxy_model/version/main; multiprocessing hook и requireAdministrator подтверждены.
- GUI/EXE, реальная сеть и frozen helper runtime не запускались. Нативная причина timeout конкретного сервера не проверена. Защита/WFP/маршруты/Windows proxy не менялись; VM/IPv6/reboot acceptance остаётся открытой.
