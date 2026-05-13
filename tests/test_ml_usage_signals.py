"""Unit tests for active vs passive ML wording heuristics."""

from tools.ml_usage_signals import is_active_ml_usage
from tools.paper_role_classifier import has_strong_ml_signal


def test_passive_emulator_without_active_phrases_not_active() -> None:
    t = (
        "We compare simulation predictions to those from current cosmological emulators "
        "for galaxy cluster gas."
    )
    assert has_strong_ml_signal(t)
    assert not is_active_ml_usage(t, has_strong_ml=has_strong_ml_signal(t))


def test_using_machine_learning_counts_as_active() -> None:
    t = "The calibration is performed using machine learning for cluster feedback models."
    assert is_active_ml_usage(t, has_strong_ml=has_strong_ml_signal(t))


def test_build_trained_emulator_counts_as_active() -> None:
    t = "We build an emulator trained on hydrodynamical simulations of galaxy clusters."
    assert is_active_ml_usage(t, has_strong_ml=has_strong_ml_signal(t))
