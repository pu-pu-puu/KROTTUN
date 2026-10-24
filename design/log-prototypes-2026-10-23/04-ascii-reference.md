# ASCII Terminal — прототип по референсу

Визуальный макет, не реализация. Код KROTTUN не изменён. Данные на изображении демонстрационные.

Изображение: `04-ascii-reference.png`.
Источник стиля: предоставленный пользователем `5frdbvq6b0dh1.png`.
Режим: встроенный image_gen, reference image; чёрный фон, ASCII-рамки, пиксельный KROTTUN, лайм/циан.

## Промпт

```text
Use case: ui-mockup. Asset: ONE polished visual prototype of the KROTTUN Windows application's CONNECTION LOG screen, landscape around 1500x1000, straight-on crisp screenshot, whole screen visible.
Input image role: STYLE REFERENCE ONLY. Adapt its pure-black terminal, lime/cyan bitmap lettering, ASCII box borders and typographic rhythm. Replace all retUI content with KROTTUN's real proxy connection-log interface; this is NOT a promotional landing page and contains no framework installation commands.
Visual direction: authentic sophisticated ASCII/TUI, pitch-black #000000, bright lime #91ef63, electric cyan #21d3e6, warm-white #e2e4dc, muted gray #6e7a72. Fine dashed character borders, + corners and box-drawing separators, monospace readable typography, tiny square cursor. No rounded cards, glass, gradients, 3D, blur, Matrix rain, heavy bloom or charts.
Composition: outer ASCII rectangular frame with small centered title KROTTUN / CONNECTIONS and tiny [-] [□] [×] controls right. Inside near top a compact beautiful bitmap/pixel-block wordmark KROTTUN, spelled K R O T T U N; KROT in lime, TUN in cyan. This wordmark is only 12–16% of screen height, not a giant hero. Beneath it a slim horizontal rule and bracket-style navigation: [ Главная ] [ Серверы ] [ Соединения ]; active Соединения cyan.
Main content occupies most of screen. Header 'Журнал соединений' in lime; one clean filter input drawn as a terminal prompt '> фильтр по сайту или программе...' with thin dashed lime outline; controls '[ II Пауза ]' and '[ Очистить ]' at right. A full-width ASCII-framed log viewport below, very readable fixed column alignment, headings 'Время', 'Программа', 'Сайт', 'Протокол', 'Маршрут'. Website/domain is the visual focus, bright cyan. 8 realistically spaced demo rows, timestamps never wrap: 17:22:31 chrome.exe github.com TLS EE; 17:22:33 Code.exe api.github.com TLS EE; 17:22:35 chrome.exe example.com TLS EE; 17:22:37 Telegram.exe cloudflare.com TLS US; 17:22:39 chrome.exe github.com HTTP EE; 17:22:41 Code.exe example.com TLS US; 17:22:43 chrome.exe api.github.com TLS EE; 17:22:45 chrome.exe cloudflare.com TLS EE. Use white time/process, muted lime protocols, cyan domains. A tiny lime '>' gutter marks selected github.com row, with barely tinted background, not a large solid pill. Do not display fake request bodies or full HTTPS paths.
Below rows a very compact dashed-outline selected-connection strip: 'Выбрано: github.com' cyan, 'chrome.exe · TLS · EE · Зафиксировано' white. Terminal footer within the outer border: lime status dot plus 'Защита: ВКЛ', then '8 записей', with small gray 'Демоданные · домены без расшифровки HTTPS'. All simulated events clearly demo. Balanced whitespace, technically intentional character-grid precision, high contrast, comfortably readable text. Faithful to the supplied retro ASCII reference but composed as a practical premium app log viewer. No retUI name, no Go code, no installation commands, no real IPs, credentials, unsafe security guarantees or marketing copy.
```
