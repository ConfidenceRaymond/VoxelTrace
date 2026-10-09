"""Minimal, dependency-free, byte-reproducible text PDF (PDF 1.4, Helvetica / Courier).

No creation date, producer timestamp or random document ID is written, so the same input
gives the same bytes. Text outside Latin-1 is replaced with '?'. Markdown is rendered
plainly: '#' headings in bold, table rows in monospace, everything else as wrapped text.
"""

from __future__ import annotations

import textwrap

PAGE_W, PAGE_H, MARGIN = 595, 842, 50  # A4 in points


def _esc(s: str) -> str:
    s = s.encode("latin-1", "replace").decode("latin-1")
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _layout(markdown: str) -> list[list[tuple[str, int, str]]]:
    """-> pages of (font, size, text) lines."""
    lines: list[tuple[str, int, str]] = []
    in_code = False
    for raw in markdown.splitlines():
        if raw.startswith("```"):
            in_code = not in_code
            continue
        if in_code or raw.startswith("|"):
            if set(raw.replace("|", "").strip()) <= {"-", " "} and raw.startswith("|"):
                continue  # table separator row
            lines += [("F2", 7, w) for w in textwrap.wrap(raw, 118) or [""]]
        elif raw.startswith("#"):
            level = len(raw) - len(raw.lstrip("#"))
            size = {1: 15, 2: 12}.get(level, 10)
            lines += [("F1", 10, ""), ("F3", size, raw.lstrip("# ").strip())]
        else:
            lines += [("F1", 9, w) for w in textwrap.wrap(raw, 105) or [""]]
    pages, cur, y = [], [], PAGE_H - MARGIN
    for font, size, text in lines:
        if y - size * 1.35 < MARGIN:
            pages.append(cur)
            cur, y = [], PAGE_H - MARGIN
        y -= size * 1.35
        cur.append((font, size, text))
    pages.append(cur)
    return pages


def markdown_to_pdf(markdown: str, *, title: str = "VoxelTrace report") -> bytes:
    pages = _layout(markdown)
    objs: list[bytes] = []

    def add(b: bytes) -> int:
        objs.append(b)
        return len(objs)

    add(b"")  # 1 catalog (filled later)
    add(b"")  # 2 pages (filled later)
    f1 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    f2 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>")
    f3 = add(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"
    )
    kids = []
    for n, page in enumerate(pages, 1):
        y = PAGE_H - MARGIN
        ops = []
        for font, size, text in page:
            y -= size * 1.35
            ops.append(f"BT /{font} {size} Tf {MARGIN} {y:.2f} Td ({_esc(text)}) Tj ET")
        ops.append(f"BT /F1 7 Tf {MARGIN} 25 Td ({_esc(f'{title} - page {n}/{len(pages)}')}) Tj ET")
        stream = "\n".join(ops).encode("latin-1")
        c = add(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
        kids.append(add(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_W} {PAGE_H}] /Contents {c} 0 R "
            f"/Resources << /Font << /F1 {f1} 0 R /F2 {f2} 0 R /F3 {f3} 0 R >> >> >>".encode()
        ))  # fmt: skip
    objs[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objs[1] = (
        f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count {len(kids)} >>".encode()
    )
    info = add(f"<< /Title ({_esc(title)}) /Producer (VoxelTrace) >>".encode("latin-1"))
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{off:010d} 00000 n \n".encode() for off in offsets)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R /Info {info} 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)
