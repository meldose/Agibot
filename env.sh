#!/usr/bin/env bash
# Source this file before running the AimDK ROS 2 examples:
#   source ./env.sh
#
# Optional: set AIMDK_PREBUILT_DIR when the AimDK development package's
# `prebuilt` directory is stored somewhere other than ./prebuilt.

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  echo "Run this with: source ./env.sh" >&2
  exit 1
fi

AGIBOT_ENV=/agibot/software/v0/entry/env/env.sh
if [[ ! -f "$AGIBOT_ENV" ]]; then
  echo "AimDK runtime environment not found: $AGIBOT_ENV" >&2
  echo "Run this on the robot (or update env.sh for your AimDK installation)." >&2
  return 1
fi

# Provides the robot's ROS 2 runtime and middleware configuration.
source "$AGIBOT_ENV"

PREBUILT_DIR="${AIMDK_PREBUILT_DIR:-$PWD/prebuilt}"
ROS_PROTO_SETUP="$PREBUILT_DIR/ros2_plugin_proto_aarch64/share/ros2_plugin_proto/local_setup.bash"

if [[ -f "$ROS_PROTO_SETUP" ]]; then
  source "$ROS_PROTO_SETUP"
  echo "Loaded AimDK runtime and ros2_plugin_proto from: $PREBUILT_DIR"
else
  echo "Loaded AimDK runtime. ros2_plugin_proto setup was not found at:" >&2
  echo "  $ROS_PROTO_SETUP" >&2
  echo "Copy the AimDK prebuilt directory here or run:" >&2
  echo "  export AIMDK_PREBUILT_DIR=/path/to/prebuilt" >&2
fi
