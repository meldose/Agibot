#!/usr/bin/env python3
"""Display live AGIBOT telemetry in an SSH terminal."""

import argparse
import os
from pathlib import Path
import sys
import time

from robot_dashboard import Telemetry


def render(snapshot):
    lines = ["AGIBOT live telemetry", "", "Pelvis odometry"]
    odometry = snapshot["odometry"]
    joints = snapshot["joints"]
    now = snapshot["now"]
    if odometry:
        sample = odometry[-1]
        age = now - sample["t"]
        lines.extend([
            f"  X {sample['x']:+.3f} m   Y {sample['y']:+.3f} m   "
            f"Speed {sample['speed']:.3f} m/s",
            f"  Frame {sample['frame']}   Sample age {age:.1f} s"
            + (" (stale)" if age > 3 else ""),
        ])
    else:
        lines.append(f"  Waiting for odometry · {snapshot.get('odom_publishers', 0)} matched publishers")

    lines.extend(["", "Leg joint angles"])
    if joints:
        sample = joints[-1]
        age = now - sample["t"]
        lines.append(f"  Sample age {age:.1f} s" + (" (stale)" if age > 3 else ""))
        lines.extend(f"  {name:<28} {angle:+.3f} rad"
                     for name, angle in sorted(sample["angles"].items()))
    else:
        lines.append(f"  Waiting for leg joint states · {snapshot.get('joint_publishers', 0)} matched publishers")

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
    rclpy.init()
    node = None
    interactive = sys.stdout.isatty() and not args.once
    try:
        node = rclpy.create_node("agibot_terminal_dashboard")
        odom_subscription = node.create_subscription(
            Odometry, "/legged_odometry_node/legged_odometry",
            telemetry.on_odometry, qos_profile_sensor_data,
        )
        joint_subscription = node.create_subscription(
            JointState, "/motion/control/leg_joint_state",
            telemetry.on_joints, qos_profile_sensor_data,
        )
        next_refresh = time.monotonic() + (3 if args.once else 0)
        while rclpy.ok():
            remaining = next_refresh - time.monotonic()
            if remaining > 0:
                rclpy.spin_once(node, timeout_sec=min(remaining, 0.2))
                continue
            prefix = "\033[H\033[2J" if interactive else ""
            snapshot = telemetry.snapshot()
            snapshot["odom_publishers"] = odom_subscription.get_publisher_count()
            snapshot["joint_publishers"] = joint_subscription.get_publisher_count()
            print(prefix + render(snapshot), flush=True)
            if args.once:
                break
            next_refresh = time.monotonic() + 1
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
