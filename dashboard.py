#!/usr/bin/env python3
"""Display live AGIBOT telemetry in an SSH terminal."""

import argparse
from collections import deque
from datetime import datetime
import math
import os
from pathlib import Path
from select import select
import sys
import termios
import time
import tty

from robot_dashboard import Telemetry


class Feed:
    def __init__(self, callback):
        self.callback = callback
        self.received = deque(maxlen=8192)

    def receive(self, message):
        self.received.append(time.monotonic())
        self.callback(message)

    def status(self, sample, now, publishers):
        cutoff = time.monotonic() - 5
        while self.received and self.received[0] < cutoff:
            self.received.popleft()
        age = None if sample is None else max(0, now - sample["t"])
        if age is not None and age <= 3:
            state = f"Receiving · sample age {age:.1f} s"
        elif age is not None:
            state = f"Stale · sample age {age:.1f} s"
        else:
            state = "Publisher matched" if publishers else "Discovering"
        return f"{state} · {publishers} matched · {len(self.received) / 5:.1f} msg/s (5 s avg)"


class WalkingTest:
    def __init__(self):
        self.started = None
        self.stopped = None
        self.baseline = None
        self.latest = None
        self.peak = None
        self.events = deque(maxlen=8)
        self.seen_events = deque(maxlen=64)
        self.message = ""

    def start(self, snapshot):
        now = snapshot["now"]
        samples = snapshot["odometry"]
        if not samples or now - samples[-1]["t"] > 3:
            self.message = "Start needs a recent odometry sample."
            return
        self.__init__()
        self.started = now
        self.baseline = samples[-1]
        self.latest = self.baseline

    def update(self, snapshot):
        if self.started is None:
            return
        end = self.stopped if self.stopped is not None else snapshot["now"]
        start_text = datetime.fromtimestamp(self.started).strftime("%Y-%m-%d %H:%M:%S")
        end_text = datetime.fromtimestamp(end).strftime("%Y-%m-%d %H:%M:%S")
        for event in reversed(snapshot["events"]):
            if start_text <= event[:19] <= end_text and event not in self.seen_events:
                self.events.append(event)
                self.seen_events.append(event)
        if self.stopped is not None:
            return
        for sample in snapshot["odometry"]:
            if sample["t"] < self.started or sample["t"] <= self.latest["t"]:
                continue
            if sample["frame"] != self.baseline["frame"] or sample["t"] - self.latest["t"] > 3:
                self.message = "Test ended early because the odometry frame changed or data dropped out."
                self.stopped = self.latest["t"] if self.latest["t"] >= self.started else self.started
                return
            self.latest = sample
            self.peak = max(self.peak or 0, sample["speed"])

    def stop(self, snapshot):
        if self.started is None or self.stopped is not None:
            self.message = "Press S to start a test."
            return
        self.update(snapshot)
        if self.stopped is None:
            self.stopped = snapshot["now"]
            if self.stopped - self.latest["t"] > 3:
                self.message = "Odometry was stale at the end. Summary uses the last received sample."

    def lines(self, now):
        lines = ["", "Walking test"]
        if self.started is None:
            lines.append("  No test marked")
        else:
            end = self.stopped if self.stopped is not None else now
            status = "Complete" if self.stopped is not None else "Recording"
            lines.append(f"  {status} · {end - self.started:.1f} s · frame {self.baseline['frame']}")
            if self.peak is None:
                lines.append("  No odometry samples received during the test")
            else:
                dx = (self.latest["x"] - self.baseline["x"]) * 100
                dy = (self.latest["y"] - self.baseline["y"]) * 100
                lines.append(f"  ΔX {dx:+.2f} cm   ΔY {dy:+.2f} cm   "
                             f"Net {math.hypot(dx, dy):.2f} cm   Sampled peak {self.peak:.3f} m/s")
            lines.extend(f"  {event}" for event in reversed(self.events))
            if not self.events:
                lines.append("  No matching controller events in the log tail")
        if self.message:
            lines.append(f"  {self.message}")
        return lines


