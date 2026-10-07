"""Typed structured-evidence objects shared by the quant engine and the AI layer."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ImageStats(BaseModel):
    """Deterministic summary statistics of a numeric array.

    Counts and fractions describe the whole array. All intensity statistics
    (min/max/mean/std/median/percentiles) are computed over finite voxels only
    and are ``None`` when the array contains no finite voxels.
    """

    model_config = ConfigDict(frozen=True)

    shape: tuple[int, ...]
    dtype: str
    voxel_count: int = Field(ge=1)
    finite_count: int = Field(ge=0)
    nan_count: int = Field(ge=0)
    nan_fraction: float = Field(ge=0.0, le=1.0)
    posinf_count: int = Field(ge=0)
    neginf_count: int = Field(ge=0)
    zero_count: int = Field(ge=0)
    zero_fraction: float = Field(ge=0.0, le=1.0)
    finite_min: float | None
    finite_max: float | None
    finite_mean: float | None
    finite_std: float | None = Field(
        default=None, description="Population standard deviation (ddof=0)."
    )
    median: float | None
    p01: float | None = Field(description="1st percentile (linear interpolation).")
    p99: float | None = Field(description="99th percentile (linear interpolation).")

    @property
    def has_finite_voxels(self) -> bool:
        return self.finite_count > 0


class AIServerStatus(BaseModel):
    """Result of probing the local OpenAI-compatible endpoint."""

    base_url: str
    reachable: bool
    models: list[str] = Field(default_factory=list)
    error: str | None = None
