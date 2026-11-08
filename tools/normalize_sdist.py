"""Normalize an sdist tarball's metadata for reproducible candidate artifacts."""
from __future__ import annotations

import argparse
import gzip
import io
import tarfile
from pathlib import Path


def normalize(source: Path, destination: Path, epoch: int) -> None:
    if epoch < 0:
        raise ValueError("SOURCE_DATE_EPOCH must be non-negative")
    with tarfile.open(source, "r:gz") as archive:
        members = sorted(archive.getmembers(), key=lambda item: item.name)
        payloads: list[tuple[tarfile.TarInfo, bytes | None]] = []
        for member in members:
            path = Path(member.name.replace("\\", "/"))
            if path.is_absolute() or ".." in path.parts:
                raise ValueError(f"unsafe sdist member path: {member.name}")
            info = tarfile.TarInfo(member.name)
            info.type = member.type
            info.mode = member.mode & 0o777
            info.size = member.size if member.isfile() else 0
            info.mtime = epoch
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.linkname = member.linkname
            info.pax_headers = {}
            content = archive.extractfile(member).read() if member.isfile() else None
            payloads.append((info, content))

    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as raw:
        with gzip.GzipFile(filename="", fileobj=raw, mode="wb", compresslevel=9, mtime=0) as zipped:
            with tarfile.open(fileobj=zipped, mode="w", format=tarfile.GNU_FORMAT) as normalized:
                for info, content in payloads:
                    normalized.addfile(info, io.BytesIO(content) if content is not None else None)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--epoch", required=True, type=int)
    args = parser.parse_args()
    normalize(args.source, args.destination, args.epoch)
    print(f"normalized {args.source.name} -> {args.destination.name} at epoch {args.epoch}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
