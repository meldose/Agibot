#!/usr/bin/env bash
# Set the A3 Ultra interaction mode through the documented AgentControl RPC.
# Usage:
#   ./set_interactive_mode.sh only_voice
#   ./set_interactive_mode.sh voice_face 10.42.10.10
#   ./set_interactive_mode.sh normal 192.168.2.196 --yes

set -euo pipefail

MODE="${1:-only_voice}"
ROBOT_IP="${2:-10.42.10.10}"
YES="${3:-}"
PORT="${ROBOT_AGENT_PORT:-59301}"

case "$MODE" in
  normal|only_voice|voice_face) ;;
  *)
    echo "Usage: $0 {normal|only_voice|voice_face} [robot-ip] [--yes]" >&2
    exit 2
    ;;
esac

if [[ "$YES" != "--yes" ]]; then
  read -r -p "Set interaction mode to '$MODE' on $ROBOT_IP:$PORT? Type APPLY: " CONFIRM
  if [[ "$CONFIRM" != "APPLY" ]]; then
    echo "Cancelled; no request sent."
    exit 1
  fi
fi

curl --fail-with-body --show-error --silent --include \
  -H 'content-type: application/json' \
  -X POST "http://${ROBOT_IP}:${PORT}/rpc/aimdk.protocol.AgentControlService/SetAgentPropertiesRequest" \
  -d "{\"contents\":{\"properties\":{\"2\":\"${MODE}\"}}}"

echo
echo "Request sent. Reboot the robot before the interaction-mode change takes effect."