def render(snapshot, walking_test, interactive):
    lines = ["AGIBOT live telemetry", "", "Pelvis odometry"]
    odometry = snapshot["odometry"]
    joints = snapshot["joints"]
    now = snapshot["now"]
    lines.append("  " + snapshot["odom_status"])
    if odometry:
        sample = odometry[-1]
        lines.extend([
            f"  X {sample['x']:+.3f} m   Y {sample['y']:+.3f} m   "
            f"Speed {sample['speed']:.3f} m/s",
            f"  Frame {sample['frame']}",
        ])

    lines.extend(["", "Leg joint angles", "  " + snapshot["joint_status"]])
    if joints:
        sample = joints[-1]
        lines.extend(f"  {name:<28} {angle:+.3f} rad"
                     for name, angle in sorted(sample["angles"].items()))

    if interactive:
        lines.extend(walking_test.lines(now))
        lines.append("  S start or restart · E end · Q quit")

    lines.extend(["", "Controller events (MDU local time)"])
    if snapshot["log"]:
        lines.append(f"  {snapshot['log']}")
    lines.extend(f"  {event}" for event in snapshot["events"][:5])
    if not snapshot["events"]:
        lines.append("  No recent policy changes or warnings in the log tail")

    # Keep terminal controls found in log messages from being executed.
    return "\n".join("".join(char for char in line if char.isprintable())
                     for line in lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log-dir", type=Path, default=Path("/agibot/log/mc"))
    parser.add_argument("--domain", type=int, default=232, help="ROS domain ID (default: 232)")
    parser.add_argument("--once", action="store_true", help="print one snapshot and exit")
    args = parser.parse_args()
    os.environ["ROS_DOMAIN_ID"] = str(args.domain)
    os.environ.pop("ROS_LOCALHOST_ONLY", None)
    os.environ["ROS_AUTOMATIC_DISCOVERY_RANGE"] = "SUBNET"

    try:
        import rclpy
        from nav_msgs.msg import Odometry
        from rclpy.executors import ExternalShutdownException
        from rclpy.qos import qos_profile_sensor_data
        from sensor_msgs.msg import JointState
    except ImportError as exc:
        parser.exit(1, f"{exc}. Source /opt/ros/jazzy/setup.bash first.\n")

    telemetry = Telemetry(args.log_dir)
    odom_feed = Feed(telemetry.on_odometry)
    joint_feed = Feed(telemetry.on_joints)
    walking_test = WalkingTest()
    rclpy.init()
    node = None
    interactive = sys.stdin.isatty() and sys.stdout.isatty() and not args.once
    terminal_settings = None
    try:
        if interactive:
            terminal_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin)
        node = rclpy.create_node("agibot_terminal_dashboard")
        odom_subscription = node.create_subscription(
            Odometry, "/legged_odometry_node/legged_odometry",
            odom_feed.receive, qos_profile_sensor_data,
        )
        joint_subscription = node.create_subscription(
            JointState, "/motion/control/leg_joint_state",
            joint_feed.receive, qos_profile_sensor_data,
        )
        next_refresh = time.monotonic() + (3 if args.once else 0)
        while rclpy.ok():
            key = b""
            if interactive and select([sys.stdin], [], [], 0)[0]:
                key = os.read(sys.stdin.fileno(), 1).lower()
                if key in (b"q", b""):
                    break
            remaining = next_refresh - time.monotonic()
            if remaining > 0 and key not in (b"s", b"e"):
                rclpy.spin_once(node, timeout_sec=min(remaining, 0.2))
                continue
            prefix = "\033[H\033[2J" if interactive else ""
            snapshot = telemetry.snapshot()
            now = snapshot["now"]
            snapshot["odom_status"] = odom_feed.status(
                next(iter(snapshot["odometry"][-1:]), None), now,
                odom_subscription.get_publisher_count(),
            )
            snapshot["joint_status"] = joint_feed.status(
                next(iter(snapshot["joints"][-1:]), None), now,
                joint_subscription.get_publisher_count(),
            )
            if key == b"s":
                walking_test.start(snapshot)
            elif key == b"e":
                walking_test.stop(snapshot)
            walking_test.update(snapshot)
            print(prefix + render(snapshot, walking_test, interactive), flush=True)
            if args.once:
                break
            next_refresh = time.monotonic() + 1
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if terminal_settings is not None:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, terminal_settings)
        if node is not None:
            node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
