#!/usr/bin/env python3
"""Compare pelvis and torso IMU readings during a body movement."""

from math import asin, atan2, degrees
from body_feedback import RangeReport, duration, feedback_parser, sample
from walk_forward import load_ros_environment


def extract(message):
    for axis in ("x", "y", "z"):
        yield f"gyro {axis} (rad/s)", getattr(message.angular_velocity, axis)
        yield f"accel {axis} (m/s²)", getattr(message.linear_acceleration, axis)
    if message.orientation_covariance[0] == -1:
        return
    q = message.orientation
    norm = q.x**2 + q.y**2 + q.z**2 + q.w**2
    if not 0.9 <= norm <= 1.1:
        return
    yield "orientation roll (deg)", degrees(atan2(
        2 * (q.w * q.x + q.y * q.z), norm - 2 * (q.x**2 + q.y**2)
    ))
    pitch_sine = min(1.0, max(-1.0, 2 * (q.w * q.y - q.z * q.x) / norm))
    yield "orientation pitch (deg)", degrees(asin(pitch_sine))


def main():
    parser = feedback_parser(__doc__)
    seconds = duration(parser, parser.parse_args())
    load_ros_environment(__file__)
    from sensor_msgs.msg import Imu

    return sample("agibot_body_imu", seconds, [
        (f"/ros2/body_drive/{part}_imu/data", Imu, RangeReport(extract))
        for part in ("pelvis", "torso")
    ])


if __name__ == "__main__":
    raise SystemExit(main())
