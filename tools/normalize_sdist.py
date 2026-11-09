"""Normalize a setuptools sdist archive for deterministic local provenance."""
from __future__ import annotations

import argparse
import copy
import gzip
import io
import os
import tarfile
import tempfile
from pathlib import Path


def normalize(source: Path, destination: Path | None = None) -> Path:
    """Rewrite tar/gzip metadata to stable values while preserving file bytes."""
    source = source.resolve()
    destination = destination.resolve() if destination is not None else source

    entries: list[tuple[tarfile.TarInfo, bytes | None]] = []
    with tarfile.open(source, mode="r:gz") as archive:
        for original in archive.getmembers():
            member = copy.copy(original)
            if member.isfile():
                stream = archive.extractfile(original)
                if stream is None:
                    raise ValueError(f"missing regular-file payload: {member.name}")
                data = stream.read()
            else:
                data = None
            member.mtime = 0
            member.uid = 0
            member.gid = 0
            member.uname = ""
            member.gname = ""
            member.pax_headers = {}
            entries.append((member, data))

    fd, temporary_name = tempfile.mkstemp(
        prefix=destination.name + ".normalizing-", dir=destination.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as raw_output:
            with gzip.GzipFile(fileobj=raw_output, mode="wb", filename="",
                               mtime=0, compresslevel=9) as compressed:
                with tarfile.open(fileobj=compressed, mode="w|",
                                  format=tarfile.PAX_FORMAT) as output:
                    for member, data in sorted(entries, key=lambda item: item[0].name):
                        output.addfile(member, io.BytesIO(data) if data is not None else None)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="sdist .tar.gz to normalize in place")
    args = parser.parse_args()
    normalize(args.archive)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
