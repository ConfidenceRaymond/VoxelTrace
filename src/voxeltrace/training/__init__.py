"""Ground truth, multimodal example generation, splits, validation and export.

DEVELOPMENT/EVALUATION infrastructure. No model training happens in this package.
"""

from voxeltrace.training.schema import (
    SOURCE_LEVEL,
    DatasetManifest,
    DatasetSplit,
    GroundTruthCase,
    GroundTruthLesion,
    GTValue,
    TrainingExample,
    gt,
)

__all__ = [
    "SOURCE_LEVEL",
    "DatasetManifest",
    "DatasetSplit",
    "GTValue",
    "GroundTruthCase",
    "GroundTruthLesion",
    "TrainingExample",
    "gt",
]
