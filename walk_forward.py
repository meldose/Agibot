#!/usr/bin/env python3
"""Send a short walking or turning command through the A3 Ultra controller."""

import argparse
import json
import os
import signal
import time

TOPIC = (
    "/motion/control/locomotion_velocity/"
    "pb_3Aaimdk_2Eprotocol_2EMotionControlLocomotionVelocityChannel"
)
CONTROLLER = "aimrt_motion_control_node"


def make_command(wrapper_type, forward, angular=0.0):
    payload = {
        "data": {
            "mode": "MotionControl_LocomotionMode_DEFAULT",
            "forward_velocity": forward,
            "lateral_velocity": 0.0,
            "angular_velocity": angular,
        },
    }
    wire_data = json.dumps(payload).encode("utf-8")
    return wrapper_type(serialization_type="json",
                        data=[bytes((value,)) for value in wire_data])


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="discover the controller")
    mode.add_argument("--execute", action="store_true", help="send a movement command")
    parser.add_argument("--direction", choices=("forward", "backward", "left", "right"),
                        default="forward", help="walk forward/backward or turn left/right")
    parser.add_argument("--scale", type=float, default=0.10,
                        help="normalized movement input (default and maximum 0.10)")
    parser.add_argument("--duration", type=float, default=1.0,
                        help="seconds to command movement (maximum 1)")
    args = parser.parse_args()
    if not 0 < args.scale <= 0.10 or not 0 < args.duration <= 1.0:
        parser.error("use 0 < scale <= 0.10 and 0 < duration <= 1 second")
    forward, angular = {
        "forward": (args.scale, 0.0),
        "backward": (-args.scale, 0.0),
        "left": (0.0, args.scale),
        "right": (0.0, -args.scale),
    }[args.direction]
    if not args.check:
        print(f"{args.direction}: forward={forward:g}, angular={angular:g} "
              f"for {args.duration:g} seconds", flush=True)
    if not (args.check or args.execute):
        return 0

    os.environ.pop("ROS_LOCALHOST_ONLY", None)
    os.environ.update(
        ROS_DOMAIN_ID="232",
        ROS_AUTOMATIC_DISCOVERY_RANGE="SYSTEM_DEFAULT",
        RMW_IMPLEMENTATION="rmw_fastrtps_cpp",
        FASTRTPS_DEFAULT_PROFILES_FILE=(
            "/agibot/software/v0/entry/cfg/ros_dds_configuration.xml"
        ),
    )

    import rclpy
    from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
    from rclpy.signals import SignalHandlerOptions
    from ros2_plugin_proto.msg import RosMsgWrapper

    interrupted = False

    def request_stop(signum, frame):
        nonlocal interrupted
        interrupted = True

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    node = None
    try:
        node = rclpy.create_node("agibot_walk_forward")
        qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT,
                         durability=DurabilityPolicy.VOLATILE)
        publisher = node.create_publisher(RosMsgWrapper, TOPIC, qos)
        discovery_deadline = time.monotonic() + 5
        while not interrupted:
            subscribers = node.get_subscriptions_info_by_topic(TOPIC)
            controller_visible = any(
                endpoint.node_name == CONTROLLER
                and endpoint.topic_type == "ros2_plugin_proto/msg/RosMsgWrapper"
                and endpoint.qos_profile.reliability == ReliabilityPolicy.BEST_EFFORT
                and endpoint.qos_profile.durability == DurabilityPolicy.VOLATILE
                for endpoint in subscribers
            )
            if controller_visible and publisher.get_subscription_count() > 0:
                break
            if time.monotonic() >= discovery_deadline:
                parser.exit(1, f"No compatible {CONTROLLER} subscriber found.\n")
            time.sleep(0.05)
        if interrupted:
            return 130
        print(f"Discovered {CONTROLLER}.", flush=True)
        if args.check:
            return 0

        command = make_command(RosMsgWrapper, forward, angular)
        stop = make_command(RosMsgWrapper, 0.0)
        deadline = time.monotonic() + args.duration
        try:
            while not interrupted:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                publisher.publish(command)
                time.sleep(min(0.05, remaining))
        finally:
            for _ in range(5):
                publisher.publish(stop)
                time.sleep(0.05)
        return 130 if interrupted else 0
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
