# Варианты блока защиты KROTTUN

Только дизайн-превью, пользователь выбирает направление. Код приложения не менялся. Встроенный image_gen, референс — пользовательский скриншот блока защиты.

1. Компактная строка.
2. Двухуровневая панель (занимает больше высоты).
3. Сегментированный блок.

Слева включённое состояние, справа снятое. Кнопка снятия показана только при включённой защите; точные pending/blocked/unknown состояния должны оставаться отдельными при реализации. Прототип не обещает доказанной защиты от всех утечек.

Изображение: `01-comparison.png`.

## Промпт

```text
Use case: ui-mockup. Produce ONE crisp high-fidelity design comparison board with THREE alternative designs for ONLY the Windows protection status/action block inside an existing desktop app. Input image is the EXISTING BLOCK / color reference, not the whole app. Preserve its saturated dark royal-blue dotted KROTTUN background, white and pale-blue text, dark navy controls. Do not redesign the app, navigation, logs or logo. No terminal aesthetic here. Flat front view, landscape board about 1536x1024 with large highly readable Russian UI text.
Board composition: 3 horizontal numbered rows, 2 columns. Column headings outside UI blocks: 'Защита включена' and 'Защита снята'. Each row presents the SAME proposed block in its two real states. Six strips total, each around 650px wide, with a consistent royal-blue application background around it. Discreet external row labels '01  Компактная строка', '02  Двухуровневая панель', '03  Сегментированный блок'. These labels are comparison annotations, not part of app UI.
All six blocks are designed to live within a 520px-wide Windows application, with compact heights roughly 55–85px at actual scale; no oversized cards. Realistic Segoe UI/Inter typography, precise alignment, readable 13–15px text at intended scale, restrained 1px outlines, subtle dimension only, comfortable touch/click targets. Use thin authored outline shield icon, NOT emoji.
Shared text inside blocks: title 'Защита Windows'. Enabled state label 'Включена', subtle green/mint indicator, an explicitly secondary action button 'Снять защиту'. Disabled state label 'Снята', neutral gray-blue indicator; NO active disable button when already off. Instead small helper 'Включится при подключении прокси'. No button that claims to turn protection on independently of connecting; no invented settings/actions.
ROW1: very compact horizontal arrangement, shield + title and small status on left, modest dark-navy rounded rectangle button on right. Minimal containment, thin bottom keyline rather than a big surrounding card; excellent simple scanability. In off state the helper occupies action area.
ROW2: composed two-level navy inset panel with 10–12px radius, thin restrained blue border: first line shield + title left and little state badge right; second line in enabled state concise helper 'Блокировка прямого выхода' left and secondary outlined 'Снять защиту' right. Off state helper replaces action with no useless button. This row is slightly taller but still compact.
ROW3: sleek divided status rail, one cohesive dark-navy rounded rectangular strip with 2 unequal segments separated by one subtle vertical rule. Left compact shield, 'Защита Windows', state; right includes a small restrained 'Снять защиту' action when enabled, or calm helper when off. More instrument-like and structured than rows1/2, no huge pills or navigation tabs.
Keep enabled/off palette coherent, not neon. Navy #041743 / royal blue #082573 / pale blue #80b9ff / ivory white / muted mint #78dbb1. Disabled state should look neutral rather than alarming red. Enabled state should indicate feature state, NOT a promise of perfect anonymity. Do not use copy like 100% secure, no leaks guaranteed, encrypted all traffic, antivirus, VPN, or system firewall reset. No real IPs, credentials, traffic, charts, toggles with nonexistent behavior, surrounding full app, photographic desk or device mockup. Three alternatives must be visually distinguishable in hierarchy/containment, NOT merely recolors. A small footer annotation outside the UI may say 'Визуальные варианты · демосостояния'.
```

