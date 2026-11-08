"""The quickstart runs, end to end, exactly as docs/QUICKSTART.md shows it."""

from __future__ import annotations

import contextlib
import io
import socket
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from examples import quickstart
from memory_fabric.offline import NetworkAccessDenied, offline_mode


class Quickstart(unittest.TestCase):
    def test_store_retrieve_inspect_correct_verify(self) -> None:
        with TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()) as out:
            result = quickstart.main(str(Path(tmp) / "q.db"))
        self.assertEqual(result["status"], "contained")
        self.assertEqual(result["shown_after"], [result["right"]])
        self.assertIn("quarantined", out.getvalue())

    def test_offline_mode_refuses_socket_connections_and_dns(self) -> None:
        connect = socket.socket.connect
        with offline_mode():
            with self.assertRaises(NetworkAccessDenied):
                socket.create_connection(("127.0.0.1", 9), timeout=0.01)
            with self.assertRaises(NetworkAccessDenied):
                socket.getaddrinfo("example.invalid", 80)
            tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                with self.assertRaises(NetworkAccessDenied):
                    tcp.connect(("127.0.0.1", 9))
            finally:
                tcp.close()
            udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                with self.assertRaises(NetworkAccessDenied):
                    udp.sendto(b"probe", ("127.0.0.1", 9))
            finally:
                udp.close()
        self.assertIs(socket.socket.connect, connect)

    def test_quickstart_succeeds_while_socket_connections_are_forbidden(self) -> None:
        with TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()) as out:
            result = quickstart.main(str(Path(tmp) / "quickstart.db"))
        self.assertEqual(result["status"], "contained")
        self.assertIn("recovery: contained / quarantined", out.getvalue())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
