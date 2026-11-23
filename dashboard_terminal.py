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
from robot_dashboard_recording import recent_tests, save_test
from robot_dashboard_status import TOPICS, health_lines, status_callback


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
        self.odometry = []
        self.joints = []
        self.events = []
        self.seen_events = set()
        self.saved = None
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
        self.odometry.append(self.baseline)

    def update(self, snapshot):
        if self.started is None:
            return
        end = self.stopped if self.stopped is not None else snapshot["now"]
        start_text = datetime.fromtimestamp(self.started).strftime("%Y-%m-%d %H:%M:%S")
        end_text = datetime.fromtimestamp(end).strftime("%Y-%m-%d %H:%M:%S")
        for event in reversed(snapshot["events"]):
            if start_text <= event[:19] <= end_text and event not in self.seen_events:
                self.events.append(event)
                self.seen_events.add(event)
        if self.stopped is not None:
            return
        last_joint = self.joints[-1]["t"] if self.joints else self.started
        self.joints.extend(sample for sample in snapshot["joints"] if last_joint < sample["t"])
        for sample in snapshot["odometry"]:
            if sample["t"] < self.started or sample["t"] <= self.latest["t"]:
                continue
            if sample["frame"] != self.baseline["frame"] or sample["t"] - self.latest["t"] > 3:
                self.message = "Test ended early because the odometry frame changed or data dropped out."
                self.stopped = self.latest["t"] if self.latest["t"] >= self.started else self.started
                self.joints = [row for row in self.joints if row["t"] <= self.stopped]
                return
            self.latest = sample
            self.odometry.append(sample)
            self.peak = max(self.peak or 0, sample["speed"])
        if end - self.started >= 1800:
            self.stopped = end
            self.message = "Test reached the 30-minute recording limit."

    def stop(self, snapshot):
        if self.saved is False:
            self.saved = None
            self.message = ""
            return
        if self.started is None or self.stopped is not None:
            self.message = "Press S to start a test."
            return
        self.update(snapshot)
        if self.stopped is None:
            self.stopped = snapshot["now"]
            if self.stopped - self.latest["t"] > 3:
                self.message = "Odometry was stale at the end. Summary uses the last received sample."

    def summary(self):
        if self.peak is None:
            return "No odometry samples received during the test"
        dx = (self.latest["x"] - self.baseline["x"]) * 100
        dy = (self.latest["y"] - self.baseline["y"]) * 100
        return (f"ΔX {dx:+.2f} cm   ΔY {dy:+.2f} cm   "
                f"Net {math.hypot(dx, dy):.2f} cm   Sampled peak {self.peak:.3f} m/s")

    def lines(self, now):
        lines = ["", "Walking test"]
        if self.started is None:
            lines.append("  No test marked")
        else:
            end = self.stopped if self.stopped is not None else now
            status = "Complete" if self.stopped is not None else "Recording"
            lines.append(f"  {status} · {end - self.started:.1f} s · frame {self.baseline['frame']}")
            lines.append("  " + self.summary())
            if self.saved:
                lines.append(f"  Saved {self.saved}")
            lines.extend(f"  {event}" for event in reversed(self.events[-5:]))
            if not self.events:
                lines.append("  No matching controller events in the log tail")
        if self.message:
            lines.append(f"  {self.message}")
        return lines


def sparkline(samples, now, value):
    bins = [None] * 30
    for sample in samples:
        age = now - sample["t"]
        reading = value(sample)
        if reading is not None and 0 <= age < 30:
            bins[29 - int(age)] = reading
    values = [value for value in bins if value is not None]
    if not values:
        return "Waiting for samples"
    lo, hi = min(values), max(values)
    bars = "▁▂▃▄▅▆▇█"
    return "".join("·" if value is None else bars[round(7 * (value - lo) / (hi - lo))]
                   if hi > lo else "▄" for value in bins)


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
        angles = [f"{name} {angle:+.3f} rad" for name, angle in sorted(sample["angles"].items())]
        lines.extend("  " + "   ".join(angles[index:index + 2])
                     for index in range(0, len(angles), 2))

    lines.extend(["", "Trends · last 30 seconds", f"  Speed   {sparkline(odometry, now, lambda row: row['speed'])}"])
    names = sorted(joints[-1]["angles"]) if joints else []
    knees = [name for name in names if "knee" in name.lower()]
    for name in knees[:2] or names[:1]:
        trend = sparkline(joints, now, lambda row: row["angles"].get(name))
        lines.append(f"  {name}   {trend}")

    lines.extend(["", "Robot status", *snapshot["robot_status"]])
    lines.extend(["", "Health", *snapshot["health"]])

    if interactive:
        lines.extend(walking_test.lines(now))
        lines.append("  S start or restart · E end · Q quit")
        if snapshot["past_tests"]:
            lines.extend(["", "Recent saved tests", *snapshot["past_tests"]])

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
    parser.add_argument("--output-dir", type=Path, default=Path("/agibot/dashboard_tests"))
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
    robot_status = {}
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
        subscriptions = {}
        try:
            from ros2_plugin_proto.msg import RosMsgWrapper
            for kind, topic in TOPICS.items():
                subscriptions[kind] = node.create_subscription(
                    RosMsgWrapper, topic, status_callback(robot_status, kind), qos_profile_sensor_data,
                )
        except (ImportError, RuntimeError) as exc:
            status_error = f"AimRT message support unavailable ({exc})"
        else:
            status_error = None
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
            snapshot["robot_status"] = [f"  {status_error}"] if status_error else []
            for kind, subscription in subscriptions.items():
                if kind in robot_status:
                    stamp, value = robot_status[kind]
                    age = time.monotonic() - stamp
                    state = f"{value} · {age:.1f} s old" + (" (stale)" if age > 3 else "")
                else:
                    state = f"Waiting · {subscription.get_publisher_count()} matched"
                snapshot["robot_status"].append(f"  {kind} · {state}")
            snapshot["health"] = health_lines()
            if key == b"s":
                walking_test.start(snapshot)
            elif key == b"e":
                walking_test.stop(snapshot)
            walking_test.update(snapshot)
            if walking_test.stopped is not None and walking_test.saved is None:
                try:
                    walking_test.saved = save_test(args.output_dir, walking_test, walking_test.summary())
                except OSError as exc:
                    walking_test.message = f"Save failed: {exc}. Press E to retry."
                    walking_test.saved = False
            snapshot["past_tests"] = recent_tests(args.output_dir)
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
