#!/usr/bin/env python3
"""Observe leg joint angles during normal stepping or turning."""

from math import degrees
from body_feedback import joint_test


if __name__ == "__main__":
    raise SystemExit(joint_test(
        __doc__, "agibot_leg_feedback", __file__,
        "/motion/control/leg_joint_state", "deg", degrees,
    ))
