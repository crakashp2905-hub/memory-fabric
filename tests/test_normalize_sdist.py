from __future__ import annotations

import gzip
import io
import tarfile
import tempfile
import unittest
from pathlib import Path

from tools.normalize_sdist import normalize


class NormalizeSdist(unittest.TestCase):
    def test_different_source_timestamps_produce_identical_normalized_archives(self) -> None:
        root = Path(__file__).resolve().parents[1]
        scratch = root / ".test-tmp" / "normalize-sdist"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            temp = Path(directory)
            sources = [temp / "first.tar.gz", temp / "second.tar.gz"]
            for source, mtime in zip(sources, (100, 200), strict=True):
                with tarfile.open(source, "w:gz", format=tarfile.GNU_FORMAT) as archive:
                    content = b"sample source\n"
                    member = tarfile.TarInfo("package-1.0/source.txt")
                    member.size = len(content)
                    member.mtime = mtime
                    member.uid = mtime
                    member.gid = mtime
                    archive.addfile(member, io.BytesIO(content))
            outputs = [temp / "first.normalized.tar.gz", temp / "second.normalized.tar.gz"]
            for source, destination in zip(sources, outputs, strict=True):
                normalize(source, destination, epoch=1234567890)
            self.assertEqual(outputs[0].read_bytes(), outputs[1].read_bytes())
            with gzip.open(outputs[0], "rb") as zipped:
                with tarfile.open(fileobj=zipped, mode="r:") as archive:
                    member = archive.getmember("package-1.0/source.txt")
                    self.assertEqual(member.mtime, 1234567890)
                    self.assertEqual(archive.extractfile(member).read(), b"sample source\n")


if __name__ == "__main__":
    unittest.main()
