# Блок защиты: выбран вариант 3

Пользователь: «да давай 3 вариант». Референс: design/protection-prototypes-2026-10-23/01-comparison.png, нижний ряд.

Scope: только #protectionStrip. Остальной синий интерфейс, терминальный лог, размер окна и backend защиты не меняются. Компактный navy segmented rail: SVG shield + заголовок/статус слева, вертикальный разделитель и действие/пояснение справа.

Состояния: unarmed — снята/нейтральный/подсказка включения при подключении; protected — включена/mint/снять защиту; blocked — интернет заблокирован/amber/снять защиту; connecting/switching — честный pending, без зелёного подтверждения; unknown/ошибка опроса — неопределённое состояние, восстановление доступно. Никаких обещаний абсолютной анонимности.

Действие использует только существующий release_protection, с busy-защитой от повторов и восстановлением кнопки при ошибке. Не добавлять независимый toggle, ослабление правил или запись настроек. Во время blocked/unknown нельзя спрятать восстановление.

Проверка: meaningful non-rendering state/action tests, JS syntax/unique IDs, full suite (база85), независимое source review. Browser/localHTML render запрещён ранее политикой, обходы и новые live networking тесты не выполняются. Поставка — свежий dist/protection/KROTTUN.exe после проверки архива.

Реализовано: scoped CSS/SVG, корректные состояния и busy/release. Опрос защиты и журнала независим: зависание журнала не замораживает статус, get_state после 3.5 секунды даёт unknown; поздние результаты игнорируются, RPC не накапливаются. Full suite 86 passed; независимое source review SAFE. Внешний вид проверен только по исходникам, без render/native GUI запуска.

Сборка dist/protection/KROTTUN.exe: 44,092,271 bytes; SHA256 99ff022721225b00a0a90e65058e09f91f6cad43fa1cd1fde2f575b6903ed218. Архив проверен: HTML/sing-box/Wintun идентичны исходным файлам, UI markers/core modules присутствуют, UAC manifest requireAdministrator.
