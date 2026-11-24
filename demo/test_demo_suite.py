"""A test suite with known flakiness, used to generate realistic CI data for FlakeRadar.

40 tests always pass. 20 tests fail at random with a fixed probability (2%, 5%, 10%, 20% or
40%), defined in ground_truth.json, so the detector's accuracy can be measured.

Run: pytest demo --junitxml=demo-report.xml
Set DEMO_SEED to make a run repeatable.
"""

import json
import os
import random
from pathlib import Path

import pytest

GROUND_TRUTH = json.loads((Path(__file__).parent / "ground_truth.json").read_text())
_rng = random.Random(os.environ.get("DEMO_SEED"))


@pytest.mark.parametrize(
    "probability",
    [pytest.param(t["failure_probability"], id=t["name"]) for t in GROUND_TRUTH["tests"]],
)
def test_case(probability: float) -> None:
    if _rng.random() < probability:
        pytest.fail(f"Simulated intermittent failure (probability {probability:.0%})")
