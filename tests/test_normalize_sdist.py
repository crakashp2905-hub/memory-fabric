from __future__ import annotations

import hashlib
import io
import tarfile
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.normalize_sdist import normalize


def _archive(path: Path, mtime: int, reverse: bool) -> None:
    rows = [("pkg/", None), ("pkg/data.txt", b"stable payload")]
    if reverse:
        rows.reverse()
    with tarfile.open(path, "w:gz") as archive:
        for name, payload in rows:
            info = tarfile.TarInfo(name)
            info.mtime = mtime
            info.uid = 1000 + mtime
            info.gid = 1000 + mtime
            if payload is None:
                info.type = tarfile.DIRTYPE
                info.mode = 0o755
                archive.addfile(info)
            else:
                info.size = len(payload)
                archive.addfile(info, io.BytesIO(payload))


class NormalizeSdistTests(unittest.TestCase):
    def test_normalization_removes_timestamp_owner_and_order_variance(self) -> None:
        with TemporaryDirectory() as tmp:
            first = Path(tmp) / "first.tar.gz"
            second = Path(tmp) / "second.tar.gz"
            _archive(first, 100, False)
            _archive(second, 900, True)
            normalize(first)
            normalize(second)
            first_hash = hashlib.sha256(first.read_bytes()).hexdigest()
            second_hash = hashlib.sha256(second.read_bytes()).hexdigest()
            self.assertEqual(first_hash, second_hash)
            with tarfile.open(first, "r:gz") as archive:
                self.assertTrue(all(member.mtime == 0 for member in archive.getmembers()))
                self.assertTrue(all(member.uid == 0 and member.gid == 0
                                    for member in archive.getmembers()))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
