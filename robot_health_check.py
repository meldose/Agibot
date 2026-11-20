#!/usr/bin/env python3
"""Sample A3 Ultra ROS 2 telemetry without commanding the robot."""

import argparse
from dataclasses import dataclass, field
from math import hypot, isfinite
from statistics import median
import time

from nav_msgs.msg import Odometry
import rclpy
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Imu, JointState, PointCloud2


def magnitude(vector):
    return hypot(vector.x, vector.y, vector.z)


def metrics(message):
    if isinstance(message, PointCloud2):
        return {"point slots": message.width * message.height,
                "payload bytes": len(message.data)}
    if isinstance(message, Imu):
        return {"gyro rad/s": magnitude(message.angular_velocity),
                "acceleration m/s²": magnitude(message.linear_acceleration)}
    if isinstance(message, JointState):
        return {"joint names": len(message.name),
                "finite positions": sum(isfinite(value) for value in message.position)}
    twist = message.twist.twist
    return {"linear m/s": magnitude(twist.linear),
            "angular rad/s": magnitude(twist.angular)}


@dataclass
class Feed:
    arrivals: list = field(default_factory=list)
    stamps: list = field(default_factory=list)
    values: dict = field(default_factory=dict)
    frame: str = ""

    def receive(self, message):
        self.arrivals.append(time.monotonic())
        stamp = message.header.stamp
        self.stamps.append(stamp.sec * 10**9 + stamp.nanosec)
        self.frame = message.header.frame_id or "(empty)"
        for name, value in metrics(message).items():
            self.values.setdefault(name, []).append(value)

    def report(self, publisher_count):
        count = len(self.arrivals)
        if not count:
            print(f"  No samples received. Discovered publishers: {publisher_count}")
            return False

        print(f"  {count} messages | frame {self.frame} | publishers {publisher_count}")
        if count > 1:
            gaps = [end - start for start, end in zip(self.arrivals, self.arrivals[1:])]
            rate = (count - 1) / sum(gaps)
            print(f"  {rate:.1f} Hz received | longest arrival gap {max(gaps):.3f} s")
        advancing = sum(end > start for start, end in zip(self.stamps, self.stamps[1:]))
        print(f"  Header timestamps advanced on {advancing}/{count - 1} transitions")
        for name, values in self.values.items():
            finite = [value for value in values if isfinite(value)]
            if finite:
                print(f"  {name}: median {median(finite):.4g}, range "
                      f"{min(finite):.4g} to {max(finite):.4g}")
            if len(finite) != len(values):
                print(f"  {name}: {len(values) - len(finite)} nonfinite samples")
        return True


PROFILES = {
    "adu": (
        ("/hal/neck_middle_livox_lidar/pointcloud", PointCloud2),
        ("/perception/lidar_perception/filtered", PointCloud2),
        ("/hal/neck_middle_livox_lidar/imu", Imu),
        ("/slam/localization/odometry", Odometry),
    ),
    "mdu": (
        ("/legged_odometry_node/legged_odometry", Odometry),
        ("/motion/control/leg_joint_state", JointState),
        ("/ros2/body_drive/pelvis_imu/data", Imu),
        ("/ros2/body_drive/torso_imu/data", Imu),
    ),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", choices=PROFILES, help="computer to run the check on")
    parser.add_argument("--seconds", type=float, default=10,
                        help="sample window in seconds (default 10)")
    args = parser.parse_args()
    if not 1 <= args.seconds <= 120:
        parser.error("--seconds must be between 1 and 120")

    rclpy.init()
    node = None
    try:
        node = rclpy.create_node("agibot_robot_health_check")
        feeds = {}
        for topic, message_type in PROFILES[args.profile]:
            feed = feeds[topic] = Feed()
            node.create_subscription(message_type, topic, feed.receive, qos_profile_sensor_data)
        print(f"Sampling {args.profile.upper()} for {args.seconds:g} seconds...", flush=True)
        deadline = time.monotonic() + args.seconds
        while (remaining := deadline - time.monotonic()) > 0:
            rclpy.spin_once(node, timeout_sec=remaining)

        results = []
        for topic, feed in feeds.items():
            print(topic)
            results.append(feed.report(len(node.get_publishers_info_by_topic(topic))))
        print(f"Received samples on {sum(results)}/{len(results)} feeds.")
        return 0 if all(results) else 1
    except KeyboardInterrupt:
        return 130
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
