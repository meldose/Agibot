#!/usr/bin/env python3
"""Preview or move one A3 Ultra wrist axis."""

import argparse

import test_elbow


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("side", choices=("left", "right"))
    parser.add_argument("axis", choices=("roll", "pitch", "yaw"))
    parser.add_argument("--delta-deg", type=float, default=1.0,
                        help=f"signed relative angle, up to {test_elbow.MAX_DELTA_DEG}°")
    parser.add_argument("--execute", action="store_true",
                        help="send motion with the robot in MOTION and motion_player stopped")
    args = parser.parse_args()
    joint_args = [args.side, "--joint", f"wrist_{args.axis}", "--delta-deg", str(args.delta_deg)]
    if args.execute:
        joint_args.append("--execute")
    return test_elbow.main(joint_args)


if __name__ == "__main__":
    raise SystemExit(main())
