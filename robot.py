
import requests


class Robot:
    """Small HTTP RPC wrapper for AGIBOT A3 Ultra."""

    def __init__(self, ip="192.168.2.196", port=56322, agent_port=59301, timeout=5):
        self.ip = ip
        self.base_url = f"http://{ip}:{port}/rpc"
        self.agent_base_url = f"http://{ip}:{agent_port}/rpc"
        self.timeout = timeout
        self.session = requests.Session()

    def _rpc(self, service, method, payload=None, base_url=None):
        url = f"{base_url or self.base_url}/{service}/{method}"

        response = self.session.post(
            url,
            json={} if payload is None else payload,
            timeout=self.timeout,
        )
        if not response.ok:
            body = response.text.strip()
            raise RuntimeError(
                f"RPC {service}/{method} returned HTTP {response.status_code}: "
                f"{body or response.reason}"
            )

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

    def play_tts(self, text, trace_id="robot_tts", interrupt=True):
        """Speak short text through the robot TTS service.

        The robot must have network access.  The A3 Ultra v3.2 API accepts
        short requests only (up to 1024 bytes).  The response being accepted
        does not guarantee audible playback if another higher-priority audio
        stream owns the speaker.
        """
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text must be a non-empty string")
        if len(text.encode("utf-8")) > 1024:
            raise ValueError("text must be 1024 UTF-8 bytes or fewer")

        return self._rpc(
            "aimdk.protocol.TTSService",
            "PlayTTS",
            {
                "text": text,
                "priority_level": "INTERACTION_L6",
                "domain": "agibot_python",
                "trace_id": trace_id,
                "is_interrupted": interrupt,
            },
            base_url=self.agent_base_url,
        )

    def get_tts_status(self, trace_id):
        """Return the playback status associated with a TTS/media trace ID."""
        return self._rpc(
            "aimdk.protocol.TTSService",
            "GetAudioStatus",
            {"trace_id": trace_id},
            base_url=self.agent_base_url,
        )

    def stop_tts(self, trace_id):
        """Interrupt the TTS/media playback associated with a trace ID."""
        return self._rpc(
            "aimdk.protocol.TTSService",
            "StopTTSTraceId",
            {"trace_id": trace_id},
            base_url=self.agent_base_url,
        )

    def get_audio_volume(self):
        """Return the built-in speaker volume and mute state."""
        return self._rpc(
            "aimdk.protocol.HalAudioService",
            "GetAudioVolume",
            base_url=f"http://{self.ip}:56666/rpc",
        )

    def set_audio_volume(self, volume, mute=False):
        """Set built-in speaker volume (0-70; the documentation warns above 70)."""
        if not isinstance(volume, int) or not 0 <= volume <= 70:
            raise ValueError("volume must be an integer from 0 to 70")
        # Firmware builds have used both SPEAKER_BUILT_IN and the misspelled
        # SPEAKRE_BUILT_IN.  Reuse the value advertised by this robot.
        current = self.get_audio_volume()
        speaker_type = current.get("type", "SPEAKER_BUILT_IN")
        return self._rpc(
            "aimdk.protocol.HalAudioService",
            "SetAudioVolume",
            {
                "audio_volume": volume,
                "is_mute": mute,
                "type": speaker_type,
            },
            base_url=f"http://{self.ip}:56666/rpc",
        )

    def play_motion(self, motion_id, duration_ms=10000, interrupt=True):
        """Request playback of a motion resource installed on the robot."""
        if not isinstance(duration_ms, int) or duration_ms <= 0:
            raise ValueError("duration_ms must be a positive integer")
        return self._rpc(
            "aimdk.protocol.MotionCommandService",
            "SendMotionCommand",
            {
                "motion_id": motion_id,
                "duration_ms": duration_ms,
                "cmd_end": interrupt,
                "cmd_pause": False,
                "cmd_reset": False,
                "cmd_repeat": False,
            },
            base_url=f"http://{self.ip}:56444/rpc",
        )

    def close(self):
        """Close the HTTP session."""
        self.session.close()
