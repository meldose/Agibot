#!/usr/bin/env python3
"""Preview or stream a small A3 Ultra elbow position adjustment."""

import argparse
import math
import time

STATE_TOPIC = "/motion/control/arm_joint_state"
COMMAND_TOPIC = "/motion/control/arm_joint_command"
ARM_JOINTS = (
    "shoulder_pitch", "shoulder_roll", "shoulder_yaw", "elbow",
    "wrist_roll", "wrist_pitch", "wrist_yaw",
)
JOINT_NAMES = [f"{side}_{joint}_joint" for side in ("left", "right") for joint in ARM_JOINTS]
JOINT_SET = set(JOINT_NAMES)
MAX_DELTA_DEG = 10
ELBOW_LIMITS_RAD = (-0.95993, 1.74533)
SAMPLE_PERIOD = 0.01


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("side", choices=("left", "right"))
    parser.add_argument("--delta-deg", type=float, default=1.0,
                        help=f"signed relative angle, at most {MAX_DELTA_DEG}° in either direction")
    parser.add_argument("--execute", action="store_true",
                        help="send targets with the robot in MOTION and motion_player stopped")
    args = parser.parse_args()
    if not 0 < abs(args.delta_deg) <= MAX_DELTA_DEG:
        parser.error(f"--delta-deg must be nonzero and at most {MAX_DELTA_DEG} degrees in magnitude")

    import rclpy
    from rclpy.qos import qos_profile_sensor_data
    from sensor_msgs.msg import JointState

    rclpy.init()
    node = None
    try:
        node = rclpy.create_node("agibot_test_elbow")
        feedback = None
        received_at = 0.0

        def receive(message):
            nonlocal feedback, received_at
            if (len(message.name) == len(message.position) == 14
                    and set(message.name) == JOINT_SET
                    and all(math.isfinite(position) for position in message.position)):
                feedback = dict(zip(message.name, message.position))
                received_at = time.monotonic()

        node.create_subscription(JointState, STATE_TOPIC, receive, qos_profile_sensor_data)
        publisher = node.create_publisher(JointState, COMMAND_TOPIC, qos_profile_sensor_data) if args.execute else None
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.05)
            if feedback is not None and (
                publisher is None or (
                    publisher.get_subscription_count()
                    and any(endpoint.node_name == "aimrt_motion_control_node"
                            for endpoint in node.get_subscriptions_info_by_topic(COMMAND_TOPIC))
                )
            ):
                break
        else:
            parser.exit(1, "Timed out waiting for live arm feedback or the motion controller.\n")

        joint = f"{args.side}_elbow_joint"
        original = feedback[joint]
        target = original + math.radians(args.delta_deg)
        lower, upper = ELBOW_LIMITS_RAD
        if not (lower <= original <= upper and lower <= target <= upper):
            parser.exit(1, f"Starting position or target is outside {lower:g} to {upper:g} rad.\n")
        print(f"{joint}: {original:.5f} -> {target:.5f} rad ({args.delta_deg:+g}°)", flush=True)
        if publisher is None:
            print("Preview only. No command sent.")
            return 0
        if time.monotonic() - received_at > 0.25:
            parser.exit(1, "Arm feedback is stale.\n")

        command = JointState()
        command.name = JOINT_NAMES
        command.position = [feedback[name] for name in JOINT_NAMES]
        command.velocity = [0.0] * len(JOINT_NAMES)
        command.effort = [0.0] * len(JOINT_NAMES)
        index = JOINT_NAMES.index(joint)
        peak = original
        start = time.monotonic()
        previous_publish = start
        ramp_samples = max(60, math.ceil(abs(args.delta_deg) * 30))
        for sample in range(ramp_samples + 21):
            next_sample = start + sample * SAMPLE_PERIOD
            while (remaining := next_sample - time.monotonic()) > 0:
                rclpy.spin_once(node, timeout_sec=remaining)
            now = time.monotonic()
            if now - previous_publish > 0.03 or now - received_at > 0.25:
                parser.exit(1, "Stopped streaming because timing or feedback was stale.\n")
            fraction = min(sample / ramp_samples, 1.0)
            smooth_fraction = fraction * fraction * (3 - 2 * fraction)
            command.position[index] = original + (target - original) * smooth_fraction
            command.header.stamp = node.get_clock().now().to_msg()
            publisher.publish(command)
            previous_publish = now
            if (feedback[joint] - peak) * args.delta_deg > 0:
                peak = feedback[joint]
        print(f"Peak observed change toward target: {math.degrees(peak - original):+.2f}°.")
        return 0
    except KeyboardInterrupt:
        return 130
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
