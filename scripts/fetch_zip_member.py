#!/usr/bin/env python3
"""Extract ONE small member (e.g. a metadata CSV) from a huge remote zip via HTTP range requests.

  fetch_zip_member.py <url> <member-name-suffix> <out-file> [--cap-mb 20]

Only the zip central directory and the requested member are read (byte-capped; the archive is
never downloaded). The URL is re-resolved for every request (signed redirects expire).
"""

from __future__ import annotations

import io
import sys
import urllib.request
import zipfile
from pathlib import Path


class RangeFile(io.RawIOBase):
    def __init__(self, url: str, cap: int) -> None:
        self.url, self.cap, self.pos, self.read_bytes = url, cap, 0, 0
        req = urllib.request.Request(url, headers={"Range": "bytes=0-0"})
        with urllib.request.urlopen(req, timeout=120) as r:  # noqa: S310 - explicit public URL
            self.size = int(r.headers["Content-Range"].split("/")[1])

    def seekable(self) -> bool:
        return True

    def readable(self) -> bool:
        return True

    def seek(self, off: int, whence: int = 0) -> int:
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off
        return self.pos

    def tell(self) -> int:
        return self.pos

    def read(self, n: int = -1) -> bytes:
        if n is None or n < 0:
            n = self.size - self.pos
        n = min(n, self.size - self.pos)
        if n <= 0:
            return b""
        if self.read_bytes + n > self.cap:
            raise RuntimeError(f"byte cap {self.cap} reached")
        req = urllib.request.Request(
            self.url, headers={"Range": f"bytes={self.pos}-{self.pos + n - 1}"}
        )
        with urllib.request.urlopen(req, timeout=120) as r:  # noqa: S310
            data = r.read()
        self.pos += len(data)
        self.read_bytes += len(data)
        return data


def main(argv: list[str]) -> int:
    url, suffix, out = argv[1], argv[2], Path(argv[3])
    cap = int(float(argv[argv.index("--cap-mb") + 1]) * 1e6) if "--cap-mb" in argv else 20_000_000
    f = RangeFile(url, cap)
    z = zipfile.ZipFile(f)  # type: ignore[arg-type]
    names = [n for n in z.namelist() if n.endswith(suffix)]
    print(f"archive {f.size / 1e9:.1f} GB, {len(z.namelist())} entries; matches: {names[:5]}")
    if len(names) != 1:
        return 2
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(z.read(names[0]))
    print(f"wrote {out} ({out.stat().st_size} bytes); transferred {f.read_bytes / 1e6:.2f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
