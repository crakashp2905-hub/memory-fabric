from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class OfflineNetworkGuardTests(unittest.TestCase):
    def test_subprocess_blocks_public_egress_and_allows_loopback_without_host_file_access(self) -> None:
        script = r'''
import builtins, json, sys, urllib.request
from tools import offline_network_guard as guard
guard.install()
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
host_file_access = []
original_open = builtins.open
def watched_open(file, *args, **kwargs):
    host_file_access.append(str(file))
    return original_open(file, *args, **kwargs)
builtins.open = watched_open
try:
    opener.open("http://203.0.113.8/private", timeout=1)
except Exception as exc:
    denial = str(exc)
    if "offline sandbox egress denied" not in denial:
        denial = str(getattr(exc, "reason", exc))
else:
    raise AssertionError("public egress unexpectedly succeeded")
loopback = guard._loopback("127.0.0.1")
guarded_loopback_resolution = bool(__import__("socket").getaddrinfo("127.0.0.1", 80))
print(json.dumps({"denial": denial, "blocked": guard.blocked_attempts(),
                  "host_file_access": host_file_access, "loopback": loopback,
                  "guarded_loopback_resolution": guarded_loopback_resolution}))
'''
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertIn("offline sandbox egress denied", report["denial"])
        self.assertEqual(report["blocked"], ["203.0.113.8"])
        self.assertEqual(report["host_file_access"], [])
        self.assertTrue(report["loopback"])
        self.assertTrue(report["guarded_loopback_resolution"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
