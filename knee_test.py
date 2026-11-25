#!/usr/bin/env python3
"""Measure each knee during a short coordinated locomotion test on the HDU."""

from math import degrees, isfinite
from pathlib import Path
import signal
import subprocess
import sys

from body_feedback import RangeReport, duration, feedback_parser, sample
from walk_forward import load_ros_environment

TOPIC = "/motion/control/leg_joint_state"
KNEES = ("left_knee_joint", "right_knee_joint")


def knee_angles(message):
    if len(message.name) != len(message.position):
        return {}
    positions = dict(zip(message.name, message.position))
    return {name: degrees(positions[name]) for name in KNEES
            if name in positions and isfinite(positions[name])}


def main():
    parser = feedback_parser(__doc__)
    parser.set_defaults(seconds=12)
    parser.add_argument("--direction", choices=("left", "right", "forward", "backward"),
                        default="right", help="coordinated movement (default: right turn)")
    parser.add_argument("--execute", action="store_true",
                        help="run a one-second locomotion test after both knees report feedback")
    args = parser.parse_args()
    seconds = duration(parser, args)
    if args.execute and seconds < 8:
        parser.error("--execute needs at least 8 seconds to discover the controller and observe movement")

    load_ros_environment(__file__)
    from sensor_msgs.msg import JointState

    motion = None
    observed_names = set()

    class KneeReport(RangeReport):
        def receive(self, message):
            nonlocal motion
            observed_names.update(message.name)
            super().receive(message)
            if args.execute and motion is None and len(knee_angles(message)) == len(KNEES):
                motion = subprocess.Popen([
                    sys.executable, str(Path(__file__).with_name("walk_forward.py")),
                    "--execute", "--direction", args.direction, "--scale", "0.10", "--duration", "1",
                ], start_new_session=True)

        def show(self):
            super().show()
            missing = [name for name in KNEES if name not in self.ranges]
            if missing:
                print(f"Knee feedback missing for {', '.join(missing)}.")
                if observed_names:
                    print(f"Joint names received: {', '.join(sorted(observed_names))}")

    observer = KneeReport(lambda message: knee_angles(message).items())
    stopped = False
    try:
        status = sample("agibot_test_knees", seconds, [(TOPIC, JointState, observer)])
    finally:
        if motion is not None and motion.poll() is None:
            stopped = True
            motion.send_signal(signal.SIGINT)
            motion.wait(timeout=3)

    if status == 130:
        return 130
    if args.execute and motion is None:
        print("No motion sent because both knees did not report in the same sample.")
        return 1
    if stopped:
        print("The observation window ended while the locomotion script was still running.")
        return 1
    if motion is not None and motion.returncode:
        return motion.returncode
    return 0 if status == 0 and len(observer.ranges) == len(KNEES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
