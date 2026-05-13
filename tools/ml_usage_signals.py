"""Heuristics for whether a paper describes active ML usage vs passive mentions (e.g. emulators in comparisons)."""

from __future__ import annotations

# Phrases that usually indicate the paper applies or builds ML, not only cites it.
_ACTIVE_ML_USAGE_PHRASES: tuple[str, ...] = (
    "we use machine learning",
    "we used machine learning",
    "using machine learning",
    "machine-learning approach",
    "machine learning algorithm",
    "machine learning algorithms",
    "machine learning technique",
    "machine learning techniques",
    "machine learning to",
    "machine learning for",
    "machine learning model",
    "machine learning models",
    "ml-based",
    "ml model",
    "ml models",
    "deep learning",
    "neural network",
    "neural networks",
    "random forest",
    "gradient boosting",
    "xgboost",
    "cnn",
    "convolutional neural network",
    "u-net",
    "unet",
    "supervised learning",
    "simulation-based inference",
    "we train",
    "we trained",
    "trained a",
    "trained with",
    "training a",
    "training the",
    "calibrate using",
    "calibrated using",
    "calibration using machine learning",
    "calibration is performed using machine learning",
    "predict using",
    "estimate using",
    "classify using",
    "detect using",
    "learned representation",
    "bayesian neural",
    "gaussian process emulator",
    "emulator trained",
    "trained emulator",
    "build an emulator",
    "construct an emulator",
    "develop an emulator",
    "emulator we",
)

# "Emulator" appears in cosmology papers as an external reference, not as the paper's method.
_PASSIVE_EMULATOR_CONTEXT_PHRASES: tuple[str, ...] = (
    "compare simulation predictions to",
    "compared to those from",
    "comparison to emulators",
    "compare to emulators",
    "compared to emulators",
    "cosmological emulators",
    "current cosmological emulators",
    "predictions from emulators",
    "predictions from cosmological emulators",
    "from cosmological emulators",
    "against cosmological emulators",
)


def is_active_ml_usage(text: str, *, has_strong_ml: bool) -> bool:
    """
    Return True if supplied text suggests the work *uses* ML (or builds/trains an emulator),
    not only compares to external emulators or mentions ML tools in passing.

    Callers should pass ``has_strong_ml`` from ``has_strong_ml_signal`` (or equivalent)
    so weak-only abstracts short-circuit cheaply.
    """
    if not has_strong_ml:
        return False
    t = text.lower()
    if any(p in t for p in _ACTIVE_ML_USAGE_PHRASES):
        return True
    if "emulator" not in t and "emulators" not in t:
        return True
    if any(p in t for p in _PASSIVE_EMULATOR_CONTEXT_PHRASES):
        return False
    return True
