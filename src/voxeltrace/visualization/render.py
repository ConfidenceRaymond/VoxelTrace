"""Core rendering primitives: exact coordinate mappings, colour maps, PNG output, footer.

Conventions (docs/visualization.md):
- Volumes are ``[k, j, i]`` (slice, row, column); DICOM affine maps (i, j, k) -> LPS mm.
- Axial rendering supports only the standard axial orientation
  ImageOrientationPatient = (1,0,0, 0,1,0); anything else raises RenderError (no silent
  reorientation).
- RADIOLOGICAL convention (default): image left = patient RIGHT, image top = ANTERIOR.
  For the standard orientation this is the natural array layout (i -> image x, j -> image y).
  NEUROLOGICAL convention mirrors x (image left = patient LEFT).
- Each voxel becomes an exact fx × fy block of pixels (nearest-neighbour). There is no
  interpolation of quantitative images, and the image region is never modified by text: labels
  and the scale bar go in a footer strip appended BELOW the image, so pixel coordinates
  inside the image region are unaffected.
- Display normalisation (window/colour map) is recorded in RenderParams and never written
  back to quantitative arrays.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from typing import Literal

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, Field

from voxeltrace.schemas import ImageGeometry

RENDERER_VERSION = "vt-render-1"
Convention = Literal["radiological", "neurological"]
STANDARD_AXIAL = np.array([1.0, 0, 0, 0, 1.0, 0])


class RenderError(ValueError):
    pass


class RenderParams(BaseModel):
    renderer_version: str = RENDERER_VERSION
    view: str
    convention: Convention = "radiological"
    scale_x: int = Field(description="pixels per voxel along image x")
    scale_y: int = Field(description="pixels per voxel along image y")
    mm_per_px_x: float
    mm_per_px_y: float
    crop_voxels: list[int] | None = Field(default=None, description="[a0, b0, a1, b1] inclusive")
    pet_window: list[float] | None = None
    pet_colormap: str | None = None
    ct_window_center_width: list[float] | None = None
    pet_alpha: float | None = None
    overlays: list[str] = Field(default_factory=list)
    resampling: str = "none (nearest-neighbour voxel blocks)"
    notes: list[str] = Field(default_factory=list)


def require_standard_axial(g: ImageGeometry) -> None:
    d = np.asarray(g.direction).reshape(3, 3)
    iop = np.concatenate([d[:, 0], d[:, 1]])
    if np.abs(iop - STANDARD_AXIAL).max() > 1e-4:
        raise RenderError(f"non-standard orientation {iop.round(4).tolist()} not supported")
    if g.spacing_ijk[2] is None:
        raise RenderError("non-uniform slice spacing")


# --------------------------------------------------------------------------------------
# Coordinates
# --------------------------------------------------------------------------------------


def voxel_to_patient(g: ImageGeometry, kji: tuple[float, float, float]) -> tuple[float, ...]:
    k, j, i = kji
    return tuple(float(v) for v in (np.asarray(g.affine) @ [i, j, k, 1.0])[:3])


def patient_to_voxel(g: ImageGeometry, xyz: tuple[float, float, float]) -> tuple[float, ...]:
    """Continuous (k, j, i) for a patient LPS point (inverse affine)."""
    ijk = np.linalg.solve(np.asarray(g.affine), [*xyz, 1.0])[:3]
    return float(ijk[2]), float(ijk[1]), float(ijk[0])


@dataclass(frozen=True)
class PlaneMapping:
    """Exact map between 2-D voxel indices (a = image-x axis, b = image-y axis) and pixels.

    Axial: a = i (column), b = j (row). Coronal MIP: a = i, b = k (flipped: superior on top).
    Voxel (a, b) occupies pixels x in [xa, xa + sx - 1], y in [yb, yb + sy - 1].
    """

    a0: int
    b0: int
    n_a: int
    n_b: int
    sx: int
    sy: int
    flip_x: bool = False
    flip_y: bool = False

    @property
    def width(self) -> int:
        return self.n_a * self.sx

    @property
    def height(self) -> int:
        return self.n_b * self.sy

    def _da(self, a: int) -> int:
        d = a - self.a0
        return self.n_a - 1 - d if self.flip_x else d

    def _db(self, b: int) -> int:
        d = b - self.b0
        return self.n_b - 1 - d if self.flip_y else d

    def contains(self, a: int, b: int) -> bool:
        return 0 <= a - self.a0 < self.n_a and 0 <= b - self.b0 < self.n_b

    def voxel_block(self, a: int, b: int) -> tuple[int, int, int, int]:
        """Inclusive pixel block [x0, y0, x1, y1] of voxel (a, b)."""
        if not self.contains(a, b):
            raise RenderError(f"voxel ({a}, {b}) outside rendered region")
        x0, y0 = self._da(a) * self.sx, self._db(b) * self.sy
        return x0, y0, x0 + self.sx - 1, y0 + self.sy - 1

    def voxel_to_px(self, a: int, b: int) -> tuple[int, int]:
        """Integer pixel at the centre of the voxel block (floor of the block centre)."""
        x0, y0, _, _ = self.voxel_block(a, b)
        return x0 + self.sx // 2, y0 + self.sy // 2

    def px_to_voxel(self, x: int, y: int) -> tuple[int, int]:
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise RenderError(f"pixel ({x}, {y}) outside image")
        da, db = x // self.sx, y // self.sy
        a = self.n_a - 1 - da if self.flip_x else da
        b = self.n_b - 1 - db if self.flip_y else db
        return a + self.a0, b + self.b0

    def voxel_box_to_px(self, a_lo: int, b_lo: int, a_hi: int, b_hi: int) -> list[int]:
        corners = [self.voxel_block(a, b) for a in (a_lo, a_hi) for b in (b_lo, b_hi)]
        return [
            min(c[0] for c in corners),
            min(c[1] for c in corners),
            max(c[2] for c in corners),
            max(c[3] for c in corners),
        ]

    def expand(self, plane: np.ndarray) -> np.ndarray:
        """[b, a] voxel plane (already cropped) -> pixel plane via exact block repetition."""
        p = plane[:, ::-1] if self.flip_x else plane
        p = p[::-1, :] if self.flip_y else p
        return np.repeat(np.repeat(p, self.sy, axis=0), self.sx, axis=1)


# --------------------------------------------------------------------------------------
# Colour
# --------------------------------------------------------------------------------------


def _lut(name: str) -> np.ndarray:
    t = np.arange(256) / 255.0
    if name == "gray":
        rgb = np.stack([t, t, t], 1)
    elif name == "gray_inverted":
        rgb = np.stack([1 - t, 1 - t, 1 - t], 1)
    elif name == "hot":
        rgb = np.stack(
            [np.clip(3 * t, 0, 1), np.clip(3 * t - 1, 0, 1), np.clip(3 * t - 2, 0, 1)], 1
        )
    else:
        raise RenderError(f"unknown colour map {name}")
    return np.round(rgb * 255).astype(np.uint8)


def window_index(values: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """Deterministic 0..255 display index (display only; input untouched)."""
    if not hi > lo:
        raise RenderError("window upper bound must exceed lower bound")
    norm = np.clip((np.asarray(values, dtype=np.float64) - lo) / (hi - lo), 0.0, 1.0)
    return np.floor(norm * 255.0 + 0.5).astype(np.uint8)


def colorize(values: np.ndarray, lo: float, hi: float, cmap: str) -> np.ndarray:
    return _lut(cmap)[window_index(values, lo, hi)]


# --------------------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------------------


def png_bytes(rgb: np.ndarray) -> bytes:
    if rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[2] != 3:
        raise RenderError("expected uint8 RGB image")
    buf = io.BytesIO()
    Image.fromarray(rgb, "RGB").save(buf, format="PNG", optimize=False, compress_level=6)
    return buf.getvalue()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _font(size: int = 12):
    return ImageFont.load_default(size=size)


def add_footer(
    rgb: np.ndarray, lines: list[str], *, mm_per_px: float, scale_bar_mm: float | None = None
) -> np.ndarray:
    """Append a footer strip below the image (image pixels unchanged)."""
    h, w, _ = rgb.shape
    line_h = 15
    fh = 8 + line_h * len(lines) + (18 if scale_bar_mm else 0)
    footer = Image.new("RGB", (w, fh), (0, 0, 0))
    draw = ImageDraw.Draw(footer)
    y = 4
    if scale_bar_mm:
        length = int(round(scale_bar_mm / mm_per_px))
        draw.rectangle([6, y + 4, 6 + length - 1, y + 7], fill=(255, 255, 255))
        draw.text((12 + length, y), f"{scale_bar_mm:g} mm", fill=(255, 255, 255), font=_font())
        y += 18
    for line in lines:
        draw.text((6, y), line, fill=(230, 230, 230), font=_font())
        y += line_h
    return np.concatenate([rgb, np.asarray(footer, dtype=np.uint8)], axis=0)
