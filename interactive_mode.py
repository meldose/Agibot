#!/usr/bin/env python3
"""Configure or inspect A3 Ultra full-takeover interaction mode.

Based on AimDK A3 Ultra v3.2, section 8.2.  The script makes no changes
unless --apply is specified, and it asks for a final confirmation before
changing the robot's persistent interaction setting.

Examples:
    python3 interactive_mode.py
    python3 interactive_mode.py --mode only_voice --apply
    python3 interactive_mode.py --mode voice_face --apply
    python3 interactive_mode.py --mode normal --apply
    python3 interactive_mode.py --mic-source external --apply

After changing --mode, reboot the robot.  In only_voice / voice_face mode,
run audio_subscriber.py on the robot after sourcing the AimDK environments.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SERVICE = "aimdk.protocol.AgentControlService"
HAL_AUDIO_SERVICE = "aimdk.protocol.HalAudioService"
MODES = ("normal", "only_voice", "voice_face")
MIC_SOURCES = {"built-in": 0, "external": 1}


class RpcError(RuntimeError):
    """The robot did not accept an RPC request."""


class RobotRpc:
    def __init__(self, robot_ip: str, port: int, timeout: float) -> None:
        self.base_url = f"http://{robot_ip}:{port}/rpc"
        self.timeout = timeout

    def call(self, service: str, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/{service}/{method}"
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RpcError(f"HTTP {exc.code} from {url}: {detail}") from exc
        except URLError as exc:
            raise RpcError(f"Cannot reach {url}: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise RpcError(f"Invalid JSON response from {url}") from exc

        code = result.get("header", {}).get("code")
        if code is not None and str(code) != "0":
            raise RpcError(f"RPC {method} failed: {json.dumps(result)}")
        return result

    def interaction_mode(self) -> str | None:
        result = self.call(SERVICE, "GetAgentPropertiesRequest", {"property_ids": [2]})
        return result.get("contents", {}).get("properties", {}).get("2")

    def mic_source(self) -> int | None:
        return self.call(HAL_AUDIO_SERVICE, "GetMicSourceRequest", {}).get("mic_source")

    def set_interaction_mode(self, mode: str) -> dict[str, Any]:
        return self.call(
            SERVICE,
            "SetAgentPropertiesRequest",
            {"contents": {"properties": {"2": mode}}},
        )

    def set_mic_source(self, source: int) -> dict[str, Any]:
        return self.call(HAL_AUDIO_SERVICE, "SetMicSourceRequest", {"mic_source": source})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--robot-ip", default="192.168.2.196", help="robot IP address")
    parser.add_argument("--port", type=int, default=59301, help="agent RPC port")
    parser.add_argument("--timeout", type=float, default=5.0, help="RPC timeout in seconds")
    parser.add_argument("--mode", choices=MODES, help="persistent interaction mode to configure")
    parser.add_argument(
        "--mic-source",
        choices=MIC_SOURCES,
        help="select the microphone source (external is recommended for A3 Ultra v3.2)",
    )
    parser.add_argument("--apply", action="store_true", help="allow a requested configuration change")
    parser.add_argument("--yes", action="store_true", help="skip the typed confirmation (use only in controlled automation)")
    return parser.parse_args()


def confirm_change(summary: str, skip_confirmation: bool) -> bool:
    print(summary)
    if skip_confirmation:
        return True
    return input("Type APPLY to continue: ").strip() == "APPLY"


def main() -> int:
    args = parse_args()
    changing = args.mode is not None or args.mic_source is not None
    if changing and not args.apply:
        print("DRY RUN: add --apply to change robot configuration.")
        return 2

    robot = RobotRpc(args.robot_ip, args.port, args.timeout)
    try:
        if not changing:
            mode = robot.interaction_mode()
            print(f"Interaction mode: {mode or 'not reported'}")
            try:
                mic = robot.mic_source()
            except RpcError as exc:
                # Some robot builds do not expose HalAudioService even though
                # the interaction-mode service is available.  Do not turn an
                # otherwise useful mode check into a failure in that case.
                print(f"Microphone source: unavailable ({exc})")
            else:
                mic_name = next(
                    (name for name, value in MIC_SOURCES.items() if value == mic),
                    f"unknown ({mic})",
                )
                print(f"Microphone source: {mic_name}")
            return 0

        requested = []
        if args.mode:
            requested.append(f"interaction mode -> {args.mode}")
        if args.mic_source:
            requested.append(f"microphone source -> {args.mic_source}")
        if not confirm_change("Will set " + ", ".join(requested) + ".", args.yes):
            print("Cancelled; no changes were sent.")
            return 1

        if args.mode:
            result = robot.set_interaction_mode(args.mode)
            print(f"Mode request accepted: {json.dumps(result)}")
            print("Reboot the robot before the new interaction mode takes effect.")
        if args.mic_source:
            result = robot.set_mic_source(MIC_SOURCES[args.mic_source])
            print(f"Microphone request accepted: {json.dumps(result)}")
        return 0
    except RpcError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
