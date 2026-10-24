# 03 — Диагностика одной кнопкой и доставка

**Требования:** R01, R04
**Зависит от:** 02
**Зона:** `core/diagnostics.py` · `gui/app_webview.py` · `gui/web/index.html` · `tests/test_diagnostics.py` · `prototypes/proxy-controls` · `README.md`
**Волна:** 3
**Ревью:** да — защита сети и lifecycle дочернего процесса
**Модель:** сильная

## Что должно заработать
Кнопка запускает ограниченную диагностику активного подключения с отдельными строками прокси/DNS/HTTPS/IP/system proxy и честными пропусками. Проверяется весь новый UI в production HTML через изолированный browser с fake bridge.

## Из брифа, дословно
> «Диагностика одной кнопкой»
> «через скил автопилот»

## Разделы спецификации
Диагностика (R01), Доставка (R04), Решения по реализации, Вне рамок. interfaces.md и notes.md первыми. Требования предыдущих двух тасков используются для общего UI verification.

## Критерии приёмки
- [ ] Одна кнопка, 5 отдельных результатов, progress/final/error/skipped, объяснения и рекомендации на русском; IP валидируется; нет raw errors/credentials.
- [ ] Healthy protected TUN проверяется по OS route; unarmed/IDLE проверяет выбранный прокси через explicit proxy transport без direct fallback и DNS DoH через него; blocked/unknown/переходы skipped без внешних сетевых запросов. Не меняются WFP, TUN или системный прокси.
- [ ] Один killable spawn worker, <=12s wall deadline, Job-bound before request gate, retain until confirmed exit; нет накопления при зависании; lifecycle смена/release/закрытие отменяет и не публикует stale результаты.
- [ ] HTTPS trust_env=False, redirects=False, bounded reads, фиксированные targets, DNS в child; системный прокси только чтение и честное unknown при ошибке.
- [ ] Polling UI single-flight/bounded timeout, stop on modal close, repeated starts/errors handled; пять строк и диалоги edit/reserve помещаются в 520×760, прокрутка внутри.
- [ ] Новые offline tests fail before implementation then pass; полный suite зелёный. Существующие map/mesh/protection/log invariants не сломаны.
- [ ] Изолированный browser production HTML regression edit/password/reserve/diagnosis/XSS и screenshots в prototypes/proxy-controls; README документирует новые функции и ограничения. EXE packaging выполняет оркестратор после review.
