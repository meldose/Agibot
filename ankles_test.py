#!/usr/bin/env python3
"""Measure ankle pitch and roll during a short coordinated locomotion test."""

from test_knees import main

ANKLES = tuple(
    f"{side}_ankle_{axis}_joint"
    for side in ("left", "right")
    for axis in ("pitch", "roll")
)


if __name__ == "__main__":
    raise SystemExit(main(__doc__, __file__, ANKLES, "agibot_test_ankles"))
