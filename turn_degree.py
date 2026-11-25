#!/usr/bin/env python3
"""Turn the A3 Ultra in place by a specified angle using legged odometry."""

import argparse
import math
import os
import signal
import time

from walk_forward import CONTROLLER, TOPIC, load_ros_environment, make_command

ODOMETRY = "/legged_odometry_node/legged_odometry"
PERIOD = 0.05


def yaw_from_quaternion(q):
    if not all(math.isfinite(value) for value in (q.x, q.y, q.z, q.w)):
        return None
    norm = q.x**2 + q.y**2 + q.z**2 + q.w**2
    if not 0.9 <= norm <= 1.1:
        return None
    return math.atan2(2 * (q.w * q.z + q.x * q.y), norm - 2 * (q.y**2 + q.z**2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("direction", choices=("left", "right"))
    parser.add_argument("--degrees", type=float, default=90.0,
                        help="relative angle, 5° to 180° in magnitude (negative reverses direction)")
    parser.add_argument("--execute", action="store_true", help="send angular commands")
    args = parser.parse_args()
    degrees = abs(args.degrees)
    if not 5 <= degrees <= 180:
        parser.error("--degrees must have a magnitude between 5 and 180")
    direction = 1 if args.direction == "left" else -1
    if args.degrees < 0:
        direction = -direction
    turn_side = "left" if direction > 0 else "right"
    target = math.radians(degrees)
    timeout = max(10.0, degrees / 2)
    load_ros_environment(__file__)

    os.environ.pop("ROS_LOCALHOST_ONLY", None)
    os.environ.update(
        ROS_DOMAIN_ID="232", ROS_AUTOMATIC_DISCOVERY_RANGE="SYSTEM_DEFAULT",
        RMW_IMPLEMENTATION="rmw_fastrtps_cpp",
        FASTRTPS_DEFAULT_PROFILES_FILE="/agibot/software/v0/entry/cfg/ros_dds_configuration.xml",
    )
    import rclpy
    from nav_msgs.msg import Odometry
    from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy, qos_profile_sensor_data
    from rclpy.signals import SignalHandlerOptions
    from ros2_plugin_proto.msg import RosMsgWrapper

    interrupted = False

    def request_stop(_signum, _frame):
        nonlocal interrupted
        interrupted = True

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    node = None
    try:
        node = rclpy.create_node("agibot_turn_90")
        last_yaw = None
        last_stamp = 0
        last_received = 0.0
        angle = 0.0
        invalid_jump = False

        def receive(msg):
            nonlocal last_yaw, last_stamp, last_received, angle, invalid_jump
            yaw = yaw_from_quaternion(msg.pose.pose.orientation)
            stamp = msg.header.stamp.sec * 10**9 + msg.header.stamp.nanosec
            if yaw is None or (stamp and stamp <= last_stamp):
                return
            if last_yaw is not None:
                difference = math.remainder(yaw - last_yaw, math.tau)
                if abs(difference) > math.radians(25):
                    invalid_jump = True
                angle += difference
            last_yaw = yaw
            last_stamp = stamp
            last_received = time.monotonic()

        node.create_subscription(Odometry, ODOMETRY, receive, qos_profile_sensor_data)
        qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT,
                         durability=DurabilityPolicy.VOLATILE)
        publisher = node.create_publisher(RosMsgWrapper, TOPIC, qos) if args.execute else None
        deadline = time.monotonic() + 5
        while not interrupted:
            rclpy.spin_once(node, timeout_sec=PERIOD)
            ready = publisher is None or (
                publisher.get_subscription_count()
                and any(ep.node_name == CONTROLLER
                        and ep.topic_type == "ros2_plugin_proto/msg/RosMsgWrapper"
                        and ep.qos_profile.reliability == ReliabilityPolicy.BEST_EFFORT
                        and ep.qos_profile.durability == DurabilityPolicy.VOLATILE
                        for ep in node.get_subscriptions_info_by_topic(TOPIC))
            )
            if ready and last_yaw is not None and time.monotonic() - last_received <= 0.4:
                break
            if time.monotonic() >= deadline:
                parser.exit(1, "Timed out waiting for fresh odometry or the motion controller.\n")
        if interrupted:
            return 130

        print(f"Heading: {math.degrees(last_yaw):+.1f}°. "
              f"Target: {degrees:g}° {turn_side}.", flush=True)
        if publisher is None:
            print("Preview only. No command sent.")
            return 0

        angle = 0.0
        invalid_jump = False
        start = time.monotonic()
        progress_time = start
        progress_mark = 0.0
        next_command = start
        stop = make_command(RosMsgWrapper, 0.0)
        commands = {
            speed: make_command(RosMsgWrapper, 0.0, direction * speed)
            for speed in (0.10, 0.05)
        }
        reason = "Interrupted."
        try:
            while not interrupted:
                now = time.monotonic()
                progress = angle * direction
                if invalid_jump or now - last_received > 0.4:
                    reason = "Odometry stopped updating or jumped."
                    break
                if progress >= target - math.radians(1):
                    reason = "Reached the turn threshold."
                    break
                if progress < -math.radians(5):
                    reason = "Robot rotated in the opposite direction."
                    break
                if progress >= progress_mark + math.radians(2):
                    progress_mark, progress_time = progress, now
                if now - progress_time > 4 or now - start > timeout:
                    reason = "Turn stalled or timed out."
                    break
                if now >= next_command:
                    speed = 0.05 if target - progress < min(target / 2, math.radians(6)) else 0.10
                    publisher.publish(commands[speed])
                    next_command = now + PERIOD
                rclpy.spin_once(node, timeout_sec=max(0.0, next_command - time.monotonic()))
        finally:
            for _ in range(5):
                publisher.publish(stop)
                end = time.monotonic() + PERIOD
                while (remaining := end - time.monotonic()) > 0:
                    rclpy.spin_once(node, timeout_sec=remaining)

        measured = math.degrees(angle * direction)
        print(f"{reason} Measured turn after stop commands: {measured:.1f}° "
              f"(target {degrees:g}° {turn_side}).")
        if interrupted:
            return 130
        return 0 if (reason == "Reached the turn threshold." and not invalid_jump
                     and abs(measured - degrees) <= 3) else 1
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
