#!/usr/bin/env python3
"""Inspect or change A3 Ultra speaker volume.

Examples:
    python3 robot_audio.py status
    python3 robot_audio.py set-volume 40 --apply
"""

import argparse
import sys

import requests

from robot import Robot


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("status", "set-volume"))
    parser.add_argument("volume", nargs="?", type=int, help="0 to 70; required by set-volume")
    parser.add_argument("--ip", default="192.168.2.196")
    parser.add_argument("--apply", action="store_true", help="permit a volume change")
    parser.add_argument("--mute", action="store_true", help="mute when setting volume")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.command == "set-volume":
        if args.volume is None:
            print("set-volume requires a value from 0 to 70", file=sys.stderr)
            return 2
        if not args.apply:
            print("DRY RUN: add --apply to change speaker volume.")
            return 2
        if input(f"Set speaker volume to {args.volume}? Type APPLY: ").strip() != "APPLY":
            print("Cancelled; no change sent.")
            return 1

    robot = Robot(ip=args.ip)
    try:
        if args.command == "status":
            print(robot.get_audio_volume())
        else:
            print(robot.set_audio_volume(args.volume, mute=args.mute))
    except (requests.RequestException, RuntimeError, ValueError) as exc:
        print(f"Audio RPC failed: {exc}", file=sys.stderr)
        return 1
    finally:
        robot.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
