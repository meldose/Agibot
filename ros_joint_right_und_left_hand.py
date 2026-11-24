#!/usr/bin/env python3
"""Preview or publish finger bend targets using the SDK ROS format."""

import argparse
import json
import os
import subprocess
import time

from test_o10_both import NAMES, TOPIC

BEND_JOINTS = [name for name in NAMES if "_bent" in name]
PUBLISH_RATE = 5
FINGERS = {
    "thumb": "thumb_bent_2",
    "index": "index_bent_1",
    "middle": "middle_bent",
    "ring": "ring_bent_1",
    "pinky": "pinky_bent_1",
}


def sdk_position(value):
    try:
        position = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("expected an integer") from error
    if not 0 <= position <= 4095:
        raise argparse.ArgumentTypeError("expected a position in 0–4095")
    return position


def publish_pose(pose, hold_seconds):
    environment = dict(os.environ)
    environment.pop("ROS_LOCALHOST_ONLY", None)
    environment.update(ROS_DOMAIN_ID="232", ROS_AUTOMATIC_DISCOVERY_RANGE="SUBNET",
                       RMW_IMPLEMENTATION="rmw_fastrtps_cpp")
    message = {
        "header": {"stamp": "now", "frame_id": "O10Hand"},
        "name": NAMES,
        "position": list(map(float, pose)),
    }
    options = ["--once"]
    if hold_seconds:
        options = ["--rate", str(PUBLISH_RATE), "--times", str(hold_seconds * PUBLISH_RATE),
                   "--print", str(PUBLISH_RATE)]
    try:
        result = subprocess.run([
            "ros2", "topic", "pub", *options, "--wait-matching-subscriptions", "1",
            "--max-wait-time-secs", "8", TOPIC, "sensor_msgs/msg/JointState",
            json.dumps(message),
        ], env=environment)
    except KeyboardInterrupt:
        print("Publishing stopped.")
        raise SystemExit(130)
    if result.returncode:
        raise SystemExit(result.returncode)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("hand", nargs="?", choices=("left", "right", "both"))
    parser.add_argument("finger", nargs="?", choices=(*FINGERS, "all", "grip"))
    parser.add_argument("--baseline", type=sdk_position, nargs=len(NAMES),
                        required=True, metavar="POS", help="current commanded positions in SDK order")
    parser.add_argument("--target", type=sdk_position,
                        help="calibrated bend target for a single hand")
    parser.add_argument("--left-target", type=sdk_position, help="left target in both mode")
    parser.add_argument("--right-target", type=sdk_position, help="right target in both mode")
    parser.add_argument("--targets", type=sdk_position, nargs=5, metavar="POS",
                        help="targets for all or grip mode in thumb, index, middle, ring, pinky order")
    parser.add_argument("--joint", choices=BEND_JOINTS,
                        help="bend joint to test (default: right_index_bent_1)")
    parser.add_argument("--hold-seconds", type=int, default=0, metavar="SECONDS",
                        help="repeat the target at 5 Hz for a timed hold")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.hold_seconds < 0:
        parser.error("--hold-seconds must be zero or a positive integer")
    if bool(args.hand) != bool(args.finger):
        parser.error("specify both hand and finger")
    if args.hand and args.joint:
        parser.error("use either hand and finger or --joint")
    if args.finger in ("all", "grip"):
        if args.hand == "both" or args.targets is None or any(
            target is not None for target in (args.target, args.left_target, args.right_target)
        ):
            parser.error("all and grip require left or right and five values through --targets")
        poses = []
        grip = args.baseline.copy()
        for suffix, target in zip(FINGERS.values(), args.targets, strict=True):
            joint = f"{args.hand}_{suffix}"
            index = NAMES.index(joint)
            previous = args.baseline[index]
            if target == previous:
                parser.error(f"the target for {joint} must differ from its baseline")
            pose = args.baseline.copy()
            pose[index] = target
            grip[index] = target
            poses.append((f"{joint}: {previous} -> {target}", pose))
        if args.finger == "grip":
            poses = [("\n".join(description for description, _ in poses), grip)]
        run_sequence(args, poses)
        return
    if args.targets is not None:
        parser.error("--targets is only for all or grip mode")
    if args.hand == "both":
        if args.target is not None or None in (args.left_target, args.right_target):
            parser.error("both requires --left-target and --right-target")
        suffix = FINGERS[args.finger]
        targets = {f"left_{suffix}": args.left_target, f"right_{suffix}": args.right_target}
    else:
        if args.target is None or args.left_target is not None or args.right_target is not None:
            parser.error("single-hand mode requires --target")
        joint = f"{args.hand}_{FINGERS[args.finger]}" if args.hand else (
            args.joint or "right_index_bent_1"
        )
        targets = {joint: args.target}

    for joint, target in targets.items():
        index = NAMES.index(joint)
        previous = args.baseline[index]
        if previous == target:
            parser.error(f"the target for {joint} must differ from its baseline")
        args.baseline[index] = target
        print(f"{joint}: {previous} -> {target}", flush=True)
    if args.hold_seconds:
        print(f"Timed hold: {args.hold_seconds} seconds at {PUBLISH_RATE} Hz.", flush=True)
    if not args.execute:
        print("Preview only. No command sent.")
        return

    print("Confirm the robot is stationary, the drive is ready, playback has released "
          "control, both hands are clear, and the baseline is current.")
    if input("Type TEST to publish: ").strip() != "TEST":
        print("No command sent.")
        return

    publish_pose(args.baseline, args.hold_seconds)


def run_sequence(args, poses):
    for description, _ in poses:
        print(description)
    if not args.execute:
        print("Preview only. No command sent.")
        return
    print("Confirm the robot is stationary, the drive is ready, playback has released "
          "control, both hands are clear, and the baseline is current.")
    if input("Type TEST to start: ").strip() != "TEST":
        print("No command sent.")
        return
    try:
        for number, (description, pose) in enumerate(poses):
            if number:
                time.sleep(3)
            print(f"Testing {description}", flush=True)
            publish_pose(pose, args.hold_seconds)
    except KeyboardInterrupt:
        print("Sequence stopped.")


if __name__ == "__main__":
    main()
