#!/usr/bin/env bash
# Read-only HTTP JSON-RPC status commands for an AgiBot A3 Ultra.
#
# Examples:
#   ./robot_rpc_status.sh mode
#   ./robot_rpc_status.sh action 192.168.2.196
#   ./robot_rpc_status.sh joints
#   ./robot_rpc_status.sh all

set -euo pipefail

COMMAND="${1:-help}"
ROBOT_IP="${2:-${ROBOT:-192.168.2.196}}"

rpc() {
  local port="$1"
  local service="$2"
  local method="$3"
  local payload="$4"

  curl --fail-with-body --silent --show-error \
    -H 'content-type: application/json' \
    -X POST "http://${ROBOT_IP}:${port}/rpc/${service}/${method}" \
    -d "$payload"
  echo
}

mode() {
  rpc 59301 aimdk.protocol.AgentControlService GetAgentPropertiesRequest \
    '{"property_ids":[2]}'
}

voice() {
  rpc 59301 aimdk.protocol.AgentControlService GetVoiceEnable '{}'
}

action() {
  rpc 56322 aimdk.protocol.MotionControlActionService GetAction '{}'
}

actions() {
  rpc 56322 aimdk.protocol.MotionControlActionService GetAvailableActions '{}'
}

joints() {
  rpc 56322 aimdk.protocol.MotionControlJointService GetArmJointState '{}'
}

compliance() {
  rpc 56322 aimdk.protocol.MotionControlMotionService CheckArmCompliance '{}'
}

usage() {
  cat <<EOF
Usage: $0 {mode|voice|action|actions|joints|compliance|all} [robot-ip]

All commands are read-only.
  mode        interaction mode: normal, only_voice, or voice_face
  voice       built-in voice interaction enabled/disabled state
  action      current motion-control action
  actions     available motion-control actions
  joints      positions, velocities, and effort for 14 arm joints
  compliance  arm-compliance status
  all         run mode, voice, action, actions, and joints
EOF
}

case "$COMMAND" in
  mode) mode ;;
  voice) voice ;;
  action) action ;;
  actions) actions ;;
  joints) joints ;;
  compliance) compliance ;;
  all)
    mode
    voice
    action
    actions
    joints
    ;;
  help|-h|--help) usage ;;
  *)
    usage >&2
    exit 2
    ;;
esac
