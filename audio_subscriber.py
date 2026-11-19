#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSHistoryPolicy, QoSProfile, QoSReliabilityPolicy
from ros2_plugin_proto.msg import RosMsgWrapper

from aimdk.protocol_pb2 import ProcessedAudioOutput, AudioVADState

import datetime
import os

class AudioSubscriber(Node):
    def __init__(self):
        super().__init__("audio_subscriber")

        # Audio buffers, stored separately by stream_id
        self.audio_buffers = {}  # {stream_id: bytearray()}
        self.recording_state = {}  # {stream_id: bool}, whether recording is active

        # Create the output directory for audio files
        self.audio_output_dir = "audio_recordings"
        os.makedirs(self.audio_output_dir, exist_ok=True)

        qos_profile = QoSProfile(
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
        )

        self.subscription = self.create_subscription(
            RosMsgWrapper,
            "/agent/process_audio_output/pb_3Aaimdk_2Eprotocol_2EProcessedAudioOutput",
            self.audio_callback,
            qos_profile,
        )

        self.get_logger().info("Started subscribing to noise-reduced audio data...")

    def audio_callback(self, msg):
        try:
            # Check whether the serialization type is pb
            if msg.serialization_type != "pb":
                self.get_logger().warn(f"Unsupported serialization type: {msg.serialization_type}")
                return

            # Convert the data field from list[bytes] to bytes
            audio_data_bytes = b"".join(msg.data)

            # Parse the message using the generated protobuf class
            processed_audio = ProcessedAudioOutput()
            processed_audio.ParseFromString(audio_data_bytes)

            self.get_logger().info(
                f"Received audio data: stream_id={processed_audio.stream_id}, "
                f"vad_state={processed_audio.vad_state}, "
                f"audio_size={len(processed_audio.audio_data)} bytes"
            )

            # Process audio according to the VAD state
            self.handle_vad_state(processed_audio)

        except Exception as e:
            self.get_logger().error(f"Error while processing audio message: {e}")

    def handle_vad_state(self, processed_audio):
        """Handle different VAD states."""
        vad_state = processed_audio.vad_state
        stream_id = processed_audio.stream_id
        audio_data = processed_audio.audio_data

        # Initialize the buffer for this stream_id if it does not exist
        if stream_id not in self.audio_buffers:
            self.audio_buffers[stream_id] = bytearray()
            self.recording_state[stream_id] = False

        # Mapping of VAD state names
        vad_state_names = {
            AudioVADState.AUDIO_VAD_STATE_NONE: "No speech",
            AudioVADState.AUDIO_VAD_STATE_BEGIN: "Speech begin",
            AudioVADState.AUDIO_VAD_STATE_PROCESSING: "Speech processing",
            AudioVADState.AUDIO_VAD_STATE_END: "Speech end",
        }

        stream_names = {1: "Internal microphone", 2: "External microphone"}

        self.get_logger().info(
            f"[{stream_names.get(stream_id, f'Unknown stream {stream_id}')}] "
            f"VAD state: {vad_state_names.get(vad_state, f'Unknown state {vad_state}')} "
            f"audio data: {len(audio_data)} bytes"
        )

        # Process audio data according to the VAD state
        if vad_state == AudioVADState.AUDIO_VAD_STATE_BEGIN:
            self.get_logger().info("Speech start detected")
            # Start a new recording and clear the buffer
            self.audio_buffers[stream_id].clear()
            self.recording_state[stream_id] = True
            # Append the current audio data
            if len(audio_data) > 0:
                self.audio_buffers[stream_id].extend(audio_data)

        elif vad_state == AudioVADState.AUDIO_VAD_STATE_PROCESSING:
            self.get_logger().info("Speech is being processed...")
            # If recording is active, continue appending audio data
            if self.recording_state[stream_id] and len(audio_data) > 0:
                self.audio_buffers[stream_id].extend(audio_data)

        elif vad_state == AudioVADState.AUDIO_VAD_STATE_END:
            self.get_logger().info("Speech ended")
            # Append the final chunk of audio data
            if self.recording_state[stream_id] and len(audio_data) > 0:
                self.audio_buffers[stream_id].extend(audio_data)

            # Save the complete audio segment
            if (
                self.recording_state[stream_id]
                and len(self.audio_buffers[stream_id]) > 0
            ):
                self.save_audio_segment(bytes(self.audio_buffers[stream_id]), stream_id)

            # Stop recording
            self.recording_state[stream_id] = False

        elif vad_state == AudioVADState.AUDIO_VAD_STATE_NONE:
            # No speech state, do not record
            if self.recording_state[stream_id]:
                self.get_logger().info("Recording state reset")
                self.recording_state[stream_id] = False

        # Output the current buffer status
        if stream_id in self.audio_buffers:
            buffer_size = len(self.audio_buffers[stream_id])
            recording = self.recording_state[stream_id]
            self.get_logger().debug(
                f"[Stream {stream_id}] Buffer size: {buffer_size} bytes, recording: {recording}"
            )

    def save_audio_segment(self, audio_data, stream_id):
        """Save the audio segment as 16 kHz, 16-bit, mono PCM."""
        if len(audio_data) > 0:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")

            # Create a subdirectory by stream_id
            stream_dir = os.path.join(self.audio_output_dir, f"stream_{stream_id}")
            os.makedirs(stream_dir, exist_ok=True)

            # Generate the file name
            stream_names = {1: "internal_mic", 2: "external_mic"}
            stream_name = stream_names.get(stream_id, f"stream_{stream_id}")
            filename = f"{stream_name}_{timestamp}.pcm"
            filepath = os.path.join(stream_dir, filename)

            try:
                with open(filepath, "wb") as f:
                    f.write(audio_data)
                self.get_logger().info(
                    f"Audio segment saved: {filepath} (size: {len(audio_data)} bytes)"
                )

                # Calculate the audio duration (assuming 16 kHz, 16-bit, mono)
                sample_rate = 16000
                bits_per_sample = 16
                channels = 1
                bytes_per_sample = bits_per_sample // 8
                total_samples = len(audio_data) // (bytes_per_sample * channels)
                duration_seconds = total_samples / sample_rate

                self.get_logger().info(
                    f"Audio duration: {duration_seconds:.2f} s ({total_samples} samples)"
                )

            except Exception as e:
                self.get_logger().error(f"Failed to save audio file: {e}")

    def get_buffer_info(self):
        """Get information about all buffers for debugging."""
        info = {}
        for stream_id in self.audio_buffers:
            info[stream_id] = {
                "buffer_size": len(self.audio_buffers[stream_id]),
                "recording": self.recording_state[stream_id],
            }
        return info

def main(args=None):
    rclpy.init(args=args)

    audio_subscriber = AudioSubscriber()

    try:
        audio_subscriber.get_logger().info("Listening for noise-reduced audio data. Press Ctrl+C to exit...")
        rclpy.spin(audio_subscriber)
    except KeyboardInterrupt:
        audio_subscriber.get_logger().info("Exit signal received, shutting down...")
    finally:
        audio_subscriber.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()

