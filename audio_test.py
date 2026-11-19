#!/usr/bin/env python3
"""Speak a short text message through an AgiBot A3 Ultra speaker.

Example:
    python3 robot_tts.py "Hello. I am ready to assist you in English."
"""

import argparse
import sys
import uuid

import requests

from robot import Robot


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("text", help="text for the robot to speak (maximum 1024 UTF-8 bytes)")
    parser.add_argument("--ip", default="192.168.2.196", help="robot IP address")
    parser.add_argument("--agent-port", type=int, default=59301, help="TTS/agent RPC port")
    parser.add_argument("--no-interrupt", action="store_true", help="queue behind current audio when supported")
    return parser.parse_args()


def main():
    args = parse_args()
    trace_id = f"tts_{uuid.uuid4().hex[:12]}"
    robot = Robot(ip=args.ip, agent_port=args.agent_port)
    try:
        result = robot.play_tts(
            args.text,
            trace_id=trace_id,
            interrupt=not args.no_interrupt,
        )
    except (requests.RequestException, RuntimeError, ValueError) as exc:
        print(f"TTS request failed: {exc}", file=sys.stderr)
        return 1
    finally:
        robot.close()

    print("TTS request accepted.")
    print("Trace ID:", result.get("trace_id", trace_id))
    print("Response:", result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
