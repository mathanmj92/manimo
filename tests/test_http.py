import http.client
import json
import socket
import threading
import unittest

from tests import APP  # noqa: F401
import server


def request(port, method, path, headers=None, host=None, body=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.putrequest(method, path, skip_host=True)
        conn.putheader("Host", host or f"127.0.0.1:{port}")
        for k, v in (headers or {}).items():
            conn.putheader(k, v)
        data = json.dumps(body).encode() if body is not None else b""
        if method == "POST":
            conn.putheader("Content-Length", str(len(data)))
        conn.endheaders(data)
        r = conn.getresponse()
        raw = r.read()
        try:
            return r.status, json.loads(raw)
        except ValueError:
            return r.status, raw
    finally:
        conn.close()


class HttpServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = server.LocalServer(("127.0.0.1", 0), server.Handler)    # port 0 = any free port
        cls.port = cls.srv.server_address[1]
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.thread.join(5)

    def test_ping(self):
        status, body = request(self.port, "GET", "/api/ping")
        self.assertEqual(status, 200)
        self.assertEqual(body["app"], "manimgx")
        self.assertEqual(body["version"], server.VERSION)

    def test_localhost_host_header_accepted(self):
        status, _ = request(self.port, "GET", "/api/ping", host=f"localhost:{self.port}")
        self.assertEqual(status, 200)

    def test_wrong_host_rejected(self):
        for host in ("evil.example.com", f"evil.example.com:{self.port}", "127.0.0.1", f"127.0.0.1:{self.port + 1}"):
            status, _ = request(self.port, "GET", "/api/ping", host=host)
            self.assertEqual(status, 403, host)

    def test_post_without_token_rejected(self):
        status, body = request(self.port, "POST", "/api/cancel", body={})
        self.assertEqual(status, 403)
        self.assertEqual(body, {"error": "forbidden"})

    def test_post_with_wrong_token_rejected(self):
        status, _ = request(self.port, "POST", "/api/cancel", headers={"X-Token": "nope"}, body={})
        self.assertEqual(status, 403)

    def test_post_with_token_but_wrong_host_rejected(self):
        status, _ = request(self.port, "POST", "/api/cancel", headers={"X-Token": server.TOKEN}, host="evil.example.com", body={})
        self.assertEqual(status, 403)

    def test_post_with_token_passes_auth(self):
        # an unknown endpoint is a 404 only once the token and Host checks have passed
        status, _ = request(self.port, "POST", "/api/definitely-not-real", headers={"X-Token": server.TOKEN}, body={})
        self.assertNotEqual(status, 403)

    def test_unknown_get_is_404(self):
        status, _ = request(self.port, "GET", "/api/definitely-not-real")
        self.assertEqual(status, 404)

    def test_files_path_traversal_not_served(self):
        status, _ = request(self.port, "GET", "/files/abc/../../app/server.py")
        self.assertEqual(status, 404)

    def test_second_server_cannot_bind_same_port(self):
        with self.assertRaises(OSError):
            server.LocalServer(("127.0.0.1", self.port), server.Handler)

    def test_plain_socket_cannot_bind_same_port(self):
        s = socket.socket()
        self.addCleanup(s.close)
        with self.assertRaises(OSError):
            s.bind(("127.0.0.1", self.port))


class CreateServer(unittest.TestCase):
    def test_create_server_skips_a_taken_port(self):
        # reserve a free port block start, then make create_server start there
        probe = server.LocalServer(("127.0.0.1", 0), server.Handler)
        first = probe.server_address[1]
        old = server.FIRST_PORT, server.PORT_SPAN
        server.FIRST_PORT, server.PORT_SPAN = first, 3
        self.addCleanup(setattr, server, "FIRST_PORT", old[0])
        self.addCleanup(setattr, server, "PORT_SPAN", old[1])
        other = None
        try:
            other = server.create_server()
            if other is None:
                self.skipTest("no free port in the test range")
            self.assertNotEqual(other.server_address[1], first)
        finally:
            probe.server_close()
            if other:
                other.server_close()

    def test_create_server_none_when_all_taken(self):
        probe = server.LocalServer(("127.0.0.1", 0), server.Handler)
        server.FIRST_PORT, server.PORT_SPAN = probe.server_address[1], 1
        self.addCleanup(setattr, server, "FIRST_PORT", 8765)
        self.addCleanup(setattr, server, "PORT_SPAN", 11)
        try:
            self.assertIsNone(server.create_server())
        finally:
            probe.server_close()


if __name__ == "__main__":
    unittest.main()
