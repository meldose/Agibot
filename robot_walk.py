#!/usr/bin/env python3
"""Send one short, guarded A3 Ultra walking command through ROS 2.

Run only from a machine with the AimDK ROS environment already sourced:
    source /agibot/software/v0/entry/env/env.sh
    source /path/to/prebuilt/ros2_plugin_proto_aarch64/share/ros2_plugin_proto/local_setup.bash

Example:
    python3 robot_walk.py forward --execute

The script checks that the robot is in MOTION state, sends a low-scale
velocity command for at most one second, then sends several zero commands.
"""

from __future__ import annotations

import argparse
import sys
import time

import requests


TOPIC = "/motion/control/locomotion_velocity"
RATE_HZ = 20.0
MAX_SCALE = 0.10
MAX_DURATION = 1.0
DIRECTIONS = {
    "forward": (1.0, 0.0, 0.0),
    "backward": (-1.0, 0.0, 0.0),
    "left": (0.0, 1.0, 0.0),
    "right": (0.0, -1.0, 0.0),
    "turn-left": (0.0, 0.0, 1.0),
    "turn-right": (0.0, 0.0, -1.0),
}


def read_confirmation(prompt: str) -> str:
    """Read an ASCII safety token without depending on the terminal locale."""
    sys.stdout.write(prompt)
    sys.stdout.flush()
    return sys.stdin.buffer.readline().decode("ascii", errors="ignore").strip()


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("direction", choices=DIRECTIONS, help="movement direction")
    parser.add_argument("--scale", type=float, default=0.05, help="velocity scale, 0.01 to 0.10 (default: 0.05)")
    parser.add_argument("--duration", type=float, default=0.5, help="command duration in seconds, 0.1 to 1.0 (default: 0.5)")
    parser.add_argument(
        "--robot-ip",
        default="192.168.2.196",
        help="robot IP used for the MOTION-state check (default: working LAN address)",
    )
    parser.add_argument("--execute", action="store_true", help="allow publication of the walking command")
    return parser.parse_args()


def require_motion_state(robot_ip: str) -> None:
    url = (
        f"http://{robot_ip}:56322/rpc/"
        "aimdk.protocol.MotionControlActionService/GetAction"
    )
    response = requests.post(url, json={}, timeout=5)
    response.raise_for_status()
    current = response.json().get("info", {}).get("current_action")
    if current != "MotionControlAction_MOTION":
        raise RuntimeError(f"Robot must be in MOTION state; current state is {current!r}")


def find_locomotion_message_type(protocol_pb2):
    """Find the generated protobuf type from its documented field layout.

    AimDK package revisions use generated class names that can differ.  The
    message itself is stable: it has either these three fields directly or in
    a nested `data` field.
    """
    from google.protobuf.message import Message

    required = {"forward_velocity", "lateral_velocity", "angular_velocity"}
    for name in dir(protocol_pb2):
        candidate = getattr(protocol_pb2, name)
        if not isinstance(candidate, type) or not issubclass(candidate, Message):
            continue
        descriptor = candidate.DESCRIPTOR
        if required.issubset(descriptor.fields_by_name):
            return candidate, None
        data_field = descriptor.fields_by_name.get("data")
        if data_field and data_field.message_type:
            fields = data_field.message_type.fields_by_name
            if required.issubset(fields):
                return candidate, "data"
    raise RuntimeError(
        "Could not find the locomotion protobuf in aimdk.protocol_pb2. "
        "Use the AimDK v3.2 package supplied with this robot."
    )


def set_velocity(message, nested_field, forward: float, lateral: float, angular: float):
    target = getattr(message, nested_field) if nested_field else message
    target.forward_velocity = forward
    target.lateral_velocity = lateral
    target.angular_velocity = angular

    mode_field = target.DESCRIPTOR.fields_by_name.get("mode")
    if mode_field and mode_field.enum_type:
        default = next(
            (value.number for value in mode_field.enum_type.values if value.name.endswith("DEFAULT")),
            mode_field.enum_type.values[0].number,
        )
        target.mode = default


def main():
    args = parse_args()
    if not 0 < args.scale <= MAX_SCALE:
        print(f"--scale must be greater than 0 and no more than {MAX_SCALE}", file=sys.stderr)
        return 2
    if not 0 < args.duration <= MAX_DURATION:
        print(f"--duration must be greater than 0 and no more than {MAX_DURATION} second", file=sys.stderr)
        return 2
    if not args.execute:
        print("DRY RUN: no walking command sent. Add --execute after safety checks.")
        return 2

    print("Confirm clear floor space, stable footing, and an accessible emergency stop.")
    if read_confirmation(
        f"Type WALK to move {args.direction} for {args.duration:.1f} second(s): "
    ) != "WALK":
        print("Cancelled; no walking command sent.")
        return 1

    try:
        require_motion_state(args.robot_ip)
        import rclpy
        from rclpy.node import Node
        from ros2_plugin_proto.msg import RosMsgWrapper
        from aimdk import protocol_pb2
    except (ImportError, requests.RequestException, RuntimeError) as exc:
        print(f"Cannot start walking command: {exc}", file=sys.stderr)
        return 1

    message_type, nested_field = find_locomotion_message_type(protocol_pb2)
    direction = DIRECTIONS[args.direction]
    command = message_type()
    set_velocity(
        command,
        nested_field,
        direction[0] * args.scale,
        direction[1] * args.scale,
        direction[2] * args.scale,
    )
    stop_command = message_type()
    set_velocity(stop_command, nested_field, 0.0, 0.0, 0.0)

    rclpy.init()
    node = Node("agibot_guarded_walk")
    publisher = node.create_publisher(RosMsgWrapper, TOPIC, 10)

    def publish(protobuf_message):
        wrapper = RosMsgWrapper()
        wrapper.serialization_type = "pb"
        wrapper.data = [protobuf_message.SerializeToString()]
        publisher.publish(wrapper)

    try:
        deadline = time.monotonic() + args.duration
        while time.monotonic() < deadline:
            publish(command)
            time.sleep(1.0 / RATE_HZ)
    except KeyboardInterrupt:
        print("Interrupted; sending stop commands.")
    finally:
        for _ in range(5):
            publish(stop_command)
            time.sleep(1.0 / RATE_HZ)
        node.destroy_node()
        rclpy.shutdown()

    print("Walking command finished; zero-velocity stop commands were sent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
