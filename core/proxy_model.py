import uuid
from dataclasses import dataclass, asdict
from typing import Optional, List
import re

@dataclass
class ProxyItem:
    id: str
    host: str
    port: int
    protocol: str = "socks5"  # socks5 или http
    username: Optional[str] = None
    password: Optional[str] = None
    tag: str = ""
    latency_ms: Optional[int] = None
    country: str = ""
    city: str = ""
    country_code: str = ""
    last_status: str = "unknown"  # alive, dead, unknown

    latency_mode: str = "tcp"  # tcp (legacy direct connect) or tun (protocol response)

    def __post_init__(self):
        proto = (self.protocol or "socks5").lower().strip()
        self.protocol = proto if proto in ("socks5", "http") else "socks5"
        if not self.tag:
            self.tag = f"{self.host}:{self.port}"
        if not self.country_code and self.country and len(self.country.strip()) == 2:
            self.country_code = self.country.strip().upper()

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict):
        from dataclasses import fields
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    def safe_host(self) -> str:
        """Возвращает хост, очищенный от потенциально опасных символов HTML/разметки."""
        return re.sub(r"[<>&\"\'/\\]", "", self.host or "").strip()[:100]

    def get_display_str(self) -> str:
        auth = f" [{self.username}]" if self.username else ""
        proto = self.protocol.upper()
        return f"{proto}://{self.host}:{self.port}{auth}"

    def get_raw_line(self) -> str:
        if self.username and self.password:
            return f"{self.host}:{self.port}:{self.username}:{self.password}"
        return f"{self.host}:{self.port}"

    def get_country_code(self) -> str:
        cc = (self.country_code or "").strip().upper()
        if cc in ("LAN", "LOC", "UNK", "PX"):
            return cc
        if len(cc) == 2 and cc.isalpha():
            return cc

        c = (self.country or "").lower().strip()
        if c in ("lan", "local", "local network"):
            return "LAN"
        if len(c) == 2 and c.isalpha():
            return c.upper()
        if "estonia" in c or c == "ee":
            return "EE"
        elif "singapore" in c or "сингапур" in c or c == "sg":
            return "SG"
        elif "russia" in c or "россия" in c or c == "ru":
            return "RU"
        elif "united states" in c or "usa" in c or c == "us":
            return "US"
        elif "germany" in c or "deutschland" in c or c == "de":
            return "DE"
        elif "united kingdom" in c or "great britain" in c or c in ("uk", "gb"):
            return "GB"
        elif "netherlands" in c or "holland" in c or c == "nl":
            return "NL"
        elif "france" in c or "франция" in c or c == "fr":
            return "FR"
        elif "canada" in c or "канада" in c or c == "ca":
            return "CA"
        elif "finland" in c or "финляндия" in c or c == "fi":
            return "FI"
        elif "sweden" in c or "швеция" in c or c == "se":
            return "SE"
        elif "turkey" in c or "турция" in c or c == "tr":
            return "TR"
        elif "ukraine" in c or "украина" in c or c == "ua":
            return "UA"
        elif "kazakhstan" in c or "казахстан" in c or c == "kz":
            return "KZ"
        elif "belarus" in c or "беларусь" in c or c == "by":
            return "BY"
        elif "poland" in c or "польша" in c or c == "pl":
            return "PL"
        elif "japan" in c or "япония" in c or c == "jp":
            return "JP"
        elif "china" in c or "китай" in c or c == "cn":
            return "CN"
        
        # Check city hints if country empty
        city = (self.city or "").lower()
        if "tallinn" in city:
            return "EE"
        elif "singapore" in city:
            return "SG"
        elif "moscow" in city or "москва" in city or "spb" in city:
            return "RU"
        elif "washington" in city or "new york" in city:
            return "US"
        elif "frankfurt" in city or "berlin" in city:
            return "DE"
        
        return "PX"

    def get_flag(self) -> str:
        return self.get_country_code()

    def get_location_name(self) -> str:
        country_clean = re.sub(r"[<>&\"\'/\\]", "", self.country or "").strip()[:50]
        city_clean = re.sub(r"[<>&\"\'/\\]", "", self.city or "").strip()[:50]
        if city_clean and country_clean:
            return f"{country_clean} ({city_clean})"
        elif country_clean:
            return country_clean
        code = self.get_country_code()
        if code == "LAN":
            return "Local Network"
        names = {
            "EE": "Estonia (Tallinn)",
            "SG": "Singapore (Singapore)",
            "US": "USA (Вашингтон)",
            "DE": "Germany (Франкфурт)",
            "GB": "UK (Лондон)",
            "RU": "Россия (Москва)",
            "NL": "Netherlands (Амстердам)",
            "FR": "France (Париж)",
            "CA": "Canada (Торонто)",
            "FI": "Finland (Хельсинки)",
            "SE": "Sweden (Стокгольм)",
            "TR": "Turkey (Стамбул)",
            "UA": "Ukraine (Киев)",
            "KZ": "Kazakhstan (Алматы)",
            "BY": "Belarus (Минск)",
            "PL": "Poland (Варшава)",
            "JP": "Japan (Токио)"
        }
        return names.get(code, f"Прокси ({self.safe_host()})")


