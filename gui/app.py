import os
import sys
import time
import threading
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
from typing import List, Optional, Tuple
import winreg

try:
    import psutil
except ImportError:
    psutil = None

from PIL import Image, ImageDraw

from core.proxy_model import ProxyItem, parse_bulk_proxies, parse_proxy_line
from core.singbox_manager import SingBoxManager
from core.ip_service import get_current_system_ip, test_proxy, quick_ping_proxy
from core.admin_utils import is_admin, run_as_admin
from core.storage import save_proxies, load_proxies
from gui.clipboard_helper import make_pasteable, paste_to_widget


def ensure_localhost_bypass():
    """Гарантирует, что Windows и Electron не пытаются проксировать localhost."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
            0,
            winreg.KEY_ALL_ACCESS
        )
        try:
            val, _ = winreg.QueryValueEx(key, "ProxyOverride")
        except FileNotFoundError:
            val = ""

        if "<local>" not in val or "127.*" not in val:
            new_val = f"<local>;localhost;127.*;10.*;192.168.*;{val}".strip(";")
            winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, new_val)
        winreg.CloseKey(key)
    except Exception:
        pass


# Настройка темы CustomTkinter
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Константы палитры Cybrix VPN
COLOR_BG = "#070d1a"          # Глубокий королевский сапфировый фон
COLOR_CARD = "#0e1f44"        # Полупрозрачное матовое стекло блоков
COLOR_BORDER = "#1e3d7a"      # Тонкий контур блоков
COLOR_ACCENT = "#1560d2"      # Электрический синий Cybrix
COLOR_ACCENT_HOVER = "#1b6cf0"
COLOR_TOGGLE_ON = "#8270f8"   # Лавандовый трек активного переключателя
COLOR_TOGGLE_ON_HOVER = "#9484fa"
COLOR_TOGGLE_OFF = "#17274d"  # Темный трек выключенного переключателя
COLOR_TOGGLE_OFF_HOVER = "#1f3363"
COLOR_GREEN = "#00c566"       # Изумрудный статус-зеленый
COLOR_TEXT_MUTED = "#8ba2d4"  # Светло-синий приглушенный текст


def generate_toggle_image(is_active: bool = False, is_connecting: bool = False, width: int = 150, height: int = 72) -> Image.Image:
    """Генерирует супер-сглаженную векторную текстуру переключателя Cybrix VPN с 3x суперсэмплингом."""
    scale = 3
    w, h = width * scale, height * scale
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if is_active:
        track_color = (130, 112, 248, 255)
        border_color = (165, 150, 255, 255)
    elif is_connecting:
        track_color = (25, 45, 90, 255)
        border_color = (70, 110, 200, 255)
    else:
        track_color = (18, 30, 60, 255)
        border_color = (35, 55, 100, 255)

    r = h // 2
    draw.rounded_rectangle([3, 3, w - 4, h - 4], radius=r, fill=track_color, outline=border_color, width=4)

    knob_diam = h - 24
    knob_r = knob_diam // 2
    if is_active:
        cx = w - 12 - knob_r
        knob_color = (246, 244, 255, 255)
        icon_color = (40, 25, 95, 255)
        knob_border = (255, 255, 255, 255)
    elif is_connecting:
        cx = w // 2
        knob_color = (100, 140, 230, 255)
        icon_color = (15, 25, 60, 255)
        knob_border = (160, 190, 255, 255)
    else:
        cx = 12 + knob_r
        knob_color = (60, 78, 108, 255)
        icon_color = (150, 172, 205, 255)
        knob_border = (90, 112, 145, 255)

    cy = h // 2
    draw.ellipse([cx - knob_r, cy - knob_r, cx + knob_r, cy + knob_r], fill=knob_color, outline=knob_border, width=4)

    ir = int(knob_r * 0.52)
    draw.arc([cx - ir, cy - ir + 2, cx + ir, cy + ir + 2], start=315, end=225, fill=icon_color, width=8)
    draw.line([cx, cy - ir - 3, cx, cy], fill=icon_color, width=8)

    return img.resize((width, height), Image.Resampling.LANCZOS)


class ProxyTunApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ensure_localhost_bypass()

        self.title("ProxyTUN — L3 TUN Proxy Manager")
        self.geometry("520x760")
        self.minsize(480, 720)
        self.configure(fg_color=COLOR_BG)

        self.is_administrator = is_admin()
        self.singbox_manager = SingBoxManager()
        self.proxies: List[ProxyItem] = load_proxies()
        self.selected_proxy_id: Optional[str] = self.proxies[0].id if self.proxies else None

        self.current_ip_info = {"ip": "Загрузка...", "country": "", "city": "", "isp": ""}
        self.is_checking_ip = False
        self.is_busy = False
        self.is_checking_pings = False

        # Таймер сессии подключения и мониторинг скорости
        self.connected_time_start: Optional[float] = None
        self.last_net_bytes: Optional[Tuple[int, int]] = None
        self.last_net_time: Optional[float] = None
        # Генерация сглаженных векторных текстур переключателя Cybrix
        _raw_off = generate_toggle_image(is_active=False)
        _raw_on = generate_toggle_image(is_active=True)
        _raw_wait = generate_toggle_image(is_connecting=True)

        self.img_toggle_off = ctk.CTkImage(light_image=_raw_off, dark_image=_raw_off, size=(150, 72))
        self.img_toggle_on = ctk.CTkImage(light_image=_raw_on, dark_image=_raw_on, size=(150, 72))
        self.img_toggle_wait = ctk.CTkImage(light_image=_raw_wait, dark_image=_raw_wait, size=(150, 72))

        self._build_ui()

        # Обработка закрытия окна
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Фоновая проверка текущего IP
        self.refresh_system_ip()

        # Фоновый мониторинг процесса и телеметрии
        self.after(2000, self._check_process_liveness)
        self.after(1000, self._telemetry_tick)

    def _build_ui(self):
        # 1. Верхний бар: Логотип и Внешний IP
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=18, pady=(14, 8))

        # Логотип Cybrix-стиль
        logo_box = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        logo_box.pack(side="left")

        lbl_logo_icon = ctk.CTkLabel(
            logo_box,
            text="▲",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#1560d2",
            text_color="white",
            corner_radius=8,
            width=30,
            height=30
        )
        lbl_logo_icon.pack(side="left", padx=(0, 8))

        lbl_logo_text = ctk.CTkLabel(
            logo_box,
            text="ProxyTUN",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color="white"
        )
        lbl_logo_text.pack(side="left")

        # Правая плашка с внешним IP
        self.ip_pill = ctk.CTkButton(
            self.header_frame,
            text="IP: Определение...",
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            fg_color="#0a1e50",
            hover_color="#122a6b",
            text_color="white",
            border_color="#234d9e",
            border_width=1,
            corner_radius=14,
            height=30,
            command=self.refresh_system_ip
        )
        self.ip_pill.pack(side="right")

        # 2. Навигационные вкладки Cybrix
        self.nav_frame = ctk.CTkFrame(self, fg_color="#0c1730", corner_radius=14, border_color="#1b2e54", border_width=1)
        self.nav_frame.pack(fill="x", padx=18, pady=(4, 10))

        self.btn_nav_home = ctk.CTkButton(
            self.nav_frame,
            text="Главная",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            corner_radius=10,
            height=32,
            command=lambda: self.switch_view("home")
        )
        self.btn_nav_home.pack(side="left", fill="x", expand=True, padx=3, pady=3)

        self.btn_nav_servers = ctk.CTkButton(
            self.nav_frame,
            text=f"Серверы ({len(self.proxies)})",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="transparent",
            hover_color="#13274f",
            text_color=COLOR_TEXT_MUTED,
            corner_radius=10,
            height=32,
            command=lambda: self.switch_view("servers")
        )
        self.btn_nav_servers.pack(side="left", fill="x", expand=True, padx=3, pady=3)

        self.btn_nav_settings = ctk.CTkButton(
            self.nav_frame,
            text="Инфо / UAC",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="transparent",
            hover_color="#13274f",
            text_color=COLOR_TEXT_MUTED,
            corner_radius=10,
            height=32,
            command=lambda: self.switch_view("settings")
        )
        self.btn_nav_settings.pack(side="left", fill="x", expand=True, padx=3, pady=3)

        # 3. Контейнер основных видов
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True, padx=18, pady=(0, 10))

        # Создаем экраны
        self._build_home_view()
        self._build_servers_view()
        self._build_settings_view()

        # Показываем домашний экран по умолчанию
        self.switch_view("home")

    def switch_view(self, view_name: str):
        self.view_home.pack_forget()
        self.view_servers.pack_forget()
        self.view_settings.pack_forget()

        # Сброс подсветки кнопок навигации
        for btn in [self.btn_nav_home, self.btn_nav_servers, self.btn_nav_settings]:
            btn.configure(fg_color="transparent", text_color=COLOR_TEXT_MUTED)

        if view_name == "home":
            self.view_home.pack(fill="both", expand=True)
            self.btn_nav_home.configure(fg_color=COLOR_ACCENT, text_color="white")
            self.update_selected_server_card()
        elif view_name == "servers":
            self.view_servers.pack(fill="both", expand=True)
            self.btn_nav_servers.configure(fg_color=COLOR_ACCENT, text_color="white")
            self.update_proxy_list_ui()
        elif view_name == "settings":
            self.view_settings.pack(fill="both", expand=True)
            self.btn_nav_settings.configure(fg_color=COLOR_ACCENT, text_color="white")

    # ================= 1. ЭКРАН ГЛАВНАЯ (CYBRIX HOME) =================
    def _build_home_view(self):
        self.view_home = ctk.CTkFrame(self.container, fg_color="transparent")

        # 1. Заголовок таймера подключения
        lbl_dur_title = ctk.CTkLabel(
            self.view_home,
            text="Your Connection Duration",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_MUTED
        )
        lbl_dur_title.pack(pady=(6, 1))

        self.lbl_timer = ctk.CTkLabel(
            self.view_home,
            text="00:00:00",
            font=ctk.CTkFont(family="Consolas", size=36, weight="bold"),
            text_color="white"
        )
        self.lbl_timer.pack(pady=(0, 10))

        # 2. Фирменный переключатель Cybrix (Pill Toggle)
        toggle_box = ctk.CTkFrame(self.view_home, fg_color="transparent")
        toggle_box.pack(pady=4)

        self.btn_toggle_tun = ctk.CTkButton(
            toggle_box,
            text="",
            image=self.img_toggle_off,
            fg_color="transparent",
            hover=False,
            corner_radius=36,
            width=150,
            height=72,
            cursor="hand2",
            command=self.toggle_tun
        )
        self.btn_toggle_tun.pack()

        # 3. Минималистичный статус-бейдж под переключателем (запрос пользователя)
        self.badge_box = ctk.CTkFrame(self.view_home, fg_color="transparent")
        self.badge_box.pack(pady=(12, 10))

        self.lbl_status_pill = ctk.CTkLabel(
            self.badge_box,
            text="✕ Disconnected",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#131d30",
            text_color="#7e95c4",
            corner_radius=14,
            width=130,
            height=28
        )
        self.lbl_status_pill.pack()

        # 4. Телеметрия Upload / Download (Cybrix Cards)
        telemetry_frame = ctk.CTkFrame(self.view_home, fg_color="transparent")
        telemetry_frame.pack(fill="x", pady=6)

        # Upload Card
        card_up = ctk.CTkFrame(telemetry_frame, fg_color=COLOR_CARD, corner_radius=16, border_color=COLOR_BORDER, border_width=1)
        card_up.pack(side="left", fill="both", expand=True, padx=(0, 6), ipady=4)

        up_header = ctk.CTkFrame(card_up, fg_color="transparent")
        up_header.pack(fill="x", padx=12, pady=(8, 2))
        ctk.CTkLabel(up_header, text="Upload", font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_MUTED).pack(side="left")
        ctk.CTkLabel(up_header, text="↑", font=ctk.CTkFont(size=12, weight="bold"), fg_color="#3c1d68", text_color="#c084fc", corner_radius=10, width=22, height=22).pack(side="right")

        self.lbl_speed_up = ctk.CTkLabel(card_up, text="0.0 Mb/s", font=ctk.CTkFont(family="Consolas", size=18, weight="bold"), text_color="white")
        self.lbl_speed_up.pack(anchor="w", padx=12, pady=(0, 8))

        # Download Card
        card_down = ctk.CTkFrame(telemetry_frame, fg_color=COLOR_CARD, corner_radius=16, border_color=COLOR_BORDER, border_width=1)
        card_down.pack(side="right", fill="both", expand=True, padx=(6, 0), ipady=4)

        down_header = ctk.CTkFrame(card_down, fg_color="transparent")
        down_header.pack(fill="x", padx=12, pady=(8, 2))
        ctk.CTkLabel(down_header, text="Download", font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_MUTED).pack(side="left")
        ctk.CTkLabel(down_header, text="↓", font=ctk.CTkFont(size=12, weight="bold"), fg_color="#0e345e", text_color="#38bdf8", corner_radius=10, width=22, height=22).pack(side="right")

        self.lbl_speed_down = ctk.CTkLabel(card_down, text="0.0 Mb/s", font=ctk.CTkFont(family="Consolas", size=18, weight="bold"), text_color="white")
        self.lbl_speed_down.pack(anchor="w", padx=12, pady=(0, 8))

        # 5. ТОЧНЫЙ БЛОК ВЫБРАННОГО СЕРВЕРА (по скриншоту пользователя)
        self.server_card = ctk.CTkFrame(self.view_home, fg_color=COLOR_CARD, corner_radius=18, border_color=COLOR_BORDER, border_width=1)
        self.server_card.pack(fill="x", pady=(10, 4))

        # Верхний ряд карточки: Код страны US | Название и HTTP | Хост | Бейдж пинга 38 ms
        top_row = ctk.CTkFrame(self.server_card, fg_color="transparent")
        top_row.pack(fill="x", padx=14, pady=(12, 8))

        # Левая колонка с кодом страны
        self.lbl_srv_code = ctk.CTkLabel(
            top_row,
            text="US",
            font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"),
            text_color="white",
            width=42
        )
        self.lbl_srv_code.pack(side="left", padx=(0, 10))

        # Средняя колонка с именем и хостом
        info_col = ctk.CTkFrame(top_row, fg_color="transparent")
        info_col.pack(side="left", fill="both", expand=True)

        name_badge_row = ctk.CTkFrame(info_col, fg_color="transparent")
        name_badge_row.pack(anchor="w")

        self.lbl_srv_name = ctk.CTkLabel(
            name_badge_row,
            text="USA (Вашингтон)",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="white"
        )
        self.lbl_srv_name.pack(side="left", padx=(0, 6))

        self.lbl_srv_proto = ctk.CTkLabel(
            name_badge_row,
            text="HTTP",
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color="#3d2b0e",
            text_color="#f59e0b",
            corner_radius=4,
            width=42,
            height=18
        )
        self.lbl_srv_proto.pack(side="left")

        self.lbl_srv_host = ctk.CTkLabel(
            info_col,
            text="192.0.2.1:1080",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=COLOR_TEXT_MUTED
        )
        self.lbl_srv_host.pack(anchor="w", pady=(2, 0))

        # Правая колонка: зеленый бейдж пинга
        self.lbl_srv_ping = ctk.CTkLabel(
            top_row,
            text="38 ms",
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            fg_color="#042416",
            text_color=COLOR_GREEN,
            corner_radius=8,
            width=70,
            height=26
        )
        self.lbl_srv_ping.pack(side="right")

        # Разделительная линия
        sep = ctk.CTkFrame(self.server_card, fg_color="#182d54", height=1)
        sep.pack(fill="x", padx=14, pady=4)

        # Нижний ряд карточки: Две кнопки действия
        btn_row = ctk.CTkFrame(self.server_card, fg_color="transparent")
        btn_row.pack(fill="x", padx=14, pady=(6, 12))

        self.btn_change_srv = ctk.CTkButton(
            btn_row,
            text="⇄ Сменить сервер",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#0c1f47",
            hover_color="#132c63",
            text_color="#60a5fa",
            border_color="#2554a8",
            border_width=1,
            corner_radius=12,
            height=34,
            command=lambda: self.switch_view("servers")
        )
        self.btn_change_srv.pack(side="left", fill="x", expand=True, padx=(0, 5))

        self.btn_ping_one = ctk.CTkButton(
            btn_row,
            text="⚡ Проверить пинг",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            text_color="white",
            corner_radius=12,
            height=34,
            command=self.run_ping_check_selected
        )
        self.btn_ping_one.pack(side="right", fill="x", expand=True, padx=(5, 0))

    # ================= 2. ЭКРАН СЕРВЕРОВ (CYBRIX SERVERS) =================
    def _build_servers_view(self):
        self.view_servers = ctk.CTkFrame(self.container, fg_color="transparent")

        # Панель действий со списком серверов
        top_bar = ctk.CTkFrame(self.view_servers, fg_color="transparent")
        top_bar.pack(fill="x", pady=(2, 8))

        self.lbl_servers_count = ctk.CTkLabel(
            top_bar,
            text=f"Выбор узла ({len(self.proxies)})",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="white"
        )
        self.lbl_servers_count.pack(side="left")

        btn_box = ctk.CTkFrame(top_bar, fg_color="transparent")
        btn_box.pack(side="right")

        self.btn_ping_all = ctk.CTkButton(
            btn_box,
            text="⚡ Замерить все",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            corner_radius=10,
            width=105,
            height=28,
            command=self.run_ping_check_all
        )
        self.btn_ping_all.pack(side="left", padx=(0, 5))

        btn_add = ctk.CTkButton(
            btn_box,
            text="+ Добавить",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#0e2352",
            hover_color="#15326f",
            text_color="white",
            corner_radius=10,
            width=85,
            height=28,
            command=self.open_add_dialog
        )
        btn_add.pack(side="left", padx=(0, 5))

        btn_import = ctk.CTkButton(
            btn_box,
            text="📥 Импорт",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#0e2352",
            hover_color="#15326f",
            text_color="white",
            corner_radius=10,
            width=80,
            height=28,
            command=self.open_import_dialog
        )
        btn_import.pack(side="left")

        # Прокручиваемый список карточек серверов
        self.scroll_servers = ctk.CTkScrollableFrame(
            self.view_servers,
            fg_color="transparent",
            corner_radius=12,
            scrollbar_fg_color="transparent",
            scrollbar_button_color="#14264d",
            scrollbar_button_hover_color="#234280"
        )
        self.scroll_servers.pack(fill="both", expand=True)

        self.update_proxy_list_ui()

    # ================= 3. ЭКРАН НАСТРОЕК / UAC =================
    def _build_settings_view(self):
        self.view_settings = ctk.CTkFrame(self.container, fg_color="transparent")

        card_uac = ctk.CTkFrame(self.view_settings, fg_color=COLOR_CARD, corner_radius=16, border_color=COLOR_BORDER, border_width=1)
        card_uac.pack(fill="x", pady=8, padx=4)

        ctk.CTkLabel(card_uac, text="Статус прав Администратора", font=ctk.CTkFont(size=13, weight="bold"), text_color="white").pack(anchor="w", padx=14, pady=(12, 4))
        
        status_admin_text = "🛡️ Приложение запущено с правами Администратора (TUN готов)" if self.is_administrator else "⚠️ Требуются права Администратора для TUN"
        status_admin_color = COLOR_GREEN if self.is_administrator else "#f59e0b"
        ctk.CTkLabel(card_uac, text=status_admin_text, font=ctk.CTkFont(size=12), text_color=status_admin_color).pack(anchor="w", padx=14, pady=(0, 10))

        if not self.is_administrator:
            btn_elevate = ctk.CTkButton(card_uac, text="Перезапустить от Администратора (UAC)", fg_color="#f59e0b", hover_color="#d97706", text_color="#111827", font=ctk.CTkFont(weight="bold"), command=self.request_elevation)
            btn_elevate.pack(padx=14, pady=(0, 12))

        # Карточка очистки маршрутов
        card_tools = ctk.CTkFrame(self.view_settings, fg_color=COLOR_CARD, corner_radius=16, border_color=COLOR_BORDER, border_width=1)
        card_tools.pack(fill="x", pady=8, padx=4)

        ctk.CTkLabel(card_tools, text="Системные утилиты", font=ctk.CTkFont(size=13, weight="bold"), text_color="white").pack(anchor="w", padx=14, pady=(12, 4))

        tool_box = ctk.CTkFrame(card_tools, fg_color="transparent")
        tool_box.pack(fill="x", padx=14, pady=(0, 14))

        btn_flush = ctk.CTkButton(tool_box, text="Сбросить кэш DNS (flushdns)", fg_color="#102554", hover_color="#19377a", text_color="white", command=self.flush_system_dns)
        btn_flush.pack(side="left", fill="x", expand=True, padx=(0, 5))

        btn_clean_routes = ctk.CTkButton(tool_box, text="Очистить маршруты Wintun", fg_color="#102554", hover_color="#19377a", text_color="white", command=self.clean_routes_action)
        btn_clean_routes.pack(side="right", fill="x", expand=True, padx=(5, 0))

    def flush_system_dns(self):
        self.singbox_manager.flush_dns()
        messagebox.showinfo("DNS", "Системный кэш DNS Windows успешно сброшен.")

    def clean_routes_action(self):
        self.singbox_manager.clean_stale_routes()
        self.singbox_manager.clean_phantom_adapters()
        messagebox.showinfo("Маршруты", "Остаточные маршруты и фантомные адаптеры Wintun очищены.")

    def request_elevation(self):
        run_as_admin()

    # ================= ЛОГИКА ТЕЛЕМЕТРИИ И ТАЙМЕРА =================
    def _telemetry_tick(self):
        # 1. Обновление таймера подключения
        if self.singbox_manager.is_running() and self.connected_time_start:
            elapsed = int(time.time() - self.connected_time_start)
            hrs = String = f"{elapsed // 3600:02d}"
            mins = f"{(elapsed % 3600) // 60:02d}"
            secs = f"{elapsed % 60:02d}"
            self.lbl_timer.configure(text=f"{hrs}:{mins}:{secs}")
        else:
            self.lbl_timer.configure(text="00:00:00")

        # 2. Обновление скорости Upload / Download
        if psutil is not None:
            try:
                now_net = psutil.net_io_counters()
                now_time = time.time()
                if self.last_net_bytes and self.last_net_time:
                    dt = now_time - self.last_net_time
                    if dt > 0.4:
                        sent_bytes = now_net.bytes_sent - self.last_net_bytes[0]
                        recv_bytes = now_net.bytes_recv - self.last_net_bytes[1]
                        
                        # Скорость в Mb/s
                        up_mbps = (sent_bytes * 8) / (dt * 1_000_000)
                        down_mbps = (recv_bytes * 8) / (dt * 1_000_000)

                        if self.singbox_manager.is_running():
                            self.lbl_speed_up.configure(text=f"{up_mbps:.1f} Mb/s")
                            self.lbl_speed_down.configure(text=f"{down_mbps:.1f} Mb/s")
                        else:
                            self.lbl_speed_up.configure(text="0.0 Mb/s")
                            self.lbl_speed_down.configure(text="0.0 Mb/s")

                self.last_net_bytes = (now_net.bytes_sent, now_net.bytes_recv)
                self.last_net_time = now_time
            except Exception:
                pass

        self.after(1000, self._telemetry_tick)

    # ================= УПРАВЛЕНИЕ TUN И ПОДКЛЮЧЕНИЕМ =================
    def toggle_tun(self):
        if self.is_busy:
            return
        if self.singbox_manager.is_running():
            self.disconnect_tun()
        else:
            sel = self.get_selected_proxy()
            if not sel:
                messagebox.showwarning("Внимание", "Выберите прокси из списка перед подключением.")
                return
            self.connect_proxy(sel)

    def connect_proxy(self, proxy: ProxyItem):
        if self.is_busy:
            return
        if not self.is_administrator:
            msg = ("Для работы в режиме TUN требуются права Администратора.\n\n"
                   "Перезапустить приложение с повышением прав?")
            if messagebox.askyesno("Требуются права Администратора", msg):
                self.request_elevation()
            return

        self.is_busy = True
        self.btn_toggle_tun.configure(image=self.img_toggle_wait, state="disabled")
        self.lbl_status_pill.configure(
            text="⋯ Connecting...",
            text_color="#60a5fa",
            fg_color="#14264d"
        )

        def _task():
            # Защитная проверка доступности прокси перед стартом
            ok, lat, country, city = test_proxy(proxy, timeout=4.5)
            if not ok:
                def _ask_proceed():
                    msg = (f"Прокси {proxy.host}:{proxy.port} не ответил на проверочный запрос.\n\n"
                           f"Если включить TUN сейчас, интернет на ПК может временно пропасть!\n\n"
                           f"Все равно попытаться подключить?")
                    if messagebox.askyesno("Предупреждение", msg):
                        self._do_start_singbox(proxy)
                    else:
                        self.is_busy = False
                        self.btn_toggle_tun.configure(
                            image=self.img_toggle_off,
                            state="normal"
                        )
                        self.lbl_status_pill.configure(
                            text="✕ Disconnected",
                            text_color="#7e95c4",
                            fg_color="#131d30"
                        )
                self.after(0, _ask_proceed)
                return

            self._do_start_singbox(proxy)

        threading.Thread(target=_task, daemon=True).start()

    def _do_start_singbox(self, proxy: ProxyItem):
        self.after(0, lambda: self.lbl_status_pill.configure(text="⋯ Starting Wintun..."))
        try:
            self.singbox_manager.start(proxy)
            self.after(0, lambda p=proxy: self._on_connect_success(p))
        except Exception as e:
            err_str = str(e)
            self.after(0, lambda msg=err_str: self._on_connect_fail(msg))

    def _on_connect_success(self, proxy: ProxyItem):
        self.is_busy = False
        self.connected_time_start = time.time()
        
        # Переключатель в активное состояние
        self.btn_toggle_tun.configure(
            image=self.img_toggle_on,
            state="normal"
        )
        
        # Минималистичный зеленый бейдж статуса
        self.lbl_status_pill.configure(
            text="✓ Connected",
            text_color=COLOR_GREEN,
            fg_color="#042416"
        )

        self.update_selected_server_card()
        self.update_proxy_list_ui()
        self.after(1500, self.refresh_system_ip)

    def _on_connect_fail(self, error_message: str):
        self.is_busy = False
        self.connected_time_start = None
        self.singbox_manager.active_proxy = None
        
        self.btn_toggle_tun.configure(
            image=self.img_toggle_off,
            state="normal"
        )
        self.lbl_status_pill.configure(
            text="✕ Disconnected",
            text_color="#7e95c4",
            fg_color="#131d30"
        )

        messagebox.showerror("Ошибка TUN подключения", error_message)
        self.update_selected_server_card()
        self.update_proxy_list_ui()

    def disconnect_tun(self):
        if self.is_busy:
            return
        self.is_busy = True
        self.btn_toggle_tun.configure(image=self.img_toggle_wait, state="disabled")
        self.lbl_status_pill.configure(text="⋯ Disconnecting...", text_color="#60a5fa", fg_color="#14264d")

        def _task():
            self.singbox_manager.stop()
            self.after(0, self._on_disconnect_done)

        threading.Thread(target=_task, daemon=True).start()

    def _on_disconnect_done(self):
        self.is_busy = False
        self.connected_time_start = None
        self.singbox_manager.active_proxy = None

        self.btn_toggle_tun.configure(
            image=self.img_toggle_off,
            state="normal"
        )
        self.lbl_status_pill.configure(
            text="✕ Disconnected",
            text_color="#7e95c4",
            fg_color="#131d30"
        )

        self.update_selected_server_card()
        self.update_proxy_list_ui()
        self.after(1000, self.refresh_system_ip)

    def _check_process_liveness(self):
        if not self.is_busy and self.singbox_manager.active_proxy and not self.singbox_manager.is_running():
            self.singbox_manager.active_proxy = None
            self._on_disconnect_done()
            self.lbl_status_pill.configure(text="✕ Disconnected", text_color="#ef4444", fg_color="#2b1111")
        self.after(2000, self._check_process_liveness)

    # ================= IP И ПИНГ =================
    def refresh_system_ip(self):
        if self.is_checking_ip:
            return
        self.is_checking_ip = True
        self.ip_pill.configure(text="IP: Проверка...")

        def _task():
            data = get_current_system_ip()
            self.current_ip_info = data
            self.is_checking_ip = False

            country_code = (data.get("country_code") or "").upper().strip()
            if not country_code:
                c = (data.get("country") or "").lower().strip()
                if "russia" in c or "россия" in c or c == "ru":
                    country_code = "RU"
                elif "united states" in c or "usa" in c or c == "us":
                    country_code = "US"
                elif "estonia" in c or c == "ee":
                    country_code = "EE"
                elif "germany" in c or c == "de":
                    country_code = "DE"
                elif "netherlands" in c or c == "nl":
                    country_code = "NL"
                elif "united kingdom" in c or "great britain" in c or c in ("uk", "gb"):
                    country_code = "GB"

            ip_str = data.get("ip", "Unknown")
            if country_code:
                text = f"IP: {ip_str}  [{country_code}]"
            else:
                text = f"IP: {ip_str}"

            self.after(0, lambda: self.ip_pill.configure(text=text))

        threading.Thread(target=_task, daemon=True).start()

    def run_ping_check_selected(self):
        sel = self.get_selected_proxy()
        if not sel:
            return
        self.lbl_srv_ping.configure(text="⏳ ...")

        def _task():
            lat = quick_ping_proxy(sel)
            def _ui():
                if lat is not None:
                    self.lbl_srv_ping.configure(text=f"{lat} ms", text_color=COLOR_GREEN)
                else:
                    self.lbl_srv_ping.configure(text="Таймаут", text_color="#ef4444")
                save_proxies(self.proxies)
                self.update_proxy_list_ui()
            self.after(0, _ui)

        threading.Thread(target=_task, daemon=True).start()

    def run_ping_check_all(self):
        if self.is_checking_pings or not self.proxies:
            return
        self.is_checking_pings = True
        self.btn_ping_all.configure(text="Замер...", state="disabled")

        def _task():
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=8) as executor:
                list(executor.map(lambda p: quick_ping_proxy(p, timeout=2.5), self.proxies))

            def _ui():
                self.is_checking_pings = False
                self.btn_ping_all.configure(text="⚡ Замерить все", state="normal")
                save_proxies(self.proxies)
                self.update_selected_server_card()
                self.update_proxy_list_ui()

            self.after(0, _ui)

        threading.Thread(target=_task, daemon=True).start()

    # ================= ОБНОВЛЕНИЕ КАРТОЧЕК СЕРВЕРОВ =================
    def get_selected_proxy(self) -> Optional[ProxyItem]:
        for p in self.proxies:
            if p.id == self.selected_proxy_id:
                return p
        return None

    def update_selected_server_card(self):
        sel = self.get_selected_proxy()
        if sel:
            self.lbl_srv_code.configure(text=sel.get_country_code())
            self.lbl_srv_name.configure(text=sel.get_location_name())
            
            # Бейдж протокола
            proto = sel.protocol.upper()
            if proto == "HTTP":
                self.lbl_srv_proto.configure(text="HTTP", fg_color="#3d2b0e", text_color="#f59e0b")
            else:
                self.lbl_srv_proto.configure(text="SOCKS5", fg_color="#0c2b4d", text_color="#38bdf8")

            self.lbl_srv_host.configure(text=f"{sel.host}:{sel.port}")
            
            if sel.latency_ms is not None:
                self.lbl_srv_ping.configure(text=f"{sel.latency_ms} ms", text_color=COLOR_GREEN)
            else:
                self.lbl_srv_ping.configure(text="— ms", text_color=COLOR_TEXT_MUTED)
        else:
            self.lbl_srv_code.configure(text="--")
            self.lbl_srv_name.configure(text="Сервер не выбран")
            self.lbl_srv_proto.configure(text="NONE", fg_color="#182338", text_color="gray")
            self.lbl_srv_host.configure(text="Добавьте прокси в список")
            self.lbl_srv_ping.configure(text="—", text_color="gray")

    def select_proxy(self, proxy_id: str):
        if self.is_busy:
            return
        self.selected_proxy_id = proxy_id
        self.update_selected_server_card()
        self.update_proxy_list_ui()

        # Если туннель уже запущен, предложим переподключиться на лету
        if self.singbox_manager.is_running():
            sel = self.get_selected_proxy()
            if sel and messagebox.askyesno("Смена IP", f"Переключить весь ПК на {sel.host}:{sel.port}?"):
                self.connect_proxy(sel)

    def delete_proxy(self, proxy_id: str):
        if self.singbox_manager.is_running() and self.singbox_manager.active_proxy and self.singbox_manager.active_proxy.id == proxy_id:
            messagebox.showwarning("Внимание", "Нельзя удалить прокси, который сейчас подключен. Сначала отключите TUN.")
            return

        self.proxies = [p for p in self.proxies if p.id != proxy_id]
        if self.selected_proxy_id == proxy_id:
            self.selected_proxy_id = self.proxies[0].id if self.proxies else None

        save_proxies(self.proxies)
        self.btn_nav_servers.configure(text=f"Серверы ({len(self.proxies)})")
        self.update_selected_server_card()
        self.update_proxy_list_ui()

    def update_proxy_list_ui(self):
        for widget in self.scroll_servers.winfo_children():
            widget.destroy()

        self.lbl_servers_count.configure(text=f"Выбор узла ({len(self.proxies)})")
        self.btn_nav_servers.configure(text=f"Серверы ({len(self.proxies)})")

        if not self.proxies:
            lbl_empty = ctk.CTkLabel(
                self.scroll_servers,
                text="Список серверов пуст.\nНажмите '+ Добавить' или '📥 Импорт' чтобы загрузить прокси.",
                font=ctk.CTkFont(size=12),
                text_color=COLOR_TEXT_MUTED
            )
            lbl_empty.pack(pady=40)
            return

        for p in self.proxies:
            is_active = (self.singbox_manager.is_running() and
                         self.singbox_manager.active_proxy and
                         self.singbox_manager.active_proxy.id == p.id)
            is_selected = (p.id == self.selected_proxy_id)

            bg_col = "#132857" if is_active else ("#11234a" if is_selected else COLOR_CARD)
            border_col = COLOR_GREEN if is_active else (COLOR_ACCENT if is_selected else COLOR_BORDER)

            card = ctk.CTkFrame(self.scroll_servers, fg_color=bg_col, corner_radius=14, border_color=border_col, border_width=1)
            card.pack(fill="x", pady=4, padx=(4, 12))

            # Левая колонка: Радио / Код страны
            left_col = ctk.CTkFrame(card, fg_color="transparent")
            left_col.pack(side="left", padx=(10, 6), pady=8)

            radio_sym = "●" if is_selected else "○"
            radio_col = COLOR_GREEN if is_active else (COLOR_ACCENT if is_selected else "gray")
            lbl_radio = ctk.CTkLabel(left_col, text=radio_sym, font=ctk.CTkFont(size=12), text_color=radio_col)
            lbl_radio.pack(side="left", padx=(0, 6))

            code_badge = ctk.CTkLabel(
                left_col,
                text=p.get_country_code(),
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color="#0a1a38",
                text_color="white",
                corner_radius=6,
                width=32,
                height=26
            )
            code_badge.pack(side="left")

            # Средняя колонка: Имя, Протокол, Хост
            mid_col = ctk.CTkFrame(card, fg_color="transparent")
            mid_col.pack(side="left", fill="both", expand=True, padx=4)

            name_row = ctk.CTkFrame(mid_col, fg_color="transparent")
            name_row.pack(anchor="w")

            ctk.CTkLabel(name_row, text=p.get_location_name(), font=ctk.CTkFont(size=12, weight="bold"), text_color="white").pack(side="left", padx=(0, 6))

            proto_bg = "#3d2b0e" if p.protocol.lower() == "http" else "#0c2b4d"
            proto_fg = "#f59e0b" if p.protocol.lower() == "http" else "#38bdf8"
            ctk.CTkLabel(name_row, text=p.protocol.upper(), font=ctk.CTkFont(size=9, weight="bold"), fg_color=proto_bg, text_color=proto_fg, corner_radius=4, width=38, height=16).pack(side="left")

            auth_note = f" • {p.username}" if p.username else " • без пароля"
            ctk.CTkLabel(mid_col, text=f"{p.host}:{p.port}{auth_note}", font=ctk.CTkFont(family="Consolas", size=10), text_color=COLOR_TEXT_MUTED).pack(anchor="w")

            # Правая колонка: Бейдж пинга и кнопки
            right_col = ctk.CTkFrame(card, fg_color="transparent")
            right_col.pack(side="right", padx=10, pady=8)

            ping_txt = f"{p.latency_ms} ms" if p.latency_ms is not None else "— ms"
            ping_fg = COLOR_GREEN if p.latency_ms is not None else COLOR_TEXT_MUTED
            lbl_ping = ctk.CTkLabel(
                right_col,
                text=ping_txt,
                font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
                text_color=ping_fg,
                fg_color="#061730",
                corner_radius=6,
                width=56,
                height=24
            )
            lbl_ping.pack(side="left", padx=(0, 6))

            # Кнопка копировать
            btn_copy = ctk.CTkButton(
                right_col,
                text="Копир.",
                font=ctk.CTkFont(size=10, weight="bold"),
                width=50,
                height=24,
                fg_color="#0c224a",
                hover_color="#18366d",
                text_color="#60a5fa",
                corner_radius=6,
                command=lambda raw=p.get_raw_line(): self.copy_to_clip(raw)
            )
            btn_copy.pack(side="left", padx=(0, 4))

            # Кнопка удалить
            btn_del = ctk.CTkButton(
                right_col,
                text="✕",
                font=ctk.CTkFont(size=11, weight="bold"),
                width=24,
                height=24,
                fg_color="#2b1111",
                hover_color="#451818",
                text_color="#f87171",
                corner_radius=6,
                command=lambda pid=p.id: self.delete_proxy(pid)
            )
            btn_del.pack(side="left")

            # Клик по карточке выбирает сервер
            def _bind_click(widget, pid):
                widget.bind("<Button-1>", lambda e: self.select_proxy(pid))
                for child in widget.winfo_children():
                    if not isinstance(child, ctk.CTkButton):
                        child.bind("<Button-1>", lambda e: self.select_proxy(pid))

            _bind_click(card, p.id)

    def copy_to_clip(self, text: str):
        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo("Скопировано", f"Строка прокси скопирована в буфер:\n{text}")

    # ================= ДИАЛОГИ =================
    def open_add_dialog(self):
        dialog = AddProxyDialog(self)
        self.wait_window(dialog)
        if dialog.result_proxy:
            self.proxies.append(dialog.result_proxy)
            if not self.selected_proxy_id:
                self.selected_proxy_id = dialog.result_proxy.id
            save_proxies(self.proxies)
            self.update_selected_server_card()
            self.update_proxy_list_ui()

    def open_import_dialog(self):
        dialog = BulkImportDialog(self)
        self.wait_window(dialog)
        if dialog.imported_proxies:
            self.proxies.extend(dialog.imported_proxies)
            if not self.selected_proxy_id:
                self.selected_proxy_id = self.proxies[0].id
            save_proxies(self.proxies)
            self.update_selected_server_card()
            self.update_proxy_list_ui()

    def on_closing(self):
        if self.singbox_manager.is_running():
            self.singbox_manager.stop()
        self.destroy()


# ================= ДИАЛОГ ДОБАВЛЕНИЯ ПРОКСИ =================
class AddProxyDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Добавить прокси")
        self.geometry("440x480")
        self.configure(fg_color=COLOR_BG)
        self.grab_set()

        self.result_proxy: Optional[ProxyItem] = None
        self._build_ui()

    def _build_ui(self):
        lbl = ctk.CTkLabel(self, text="Добавление прокси", font=ctk.CTkFont(size=16, weight="bold"), text_color="white")
        lbl.pack(pady=(16, 4))

        sub = ctk.CTkLabel(self, text="Заполните параметры или вставьте строку формата ip:port:user:pass", font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_MUTED)
        sub.pack(pady=(0, 10))

        btn_clip = ctk.CTkButton(
            self,
            text="📋 Вставить из буфера обмена",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#122a5e",
            hover_color="#1a3b82",
            border_color="#234e9e",
            border_width=1,
            height=32,
            command=self.autofill_from_clipboard
        )
        btn_clip.pack(fill="x", padx=25, pady=(0, 12))

        form = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=14, border_color=COLOR_BORDER, border_width=1)
        form.pack(fill="x", padx=25, pady=4)

        ctk.CTkLabel(form, text="Протокол:", font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_MUTED).pack(anchor="w", padx=14, pady=(10, 2))
        self.proto_var = ctk.StringVar(value="http")
        proto_box = ctk.CTkSegmentedButton(form, values=["http", "socks5"], variable=self.proto_var)
        proto_box.pack(fill="x", padx=14, pady=(0, 8))

        ctk.CTkLabel(form, text="IP адрес / Хост:", font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_MUTED).pack(anchor="w", padx=14, pady=(2, 2))
        self.ent_host = ctk.CTkEntry(form, placeholder_text="например 192.0.2.1")
        self.ent_host.pack(fill="x", padx=14, pady=(0, 8))
        make_pasteable(self.ent_host)

        ctk.CTkLabel(form, text="Порт:", font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_MUTED).pack(anchor="w", padx=14, pady=(2, 2))
        self.ent_port = ctk.CTkEntry(form, placeholder_text="например 8000")
        self.ent_port.pack(fill="x", padx=14, pady=(0, 8))
        make_pasteable(self.ent_port)

        ctk.CTkLabel(form, text="Логин (если есть):", font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_MUTED).pack(anchor="w", padx=14, pady=(2, 2))
        self.ent_user = ctk.CTkEntry(form, placeholder_text="логин")
        self.ent_user.pack(fill="x", padx=14, pady=(0, 8))
        make_pasteable(self.ent_user)

        ctk.CTkLabel(form, text="Пароль (если есть):", font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_MUTED).pack(anchor="w", padx=14, pady=(2, 2))
        self.ent_pass = ctk.CTkEntry(form, placeholder_text="пароль", show="*")
        self.ent_pass.pack(fill="x", padx=14, pady=(0, 12))
        make_pasteable(self.ent_pass)

        btn_box = ctk.CTkFrame(self, fg_color="transparent")
        btn_box.pack(fill="x", padx=25, pady=(12, 16))

        btn_save = ctk.CTkButton(btn_box, text="Сохранить", font=ctk.CTkFont(size=12, weight="bold"), fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, height=34, command=self.save)
        btn_save.pack(side="right", padx=(6, 0))

        btn_cancel = ctk.CTkButton(btn_box, text="Отмена", font=ctk.CTkFont(size=12), fg_color="#182747", hover_color="#243863", height=34, command=self.destroy)
        btn_cancel.pack(side="right")

    def autofill_from_clipboard(self):
        try:
            clip = self.clipboard_get().strip()
            item = parse_proxy_line(clip)
            if item:
                self.ent_host.delete(0, "end")
                self.ent_host.insert(0, item.host)
                self.ent_port.delete(0, "end")
                self.ent_port.insert(0, str(item.port))
                self.ent_user.delete(0, "end")
                if item.username:
                    self.ent_user.insert(0, item.username)
                self.ent_pass.delete(0, "end")
                if item.password:
                    self.ent_pass.insert(0, item.password)
                self.proto_var.set(item.protocol)
            else:
                messagebox.showinfo("Буфер обмена", f"В буфере не найдена строка ip:port:user:pass:\n{clip[:60]}")
        except Exception as e:
            messagebox.showwarning("Ошибка", f"Не удалось прочитать буфер: {e}")

    def save(self):
        host = self.ent_host.get().strip()
        port_str = self.ent_port.get().strip()
        user = self.ent_user.get().strip() or None
        pwd = self.ent_pass.get().strip() or None
        proto = self.proto_var.get()

        if not host or not port_str:
            messagebox.showwarning("Ошибка", "Заполните хост и порт.")
            return

        try:
            port = int(port_str)
        except ValueError:
            messagebox.showwarning("Ошибка", "Порт должен быть числом.")
            return

        import uuid
        self.result_proxy = ProxyItem(
            id=str(uuid.uuid4())[:8],
            host=host,
            port=port,
            protocol=proto,
            username=user,
            password=pwd
        )
        self.destroy()


# ================= ДИАЛОГ МАССОВОГО ИМПОРТА =================
class BulkImportDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Импорт списка прокси")
        self.geometry("520x520")
        self.configure(fg_color=COLOR_BG)
        self.grab_set()

        self.imported_proxies: List[ProxyItem] = []
        self._build_ui()

    def _build_ui(self):
        lbl = ctk.CTkLabel(self, text="Вставьте список прокси", font=ctk.CTkFont(size=16, weight="bold"), text_color="white")
        lbl.pack(pady=(16, 2))

        sub = ctk.CTkLabel(self, text="Формат: ip:port:login:pass или ip:port (по одной на строку)", font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_MUTED)
        sub.pack(pady=(0, 10))

        top_bar = ctk.CTkFrame(self, fg_color="transparent")
        top_bar.pack(fill="x", padx=20, pady=(0, 6))

        ctk.CTkLabel(top_bar, text="Протокол по умолчанию:", font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_MUTED).pack(side="left", padx=(0, 8))
        self.proto_var = ctk.StringVar(value="http")
        proto_menu = ctk.CTkSegmentedButton(top_bar, values=["http", "socks5"], variable=self.proto_var)
        proto_menu.pack(side="left")

        btn_paste_clip = ctk.CTkButton(
            top_bar,
            text="📋 Из буфера",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#122a5e",
            hover_color="#1a3b82",
            width=110,
            command=self.paste_from_clip
        )
        btn_paste_clip.pack(side="right")

        self.txt_input = ctk.CTkTextbox(self, corner_radius=12, fg_color=COLOR_CARD, border_color=COLOR_BORDER, border_width=1, font=ctk.CTkFont(family="Consolas", size=12))
        self.txt_input.pack(fill="both", expand=True, padx=20, pady=6)
        make_pasteable(self.txt_input)

        btn_box = ctk.CTkFrame(self, fg_color="transparent")
        btn_box.pack(fill="x", padx=20, pady=(10, 16))

        btn_import = ctk.CTkButton(
            btn_box,
            text="Импортировать",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            height=34,
            command=self.process_import
        )
        btn_import.pack(side="right", padx=(6, 0))

        btn_cancel = ctk.CTkButton(
            btn_box,
            text="Отмена",
            fg_color="#182747",
            hover_color="#243863",
            height=34,
            command=self.destroy
        )
        btn_cancel.pack(side="right")

    def paste_from_clip(self):
        try:
            text = self.clipboard_get()
            self.txt_input.insert("insert", text)
        except Exception as e:
            messagebox.showwarning("Буфер обмена", f"Не удалось прочитать буфер: {e}")

    def process_import(self):
        text = self.txt_input.get("1.0", "end")
        proto = self.proto_var.get()
        parsed = parse_bulk_proxies(text, default_protocol=proto)

        if not parsed:
            messagebox.showwarning("Внимание", "Не удалось распознать ни одного прокси. Проверьте формат.")
            return

        self.imported_proxies = parsed
        messagebox.showinfo("Успешно", f"Успешно импортировано прокси: {len(parsed)}")
        self.destroy()
