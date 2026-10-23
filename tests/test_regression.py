import unittest
import os
import sys
import re
import time
import socket
import threading
import subprocess
import hashlib
import tempfile
from unittest.mock import patch, MagicMock

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.proxy_model import ProxyItem, parse_proxy_line
from core.ip_service import (
    _clean_geo_str,
    _clean_code,
    _resolve_ip_with_timeout,
    resolve_host_geo,
    probe_proxy_protocol
)
from core.singbox_manager import SingBoxManager
from core.paths import PINNED_HASHES


def _start_mock_server(handler_fn):
    """Вспомогательный мок-сервер для тестирования реальных сокет-проб."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.listen(10)
    stop_event = threading.Event()

    def _srv():
        while not stop_event.is_set():
            try:
                s.settimeout(0.1)
                client, _ = s.accept()
                threading.Thread(target=handler_fn, args=(client,), daemon=True).start()
            except (socket.timeout, OSError):
                pass

    t = threading.Thread(target=_srv, daemon=True)
    t.start()

    def _cleanup():
        stop_event.set()
        try:
            s.close()
        except Exception:
            pass

    return port, _cleanup


class TestRegressionR2R3(unittest.TestCase):

    def setUp(self):
        """Гарантирует изоляцию хранилища на весь срок каждого теста."""
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)

        # Перенаправляем все пути к защищенному каталогу во временную директорию
        self.patch_root = patch("core.paths.get_secure_root", return_value=self.tmp_dir.name)
        self.patch_data = patch("core.paths.get_user_data_dir", return_value=self.tmp_dir.name)
        self.patch_root.start()
        self.patch_data.start()
        self.addCleanup(self.patch_root.stop)
        self.addCleanup(self.patch_data.stop)

    def test_r2_1_singbox_typing_and_annotations(self):
        """R2-1: Verify SingBoxManager imports cleanly with future annotations and Tuple."""
        import core.singbox_manager
        annotations = core.singbox_manager.SingBoxManager._probe_tunnel.__annotations__
        self.assertIn("endpoints", annotations)

    def test_r2_2_singbox_binary_and_dns_fallback(self):
        """R2-2: Verify bundled sing-box is 1.14.3, hash matches PINNED_HASHES, and config check passes."""
        bin_path = os.path.join("bin", "sing-box.exe")
        self.assertTrue(os.path.exists(bin_path), "bin/sing-box.exe must exist")

        # 1. SHA256 integrity
        with open(bin_path, "rb") as f:
            actual_hash = hashlib.sha256(f.read()).hexdigest()
        self.assertEqual(actual_hash, PINNED_HASHES.get("sing-box.exe"), "SHA256 must match pinned hash")

        # 2. Version check
        ver_proc = subprocess.run([bin_path, "version"], capture_output=True, text=True)
        self.assertEqual(ver_proc.returncode, 0)
        self.assertIn("1.14", ver_proc.stdout, "sing-box version must be 1.14.x")

        # 3. Generate config and run sing-box check
        with patch("core.singbox_manager.get_secure_bin_dir", return_value="bin"), \
             patch("core.singbox_manager.get_log_dir", return_value="logs"):
            sm = SingBoxManager()
            for proto in ("socks5", "http"):
                p = ProxyItem(id="t1", host="1.2.3.4", port=1080, protocol=proto)
                cfg = sm.generate_config(p)

                # Check DNS fallback rule structure
                dns_rules = cfg["dns"]["rules"]
                actions = [r.get("action") for r in dns_rules]
                self.assertIn("evaluate", actions)
                self.assertIn("respond", actions)
                self.assertEqual(cfg["dns"]["final"], "dns-remote-tcp")
                self.assertEqual(cfg["route"]["default_domain_resolver"], "dns-direct")

                # Validate with sing-box check
                import json
                tmp_cfg = os.path.join(self.tmp_dir.name, f"tmp_check_{proto}.json")
                with open(tmp_cfg, "w") as tf:
                    json.dump(cfg, tf)
                chk = subprocess.run([bin_path, "check", "-c", tmp_cfg], capture_output=True, text=True)
                self.assertEqual(chk.returncode, 0, f"sing-box check failed: {chk.stderr}")

    def test_r2_3_auto_protocol_no_guessing(self):
        """R2-3: Auto mode must return error when undetermined, without saving a guess."""
        from gui.app_webview import ProxyTunBridgeApi

        with patch("gui.app_webview.SingBoxManager"), \
             patch("gui.app_webview.is_admin", return_value=True), \
             patch("gui.app_webview.load_proxies", return_value=[]), \
             patch("gui.app_webview.save_proxies") as mock_save, \
             patch("gui.app_webview.load_settings", return_value={}):

            api = ProxyTunBridgeApi()
            self.addCleanup(api.shutdown)

            # When probe fails (None), do NOT save a guess on port 8080 or 443
            with patch("gui.app_webview.probe_proxy_protocol", return_value=None):
                res1 = api.add_proxy("1.2.3.4", 8080, "auto")
                self.assertFalse(res1["success"], "Auto probe failure must not succeed")
                self.assertIn("Не удалось автоматически определить", res1["error"])
                self.assertEqual(len(api.proxies), 0, "Failed auto probe must not add proxy")

                res2 = api.add_proxy("1.2.3.4", 443, "auto")
                self.assertFalse(res2["success"])
                self.assertEqual(len(api.proxies), 0)

            # When probe succeeds with socks5, protocol is socks5
            with patch("gui.app_webview.probe_proxy_protocol", return_value="socks5"):
                res3 = api.add_proxy("1.2.3.4", 8080, "auto")
                self.assertTrue(res3["success"])
                self.assertEqual(api.proxies[0].protocol, "socks5")

            # Explicit choice on port 80: must NOT probe and must keep socks5
            with patch("gui.app_webview.probe_proxy_protocol") as mock_probe:
                res4 = api.add_proxy("5.6.7.8", 80, "socks5")
                self.assertTrue(res4["success"])
                mock_probe.assert_not_called()
                self.assertEqual(api.proxies[1].protocol, "socks5")

    def test_r2_4_bounded_dns_and_async_geo(self):
        """R2-4: DNS resolution is bounded, and geo resolution runs asynchronously."""
        # IP addresses bypass DNS completely
        self.assertEqual(_resolve_ip_with_timeout("1.1.1.1", timeout=0.5), "1.1.1.1")
        self.assertEqual(_resolve_ip_with_timeout("2606:4700::6810:85e5", timeout=0.5), "2606:4700::6810:85e5")

        # Simulated slow DNS resolution terminates within deadline
        def slow_dns(h):
            time.sleep(2.0)
            return "1.2.3.4"

        with patch("socket.gethostbyname", side_effect=slow_dns):
            t0 = time.monotonic()
            res = _resolve_ip_with_timeout("unreachable.domain.test", timeout=0.2)
            elapsed = time.monotonic() - t0
            self.assertLess(elapsed, 0.8, "DNS resolution must be bounded by timeout")
            self.assertEqual(res, "unreachable.domain.test")

    def test_r2_5_firefox_probe_and_captive_portal(self):
        """R2-5: Firefox probe requires exact 'success' body; captive portal 200 is rejected."""
        from core.singbox_manager import _probe_request
        import io
        sm = SingBoxManager.__new__(SingBoxManager)
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None

        class MockResp:
            def __init__(self, code, text):
                self.status_code = code
                self.text = text
                self.raw = MagicMock()
                self.raw.read.side_effect = lambda *args,**kwargs:text.encode()
            def close(self): pass

        # 1. Body starts with success but is invalid -> REJECTED
        with patch("requests.Session.get", return_value=MockResp(200, "success-but-different-body")):
            ok = _probe_request("http://detectportal.firefox.com/success.txt", "firefox_success", .3)
            self.assertFalse(ok, "Non-exact success body must be rejected")

        # 2. Body is exactly 'success\n' -> ACCEPTED
        with patch("requests.Session.get", return_value=MockResp(200, "success\n")):
            ok = _probe_request("http://detectportal.firefox.com/success.txt", "firefox_success", .3)
            self.assertTrue(ok, "Exact 'success' body must be accepted")

        # 3. Captive portal HTML 200 on generate_204 -> REJECTED
        with patch("requests.Session.get", return_value=MockResp(200, "<html>Portal Login</html>")):
            ok = _probe_request("https://cp.cloudflare.com/generate_204", "204", .3)
            self.assertFalse(ok, "200 on generate_204 endpoint must be rejected")

        # 4. Real 204 on HTTPS generate_204 -> ACCEPTED
        with patch("requests.Session.get", return_value=MockResp(204, "")):
            ok = _probe_request("https://cp.cloudflare.com/generate_204", "204", .3)
            self.assertTrue(ok, "204 on HTTPS generate_204 must be accepted")

    def test_sanitization_and_lan_code(self):
        """Sanitization: Strings are cleaned, LAN code is preserved."""
        p = ProxyItem(id="x", host="<img src=x>", port=80, country="<script>alert(1)</script>", city="<b>City</b>")
        self.assertNotIn("<", p.safe_host())
        self.assertNotIn(">", p.safe_host())
        self.assertNotIn("<", p.get_location_name())
        self.assertNotIn(">", p.get_location_name())

        p_lan = ProxyItem(id="l", host="192.168.1.1", port=80, country="Local Network", country_code="LAN")
        self.assertEqual(p_lan.get_country_code(), "LAN")
        self.assertEqual(p_lan.get_location_name(), "Local Network")

    # =========================================================================
    # R3-1: Тестирование защиты хранилища от гонок при завершении работы (Shutdown)
    # =========================================================================
    def test_r3_1_storage_isolation_and_shutdown_safety(self):
        """R3-1: Background geo tasks must NOT write to storage after api.shutdown()."""
        from gui.app_webview import ProxyTunBridgeApi

        save_mock = MagicMock()
        def slow_geo(h, timeout=3.0):
            time.sleep(0.3)
            return ("Germany", "DE", "Berlin")

        with patch("gui.app_webview.SingBoxManager"), \
             patch("gui.app_webview.is_admin", return_value=True), \
             patch("gui.app_webview.load_proxies", return_value=[]), \
             patch("gui.app_webview.load_settings", return_value={}), \
             patch("gui.app_webview.save_proxies", save_mock), \
             patch("gui.app_webview.resolve_host_geo", side_effect=slow_geo):

            api = ProxyTunBridgeApi()

            # Добавляем прокси: вызывается ровно 1 синхронное сохранение до постановки задачи гео
            res = api.add_proxy("1.2.3.4", 1080, "socks5")
            self.assertTrue(res["success"])
            initial_saves = save_mock.call_count
            self.assertEqual(initial_saves, 1, "Must save exactly once upon initial addition")

            # Немедленно закрываем API
            api.shutdown()
            self.assertTrue(api._closing)

            # Ждем завершения фонового воркера гео (0.3s sleep в slow_geo + запас)
            time.sleep(0.5)

            # Проверяем: фоновый воркер НЕ должен был вызвать save_proxies после shutdown!
            self.assertEqual(save_mock.call_count, initial_saves, "No disk save may occur after shutdown()")

            # Прямой вызов _save() при _closing=True должен быть no-op
            api._save()
            self.assertEqual(save_mock.call_count, initial_saves, "_save() must be a no-op when closing")

    # =========================================================================
    # R3-2: Тестирование реальной функции probe_proxy_protocol с сокет-моделями
    # =========================================================================
    def test_r3_2_real_probe_http_silence_on_socks(self):
        """R3-2: Real probe must detect HTTP proxy immediately even if it is silent on SOCKS greeting."""
        def handler(client):
            try:
                client.settimeout(1.5)
                req = client.recv(1024)
                if req.startswith(b"CONNECT"):
                    client.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
                elif req.startswith(b"\x05"):
                    # Сервер HTTP молчит при получении бинарного приветствия SOCKS
                    time.sleep(1.2)
                client.close()
            except Exception:
                pass

        port, cleanup = _start_mock_server(handler)
        try:
            t0 = time.monotonic()
            proto = probe_proxy_protocol("127.0.0.1", port, timeout=1.5)
            elapsed = time.monotonic() - t0
            self.assertEqual(proto, "http")
            # Обнаружение должно пройти параллельно и быстро (< 0.5s), не дожидаясь таймаута SOCKS
            self.assertLess(elapsed, 0.6, "Parallel probe must not be starved by silent SOCKS handler")
        finally:
            cleanup()

    def test_r3_2_real_probe_http_auth_407(self):
        """R3-2: Real probe must detect HTTP proxy returning 407 Proxy Authentication Required."""
        def handler(client):
            try:
                client.settimeout(1.0)
                req = client.recv(1024)
                if req.startswith(b"CONNECT"):
                    client.sendall(b"HTTP/1.1 407 Proxy Authentication Required\r\nProxy-Authenticate: Basic\r\n\r\n")
                client.close()
            except Exception:
                pass

        port, cleanup = _start_mock_server(handler)
        try:
            proto = probe_proxy_protocol("127.0.0.1", port, timeout=1.0)
            self.assertEqual(proto, "http")
        finally:
            cleanup()

    def test_r3_2_real_probe_socks5_auth_variants(self):
        """R3-2: Real probe must detect SOCKS5 with methods 00 (no auth), 02 (user/pass), and FF (no acceptable methods)."""
        for code, expected_name in [(b"\x05\x00", "no auth"), (b"\x05\x02", "user/pass"), (b"\x05\xff", "methods required")]:
            def make_handler(ret_bytes):
                def handler(client):
                    try:
                        client.settimeout(1.0)
                        req = client.recv(1024)
                        if req.startswith(b"\x05"):
                            client.sendall(ret_bytes)
                        client.close()
                    except Exception:
                        pass
                return handler

            port, cleanup = _start_mock_server(make_handler(code))
            try:
                proto = probe_proxy_protocol("127.0.0.1", port, timeout=1.0)
                self.assertEqual(proto, "socks5", f"SOCKS5 response {code.hex()} ({expected_name}) must be detected as socks5")
            finally:
                cleanup()

    def test_r3_2_real_probe_fragmented_tcp(self):
        """R3-2: Real probe must properly handle fragmented TCP stream responses."""
        def handler(client):
            try:
                client.settimeout(1.0)
                req = client.recv(1024)
                if req.startswith(b"\x05"):
                    # Отправляем первый байт
                    client.sendall(b"\x05")
                    time.sleep(0.05)
                    # Отправляем второй байт с задержкой
                    client.sendall(b"\x00")
                client.close()
            except Exception:
                pass

        port, cleanup = _start_mock_server(handler)
        try:
            proto = probe_proxy_protocol("127.0.0.1", port, timeout=1.0)
            self.assertEqual(proto, "socks5")
        finally:
            cleanup()

    def test_r3_2_real_probe_silent_server_timeout(self):
        """R3-2: Silent non-responsive server must return None within timeout."""
        def handler(client):
            try:
                # Ничего не отправляем в ответ
                time.sleep(2.0)
                client.close()
            except Exception:
                pass

        port, cleanup = _start_mock_server(handler)
        try:
            t0 = time.monotonic()
            proto = probe_proxy_protocol("127.0.0.1", port, timeout=0.3)
            elapsed = time.monotonic() - t0
            self.assertIsNone(proto)
            self.assertLess(elapsed, 0.6, "Timeout must be bounded and not hang")
        finally:
            cleanup()

    # =========================================================================
    # R4-1: Тестирование строгого отсечения не-прокси HTTP-ответов (404, 405, malformed)
    # =========================================================================
    def test_r4_1_negative_http_probe_rejection(self):
        """R4-1: Server responding with non-proxy codes (404, 405, 500, 400, 403) or malformed status must NOT be detected as http."""
        negative_responses = [
            (b"HTTP/1.1 404 Not Found\r\n\r\n", "404 Not Found"),
            (b"HTTP/1.1 405 Method Not Allowed\r\n\r\n", "405 Method Not Allowed"),
            (b"HTTP/1.1 nope\r\n\r\n", "malformed status"),
            (b"HTTP/1.1 500 Internal Server Error\r\n\r\n", "500 Server Error"),
            (b"HTTP/1.1 400 Bad Request\r\n\r\n", "400 Bad Request"),
            (b"HTTP/1.1 403 Forbidden\r\n\r\n", "403 Forbidden"),
            (b"NOT_HTTP_DATA\r\n\r\n", "garbage non-http data"),
        ]

        for resp_bytes, desc in negative_responses:
            def make_handler(ret_bytes):
                def handler(client):
                    try:
                        client.settimeout(0.5)
                        req = client.recv(1024)
                        if req.startswith(b"CONNECT"):
                            client.sendall(ret_bytes)
                        client.close()
                    except Exception:
                        pass
                return handler

            port, cleanup = _start_mock_server(make_handler(resp_bytes))
            try:
                proto = probe_proxy_protocol("127.0.0.1", port, timeout=0.3)
                self.assertIsNone(
                    proto,
                    f"Response '{desc}' must NOT be detected as http, got: {proto}"
                )
            finally:
                cleanup()

    # =========================================================================
    # R3-3: Тестирование ограниченного DNS для Auto с именами хостов
    # =========================================================================
    def test_r3_3_bounded_dns_for_auto_hostname(self):
        """R3-3: Hostname DNS in probe_proxy_protocol must be bounded and not block."""
        # 1. Замедленный DNS: системный вызов занимает 2 секунды
        def slow_dns(h):
            time.sleep(2.0)
            return "127.0.0.1"

        with patch("socket.gethostbyname", side_effect=slow_dns):
            t0 = time.monotonic()
            res = probe_proxy_protocol("slow.unresolvable.domain", 8080, timeout=0.4)
            elapsed = time.monotonic() - t0
            self.assertIsNone(res)
            self.assertLess(elapsed, 0.6, "Auto probe on slow domain must fail fast within budget")

        # 2. Успешный DNS к мок-серверу
        def fast_dns(h):
            return "127.0.0.1"

        def handler(client):
            try:
                client.settimeout(1.0)
                req = client.recv(1024)
                if req.startswith(b"\x05"):
                    client.sendall(b"\x05\x00")
                client.close()
            except Exception:
                pass

        port, cleanup = _start_mock_server(handler)
        try:
            with patch("socket.gethostbyname", side_effect=fast_dns):
                res = probe_proxy_protocol("my.proxy.domain", port, timeout=1.0)
                self.assertEqual(res, "socks5")
        finally:
            cleanup()

    # =========================================================================
    # R3-DNS: Архитектурный тест отказоустойчивости DNS sing-box 1.14
    # =========================================================================
    def test_r3_singbox_dns_failover_architecture(self):
        """R3-DNS: Validate 3-tier DNS failover rules (Cloudflare DoH -> Google DoH -> TCP DNS)."""
        with patch("core.singbox_manager.get_secure_bin_dir", return_value="bin"), \
             patch("core.singbox_manager.get_log_dir", return_value="logs"):
            sm = SingBoxManager()
            cfg = sm.generate_config(ProxyItem(id="x", host="9.9.9.9", port=1080, protocol="socks5"))

            servers = cfg["dns"]["servers"]
            tags = [s["tag"] for s in servers]
            self.assertIn("dns-remote-cf", tags)
            self.assertIn("dns-remote-google", tags)
            self.assertIn("dns-remote-tcp", tags)
            self.assertIn("dns-direct", tags)

            # Проверяем цепочку правил
            rules = cfg["dns"]["rules"]
            # Tier 1: evaluate Cloudflare DoH
            self.assertTrue(any(r.get("action") == "evaluate" and r.get("server") == "dns-remote-cf" for r in rules))
            # Tier 2: evaluate Google DoH
            self.assertTrue(any(r.get("action") == "evaluate" and r.get("server") == "dns-remote-google" for r in rules))
            # Tier 3: route TCP DNS
            self.assertTrue(any(r.get("action") == "route" and r.get("server") == "dns-remote-tcp" for r in rules))
            # Final fallback
            self.assertEqual(cfg["dns"]["final"], "dns-remote-tcp")


if __name__ == "__main__":
    unittest.main()
