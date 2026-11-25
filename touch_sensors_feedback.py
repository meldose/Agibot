#!/usr/bin/env python3
"""Observe touch sensor messages while pressing and releasing a sensor."""

import json
from body_feedback import duration, feedback_parser, sample
from walk_forward import load_ros_environment

TOPIC = "/aima/touch_sensor/data/pb_3Aaimdk_2Eprotocol_2ETouchSensorDataChannel"


class TouchReport:
    def __init__(self):
        self.samples = 0
        self.changes = 0
        self.last = None
        self.format = ""
        self.last_fields = None

    def receive(self, message):
        self.samples += 1
        self.format = message.serialization_type
        data = message.data
        payload = bytes(data) if not data or isinstance(data[0], int) else b"".join(data)
        value = payload
        self.last_fields = None
        if self.format == "json":
            try:
                decoded = json.loads(payload)
                if isinstance(decoded, dict):
                    self.last_fields = {key: item for key, item in decoded.items()
                                        if key not in {"header", "timestamp", "stamp"}}
                    value = self.last_fields
            except (ValueError, UnicodeError):
                pass
        if self.last is not None and value != self.last:
            self.changes += 1
        self.last = value

    def show(self):
        if not self.samples:
            print("No touch messages observed.")
            return
        print(f"Format: {self.format or '(unspecified)'} | observed changes: {self.changes}")
        if self.last_fields is not None:
            print(f"Last touch data: {json.dumps(self.last_fields, ensure_ascii=False)}")
        else:
            print("Raw payload changes can include timestamps or counters.")


def main():
    parser = feedback_parser(__doc__)
    seconds = duration(parser, parser.parse_args())
    load_ros_environment(__file__)
    from ros2_plugin_proto.msg import RosMsgWrapper

    return sample("agibot_touch_feedback", seconds, [(TOPIC, RosMsgWrapper, TouchReport())])


if __name__ == "__main__":
    raise SystemExit(main())
