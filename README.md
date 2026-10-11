# 🐾 KROTTUN — L3 TUN Proxy Manager for Windows

<p align="center">
  <img src="gui/web/krottun_logo_128.png" alt="KROTTUN Logo" width="128" height="128" />
</p>

<p align="center">
  <strong>Высокоскоростное системное L3-туннелирование трафика Windows через SOCKS5 и HTTP/HTTPS прокси.</strong><br>
  Построено на базе ядра <strong>sing-box</strong>, драйвера <strong>Wintun</strong> и аппаратного интерфейса <strong>Microsoft Edge WebView2</strong>.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078D6?logo=windows" alt="Platform" />
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?logo=python" alt="Python" />
  <img src="https://img.shields.io/badge/Driver-Wintun%200.14-orange" alt="Wintun" />
  <img src="https://img.shields.io/badge/Core-sing--box%201.11-success" alt="sing-box" />
  <img src="https://img.shields.io/badge/UI-Edge%20WebView2-informational" alt="WebView2" />
  <img src="https://img.shields.io/badge/Security-DPAPI%20%2B%20SDDL%20Hardened-green" alt="Security" />
</p>

---

## ⚡ О проекте

**KROTTUN** перехватывает весь сетевой трафик операционной системы на 3-м сетевом уровне (IP-пакеты) с помощью виртуального сетевого адаптера Wintun и прозрачно маршрутизирует его через указанный SOCKS5 или HTTP прокси.

В отличие от стандартных системных прокси Windows (WinINet), которые игнорируются мессенджерами, консольными утилитами и играми:
* **Весь стек приложений** (браузеры, Telegram, Discord, Git, curl, Steam, игры) начинает работать через прокси без необходимости настраивать каждое приложение отдельно.
* **Никаких утечек DNS или IPv6**: встроенный резолвер перенаправляет все DNS-запросы в шифрованные DoH (Cloudflare / Google), а IPv6-утечки на dual-stack сетях блокируются.

---

## 🛡️ Безопасность и Архитектура

Проект спроектирован с упором на надежность уровня Enterprise и защищен от типовых векторов атак в Windows:

1. **Аппаратное шифрование профилей (DPAPI):**
   * Данные прокси и пароли шифруются через Win32 `CryptProtectData` с двухэтапной энтропией пользователя. В открытом виде пароли на диск **никогда не записываются**.
2. **Изоляция каталогов и защита от повышения привилегий (LPE):**
   * Все бинарные файлы и логи размещаются в защищенном системном каталоге `%ProgramData%\ProxyTUN\` с дескриптором безопасности `SDDL_SECURE` (`SYSTEM` и `Administrators` — Full Access; `Users` — только Read & Execute).
   * Пользовательские данные изолируются в `%ProgramData%\ProxyTUN\users\<SID>\` со строгим дескриптором `SDDL_PRIVATE` (без прав для других пользователей).
   * Автоматическая защита от символьных ссылок (reparse point / junction attacks) и автоматический карантин при компрометации каталогов.
3. **Безопасная передача конфигурации ядра:**
   * Конфигурация для `sing-box` передается исключительно через системный поток `stdin` в памяти процесса.
4. **Гарантированное завершение дочерних процессов:**
   * Процесс привязывается к **Windows Job Object** (`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`). При закрытии окна или аварийном падении все дочерние службы (`sing-box`) мгновенно и гарантированно выгружаются, не оставляя повисших адаптеров.
5. **Фиксация хэшей бинарников (Pinned SHA-256):**
   * Перед запуском `sing-box.exe` и `wintun.dll` сверяются по контрольным суммам SHA-256 непосредственно перед `Popen`, исключая Time-of-Check to Time-of-Use (TOCTOU) подмену.

---

## 🎨 Графический интерфейс

* Современный **Obsidian Dark Blue Glassmorphism** интерфейс на Microsoft Edge WebView2 (60 FPS без лагов и внешних веб-зависимостей).
* Интерактивная матрица континентов Земли в стиле Cybrix VPN.
* Анимированный тумблер включения/выключения туннеля с металлической фаской.
* Мониторинг входящего и исходящего трафика (Upload/Download) в реальном времени.
* Автоматическое определение текущего внешнего IP и страны выхода.
* Встроенный замер задержки (Ping) как для одного сервера, так и массово для всех добавленных узлов.

---

## 🚀 Быстрый старт

### Требования
* Windows 10 (версия 1809+) или Windows 11 (64-bit).
* Установленный компонент **Microsoft Edge WebView2 Runtime** (входит в стандартную поставку Windows 10/11).
* Права **Администратора** (требуются Windows для создания виртуального сетевого адаптера Wintun и настройки маршрутов).

---

### Запуск из исходного кода

1. Клонируйте репозиторий:
   ```bash
   git clone https://github.com/your-username/krottun.git
   cd krottun
   ```

2. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```

3. Запустите приложение с правами Администратора:
   ```bash
   python main.py
   # или используйте скрипт:
   run.bat
   ```

---

### Сборка автономного .exe (PyInstaller)

Для сборки одного независимого `.exe` файла со всеми зависимостями и иконкой:

```bash
pyinstaller KROTTUN.spec --noconfirm
```

Готовый файл появится в каталоге `dist\KROTTUN.exe`. Он содержит встроенный манифест администратора (`uac_admin=True`) и запускается в один клик.

---

## 📋 Форматы добавления прокси

KROTTUN поддерживает как одиночное добавление через форму, так и пакетный импорт списка прокси в любом из следующих форматов:

```text
# 1. IP:PORT:USER:PASS
192.0.2.1:1080:username:password

# 2. IP:PORT (без авторизации)
192.0.2.2:8080

# 3. SOCKS5 URL
socks5://username:password@192.0.2.3:1080

# 4. HTTP / HTTPS URL
http://username:password@192.0.2.4:8080
```

---

## 📁 Структура проекта

```text
krottun/
├── bin/
│   ├── sing-box.exe          # Сетевое ядро sing-box (64-bit)
│   └── wintun.dll            # Официальный драйвер Wintun
├── core/
│   ├── admin_utils.py        # Проверка и повышение привилегий UAC
│   ├── ip_service.py         # Определение внешнего IP и замер Ping
│   ├── paths.py              # Безопасные каталоги, ACL и проверка SHA-256
│   ├── proxy_model.py        # Модели ProxyItem и надежный парсер строк
│   ├── singbox_manager.py    # Маршрутизация sing-box, правила и stdin пайпы
│   ├── storage.py            # Хранилище с шифрованием Windows DPAPI
│   └── win_job.py            # Windows Job Object (гарантия завершения)
├── gui/
│   ├── app_webview.py        # Backend-мост Python <-> WebView2
│   └── web/
│       ├── app_icon.ico      # Многослойная Windows-иконка
│       └── index.html        # Glassmorphic UI (HTML, CSS, JS, SVG-карта)
├── KROTTUN.spec              # Спецификация сборки PyInstaller
├── main.py                   # Точка входа в приложение
├── proxies.example.txt       # Примеры синтаксиса для импорта прокси
├── requirements.txt          # Python зависимости
├── run.bat                   # Скрипт быстрого запуска с авто-UAC
└── README.md                 # Документация проекта
```

---

## 📄 Лицензия

Проект распространяется под лицензией **MIT**. Подробности в файле `LICENSE`.