def parse_proxy_line(line: str, default_protocol: str = "socks5") -> Optional[ProxyItem]:
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    protocol = default_protocol.lower()
    has_explicit_scheme = False

    # Проверка на URL схему (например socks5://user:pass@host:port или http://host:port)
    if "://" in line:
        schema, rest = line.split("://", 1)
        if schema.lower() in ("socks5", "socks", "http", "https"):
            protocol = "socks5" if "socks" in schema.lower() else "http"
            has_explicit_scheme = True
            line = rest

    username = None
    password = None

    # Вариант user:pass@host:port
    if "@" in line:
        auth_part, host_part = line.split("@", 1)
        if ":" in auth_part:
            username, password = auth_part.split(":", 1)
        else:
            username = auth_part
        parts = host_part.split(":")
        if len(parts) >= 2:
            host = parts[0]
            try:
                port = int(parts[1])
            except ValueError:
                return None
            if not has_explicit_scheme and port in (80, 3128, 8888):
                protocol = "http"
            elif not has_explicit_scheme and port in (1080, 1081, 9050, 10808):
                protocol = "socks5"
            return ProxyItem(
                id=str(uuid.uuid4())[:8],
                host=host,
                port=port,
                protocol=protocol,
                username=username,
                password=password
            )

    # Стандартный вариант host:port:user:pass или host:port
    parts = line.split(":")
    if len(parts) == 4:
        host, port_str, username, password = parts[0], parts[1], parts[2], parts[3]
        try:
            port = int(port_str)
        except ValueError:
            return None
        if not has_explicit_scheme and port in (80, 3128, 8888):
            protocol = "http"
        elif not has_explicit_scheme and port in (1080, 1081, 9050, 10808):
            protocol = "socks5"
        return ProxyItem(
            id=str(uuid.uuid4())[:8],
            host=host,
            port=port,
            protocol=protocol,
            username=username,
            password=password
        )
    elif len(parts) == 2:
        host, port_str = parts[0], parts[1]
        try:
            port = int(port_str)
        except ValueError:
            return None
        if not has_explicit_scheme and port in (80, 3128, 8888):
            protocol = "http"
        elif not has_explicit_scheme and port in (1080, 1081, 9050, 10808):
            protocol = "socks5"
        return ProxyItem(
            id=str(uuid.uuid4())[:8],
            host=host,
            port=port,
            protocol=protocol
        )

    return None


def parse_bulk_proxies(text: str, default_protocol: str = "socks5") -> List[ProxyItem]:
    proxies = []
    for line in text.strip().splitlines():
        item = parse_proxy_line(line, default_protocol)
        if item:
            proxies.append(item)
    return proxies
