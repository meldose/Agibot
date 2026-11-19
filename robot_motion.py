#!/usr/bin/env python3
"""Request playback of an installed A3 Ultra motion resource.

Example (the documented handshake resource):
    python3 robot_motion.py /agibot/data/resources/default/motion/handshake/woshou1_Skeleton0.mcap --execute
"""

import argparse
import sys

import requests

from robot import Robot


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("motion_id", help="absolute path of a motion resource installed on the robot")
    parser.add_argument("--duration-ms", type=int, default=10000, help="playback duration")
    parser.add_argument("--ip", default="192.168.2.196")
    parser.add_argument("--execute", action="store_true", help="send the motion command")
    return parser.parse_args()


def main():
    args = parse_args()
    if not args.execute:
        print("DRY RUN: no motion command sent. Add --execute after safety checks.")
        return 2
    print("Make sure the robot has clear space and no person is within its movement range.")
    if input("Type PLAY to start this motion: ").strip() != "PLAY":
        print("Cancelled; no motion command sent.")
        return 1

    robot = Robot(ip=args.ip)
    try:
        print(robot.play_motion(args.motion_id, args.duration_ms))
    except (requests.RequestException, RuntimeError, ValueError) as exc:
        print(f"Motion RPC failed: {exc}", file=sys.stderr)
        return 1
    finally:
        robot.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
