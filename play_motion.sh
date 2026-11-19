#!/usr/bin/env bash
# Play an installed A3 Ultra motion resource through MotionCommandService.
#
# Examples:
#   ./play_motion.sh
#   ./play_motion.sh /agibot/data/resources/default/motion/handshake/woshou1_Skeleton0.mcap
#   ROBOT=192.168.2.196 ./play_motion.sh /path/to/motion.mcap 10000 --execute

set -euo pipefail

DEFAULT_MOTION="/agibot/data/resources/default/motion/handshake/woshou1_Skeleton0.mcap"
MOTION_ID="$DEFAULT_MOTION"
DURATION_MS=10000
EXECUTE=false
ROBOT_IP="${ROBOT:-192.168.2.196}"
PORT="${ROBOT_MOTION_PORT:-56444}"

POSITIONAL=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --execute)
      EXECUTE=true
      ;;
    --duration-ms)
      shift
      if [[ $# -eq 0 ]]; then
        echo "--duration-ms requires a value." >&2
        exit 2
      fi
      DURATION_MS="$1"
      ;;
    -h|--help)
      echo "Usage: $0 [motion-file] [duration-ms] [--execute]"
      exit 0
      ;;
    -*)
      echo "Unknown option: $1" >&2
      exit 2
      ;;
    *)
      POSITIONAL+=("$1")
      ;;
  esac
  shift
done

if [[ ${#POSITIONAL[@]} -gt 2 ]]; then
  echo "Usage: $0 [motion-file] [duration-ms] [--execute]" >&2
  exit 2
fi
if [[ ${#POSITIONAL[@]} -ge 1 ]]; then
  MOTION_ID="${POSITIONAL[0]}"
fi
if [[ ${#POSITIONAL[@]} -eq 2 ]]; then
  DURATION_MS="${POSITIONAL[1]}"
fi

if ! [[ "$DURATION_MS" =~ ^[1-9][0-9]*$ ]]; then
  echo "Duration must be a positive number of milliseconds." >&2
  exit 2
fi

echo "Robot:  $ROBOT_IP:$PORT"
echo "Motion: $MOTION_ID"
echo "Length: ${DURATION_MS} ms"

if [[ "$EXECUTE" != true ]]; then
  echo "DRY RUN: no motion command sent. Add --execute after safety checks."
  exit 0
fi

echo "Confirm that the robot has clear space and no person is within its movement range."
read -r -p "Type PLAY to start this motion: " CONFIRM
if [[ "$CONFIRM" != "PLAY" ]]; then
  echo "Cancelled; no motion command sent."
  exit 1
fi

curl --fail-with-body --show-error --silent --include \
  -H 'content-type: application/json' \
  -X POST "http://${ROBOT_IP}:${PORT}/rpc/aimdk.protocol.MotionCommandService/SendMotionCommand" \
  -d "{\"motion_id\":\"${MOTION_ID}\",\"duration_ms\":${DURATION_MS},\"cmd_end\":true,\"cmd_pause\":false,\"cmd_reset\":false,\"cmd_repeat\":false}"
echo
