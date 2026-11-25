#!/usr/bin/env python3
"""Observe individual finger positions during a grasp or release."""

from body_feedback import joint_test


if __name__ == "__main__":
    raise SystemExit(joint_test(
        __doc__, "agibot_hand_feedback", __file__,
        "/motion/control/hand_joint_state", "device units", float,
    ))
