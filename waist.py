#!/usr/bin/env python3
"""Preview or test a small A3 Ultra waist posture adjustment."""

import argparse
import json
import math
import time

from walk_forward import CONTROLLER, load_ros_environment

STATE = "/motion/control/waist_joint_state"
COMMAND = "/motion/control/move_waist/pb_3Aaimdk_2Eprotocol_2EMotionControlMoveWaistChannel"
LIMITS_RAD = {"pitch": (0.0, 0.4), "roll": (-0.314, 0.314), "yaw": (-1.6, 1.6)}
JOINTS = {axis: f"waist_{axis}_joint" for axis in LIMITS_RAD}
BASELINE_TOLERANCE_RAD = math.radians(1)


def make_command(wrapper, stamp_ns, angles, height_m):
    seconds, nanos = divmod(stamp_ns, 1_000_000_000)
    payload = {
        "header": {
            "timestamp": {"seconds": seconds, "nanos": nanos},
            "control_source": "ControlSource_MANUAL",
        },
        **{f"waist_{axis}": angle for axis, angle in angles.items()},
        "waist_height": height_m,
    }
    data = json.dumps(payload, allow_nan=False).encode()
    return wrapper(serialization_type="json", data=[bytes((value,)) for value in data])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("axis", choices=LIMITS_RAD)
    parser.add_argument("--delta-deg", type=float, default=2.0,
                        help="signed angular change, up to 5 degrees")
    parser.add_argument("--height-m", type=float,
                        help="current waist height offset to include in the posture command")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not 0 < abs(args.delta_deg) <= 5:
        parser.error("--delta-deg must be nonzero and within ±5 degrees")
    if args.height_m is not None and not -0.3 <= args.height_m <= 0:
        parser.error("--height-m must be between -0.3 and 0 metres")
    if args.execute and args.height_m is None:
        parser.error("--execute requires the current waist height offset via --height-m")

    load_ros_environment(__file__)
    import rclpy
    from rclpy.qos import qos_profile_sensor_data
    from ros2_plugin_proto.msg import RosMsgWrapper
    from sensor_msgs.msg import JointState

    rclpy.init()
    node = None
    try:
        node = rclpy.create_node("agibot_test_waist")
        feedback = None
        received_at = 0.0

        def receive(message):
            nonlocal feedback, received_at
            positions = dict(zip(message.name, message.position))
            if (len(positions) == len(message.name) == len(message.position)
                    and all(name in positions and math.isfinite(positions[name])
                            for name in JOINTS.values())):
                feedback = {axis: positions[name] for axis, name in JOINTS.items()}
                received_at = time.monotonic()

        node.create_subscription(JointState, STATE, receive, qos_profile_sensor_data)
        publisher = None
        if args.execute:
            publisher = node.create_publisher(RosMsgWrapper, COMMAND, qos_profile_sensor_data)

        deadline = time.monotonic() + 5
        while (remaining := deadline - time.monotonic()) > 0:
            rclpy.spin_once(node, timeout_sec=min(0.05, remaining))
            if feedback is not None and (
                publisher is None or (
                    publisher.get_subscription_count()
                    and any(endpoint.node_name == CONTROLLER
                            for endpoint in node.get_subscriptions_info_by_topic(COMMAND))
                )
            ):
                break
        else:
            detail = "No valid waist joint feedback" if feedback is None else "No matched waist controller"
            parser.exit(1, f"{detail}. Check the HDU ROS 2 environment.\n")

        original = feedback.copy()
        for axis, (lower, upper) in LIMITS_RAD.items():
            measured = original[axis]
            bounded = min(upper, max(lower, measured))
            if abs(bounded - measured) > BASELINE_TOLERANCE_RAD:
                parser.exit(1, f"Measured waist {axis} {measured:.5f} rad is more than 1° "
                               f"outside the command range {lower:g} to {upper:g} rad.\n")
            if bounded != measured:
                original[axis] = bounded
                print(f"Waist {axis} baseline: measured {math.degrees(measured):.2f}°, "
                      f"command {math.degrees(bounded):.2f}° (nearest allowed value).", flush=True)
        target = original.copy()
        target[args.axis] += math.radians(args.delta_deg)
        lower, upper = LIMITS_RAD[args.axis]
        if not lower <= target[args.axis] <= upper:
            parser.exit(1, f"Waist {args.axis} target {target[args.axis]:.5f} rad is outside "
                           f"the command range {lower:g} to {upper:g} rad.\n")
        start_angle = original[args.axis]
        target_angle = target[args.axis]
        print(f"Waist {args.axis}: {math.degrees(start_angle):.2f}° -> "
              f"{math.degrees(target_angle):.2f}°", flush=True)
        if publisher is None:
            print("Preview only. No command sent.")
            return 0

        print(f"Height offset in command: {args.height_m:g} m", flush=True)
        start = time.monotonic()
        measured_start = feedback[args.axis]
        peak = measured_start
        for sample in range(101):
            sample_time = start + sample * 0.02
            while (remaining := sample_time - time.monotonic()) > 0:
                rclpy.spin_once(node, timeout_sec=remaining)
            now = time.monotonic()
            if now - received_at > 0.25 or now - sample_time > 0.04:
                parser.exit(1, "Stopped streaming because feedback or timing was stale.\n")
            fraction = min(sample / 75, 1.0)
            angles = original.copy()
            angles[args.axis] += (target_angle - start_angle) * fraction**2 * (3 - 2 * fraction)
            publisher.publish(make_command(
                RosMsgWrapper, node.get_clock().now().nanoseconds, angles, args.height_m
            ))
            measured = feedback[args.axis]
            if (measured - peak) * args.delta_deg > 0:
                peak = measured
        print(f"Peak observed change toward target: {math.degrees(peak - measured_start):+.2f}°. "
              f"Final observed change: {math.degrees(feedback[args.axis] - measured_start):+.2f}°.")
        return 0
    except KeyboardInterrupt:
        return 130
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
