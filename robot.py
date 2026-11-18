
import requests


class Robot:
    """Small HTTP RPC wrapper for AGIBOT A3 Ultra."""

    def __init__(self, ip="192.168.2.196", port=56322, timeout=5):
        self.base_url = f"http://{ip}:{port}/rpc"
        self.timeout = timeout
        self.session = requests.Session()

    def _rpc(self, service, method, payload=None):
        url = f"{self.base_url}/{service}/{method}"

        response = self.session.post(
            url,
            json={} if payload is None else payload,
            timeout=self.timeout,
        )
        response.raise_for_status()

        data = response.json()

        code = str(data.get("header", {}).get("code", ""))
        if code != "0":
            raise RuntimeError(
                f"RPC {service}/{method} failed: {data}"
            )

        return data

    def get_jointstate(self):
        """Return all 14 arm joints, keyed by joint name."""
        data = self._rpc(
            "aimdk.protocol.MotionControlJointService",
            "GetArmJointState",
        )

        return {
            joint["name"]: {
                "position": joint["position"],
                "velocity": joint["velocity"],
                "effort": joint["effort"],
            }
            for joint in data.get("states", [])
        }

    def get_right_arm(self):
        """Return the seven right-arm joints."""
        return {
            name: state
            for name, state in self.get_jointstate().items()
            if name.startswith("right_")
        }

    def get_left_arm(self):
        """Return the seven left-arm joints."""
        return {
            name: state
            for name, state in self.get_jointstate().items()
            if name.startswith("left_")
        }

    def get_action(self):
        """Return current robot motion-action information."""
        data = self._rpc(
            "aimdk.protocol.MotionControlActionService",
            "GetAction",
        )
        return data.get("info", {})

    def get_available_actions(self):
        """Return available motion action names."""
        data = self._rpc(
            "aimdk.protocol.MotionControlActionService",
            "GetAvailableActions",
        )
        return [
            item["ext_action"]
            for item in data.get("commands", [])
        ]

    def close(self):
        """Close the HTTP session."""
        self.session.close()
