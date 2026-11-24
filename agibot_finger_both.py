#!/usr/bin/env python3

import argparse
import time

TOPIC = "/motion/control/hand_joint_command"
JOINTS = (
    "thumb_rotation_0", "thumb_wiggles_1", "thumb_bent_2",
    "index_wiggles_0", "index_bent_1", "middle_bent",
    "ring_wiggles_0", "ring_bent_1",
    "pinky_wiggles_0", "pinky_bent_1",
)
NAMES = [f"{side}_{joint}" for side in ("left", "right") for joint in JOINTS]
NAMES[0] = "left_thumb_roration_0"  # Spelling in the A3 Ultra v3.2 SDK.

POSES = (
    [4095, 0, 500, 4095, 3754, 3730, 4095, 3143, 0, 3227,
     0, 4000, 3000, 0, 3766, 3766, 0, 3706, 4095, 3730],
    [4095, 0, 500, 4095, 0, 0, 4095, 0, 0, 0,
     0, 4000, 3000, 0, 0, 0, 0, 0, 4095, 0],
)


def main():
    parser = argparse.ArgumentParser(description="Two-pose A3 Ultra O10 hand test.")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    for number, pose in enumerate(POSES, 1):
        print(f"SDK pose {number}: {pose}", flush=True)
    if not args.execute:
        print("Preview only. No command sent.")
        return

    print("Confirm the robot is stationary, both drives are ready, playback has "
          "released control, and both hands are clear.")
    if input("Type BOTH to send the two poses: ").strip() != "BOTH":
        return

    import rclpy
    from rclpy.qos import QoSProfile, QoSReliabilityPolicy
    from sensor_msgs.msg import JointState

    rclpy.init()
    node = None
    try:
        node = rclpy.create_node("o10_both_hands_test")
        publisher = node.create_publisher(
            JointState, TOPIC,
            QoSProfile(depth=10, reliability=QoSReliabilityPolicy.RELIABLE),
        )

        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            endpoints = node.get_subscriptions_info_by_topic(TOPIC)
            if publisher.get_subscription_count() and any(
                endpoint.node_name == "aimrt_motion_control_node"
                for endpoint in endpoints
            ):
                break
            rclpy.spin_once(node, timeout_sec=0.1)
        else:
            raise SystemExit("Motion controller subscriber unavailable. Nothing sent.")

        for number, pose in enumerate(POSES, 1):
            message = JointState()
            message.header.stamp = node.get_clock().now().to_msg()
            message.header.frame_id = "O10Hand"
            message.name = NAMES
            message.position = [float(value) for value in pose]
            publisher.publish(message)
            print(f"Published SDK pose {number} to both hands.", flush=True)
            time.sleep(1)
    except KeyboardInterrupt:
        print("Test interrupted.")
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
