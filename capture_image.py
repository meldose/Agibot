#!/usr/bin/env python3
"""Save one color frame from a ROS 2 camera topic as a PNG."""

import argparse
from datetime import datetime
from pathlib import Path
import struct
import time
import zlib


def png_chunk(kind, data):
    return (struct.pack(">I", len(data)) + kind + data
            + struct.pack(">I", zlib.crc32(kind + data)))


def nv12_rows(frame):
    width, height, stride = frame.width, frame.height, frame.step
    data = bytes(frame.data)
    chroma_offset = stride * height
    if (width <= 0 or height <= 0 or width % 2 or height % 2
            or stride < width or len(data) < chroma_offset + stride * (height // 2)):
        raise ValueError("Invalid NV12 dimensions or plane data")

    def clamp(value):
        return min(255, max(0, (value + 128) >> 8))

    rows = bytearray((3 * width + 1) * height)
    for y in range(height):
        luma_start = y * stride
        chroma_start = chroma_offset + (y // 2) * stride
        output_start = y * (3 * width + 1) + 1
        for x in range(0, width, 2):
            u = data[chroma_start + x] - 128
            v = data[chroma_start + x + 1] - 128
            red = 409 * v
            green = -100 * u - 208 * v
            blue = 516 * u
            for column in (x, x + 1):
                luma = 298 * (data[luma_start + column] - 16)
                pixel = output_start + 3 * column
                rows[pixel] = clamp(luma + red)
                rows[pixel + 1] = clamp(luma + green)
                rows[pixel + 2] = clamp(luma + blue)
    return rows


def image_png(frame):
    encodings = {"rgb8": (3, 2), "bgr8": (3, 2), "mono8": (1, 0),
                 "rgba8": (4, 6), "bgra8": (4, 6)}
    if frame.encoding == "nv12":
        rows, color_type = nv12_rows(frame), 2
    elif frame.encoding in encodings:
        channels, color_type = encodings[frame.encoding]
        rows = packed_rows(frame, channels)
    else:
        raise ValueError(f"Unsupported camera encoding: {frame.encoding}")
    header = struct.pack(">IIBBBBB", frame.width, frame.height, 8, color_type, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", header)
            + png_chunk(b"IDAT", zlib.compress(rows)) + png_chunk(b"IEND", b""))


def packed_rows(frame, channels):
    row_size = frame.width * channels
    data = bytes(frame.data)
    if (frame.width <= 0 or frame.height <= 0 or frame.step < row_size
            or len(data) < frame.height * frame.step):
        raise ValueError("Invalid camera frame dimensions or data")
    rows = bytearray()
    for offset in range(0, frame.step * frame.height, frame.step):
        row = bytearray(data[offset:offset + row_size])
        if frame.encoding in ("bgr8", "bgra8"):
            row[0::channels], row[2::channels] = row[2::channels], row[0::channels]
        rows.append(0)
        rows.extend(row)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topic", default="/hal/head_front_left_fisheye_camera/image",
                        help="ROS image topic (default: front-left head camera)")
    parser.add_argument("--output", type=Path,
                        help="PNG path (default: a timestamped file next to this script)")
    args = parser.parse_args()
    if args.output is None:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        args.output = Path(__file__).with_name(f"head-left-{timestamp}.png")

    import rclpy
    from rclpy.qos import qos_profile_sensor_data
    from sensor_msgs.msg import Image

    frame = None

    def receive_image(message):
        nonlocal frame
        frame = message

    rclpy.init()
    node = None
    try:
        node = rclpy.create_node("agibot_camera_snapshot")
        node.create_subscription(Image, args.topic, receive_image, qos_profile_sensor_data)
        deadline = time.monotonic() + 8
        while frame is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                publishers = node.get_publishers_info_by_topic(args.topic)
                names = ", ".join(endpoint.node_name for endpoint in publishers)
                parser.exit(
                    1,
                    f"No image received on {args.topic} within 8 seconds. "
                    f"Discovered publishers: {names or 'none'}.\n",
                )
            rclpy.spin_once(node, timeout_sec=remaining)
        try:
            png = image_png(frame)
            with args.output.open("xb") as output:
                output.write(png)
        except (OSError, ValueError) as error:
            parser.exit(1, f"Could not save image: {error}\n")
        print(f"Saved {frame.width}×{frame.height} {frame.encoding} image to {args.output}")
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
