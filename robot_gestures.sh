#!/usr/bin/env bash
# Launch installed A3 Ultra upper-body gesture resources by a simple name.
#
# Examples:
#   ROBOT=10.42.10.12 ./robot_gestures.sh list
#   ROBOT=10.42.10.12 ./robot_gestures.sh wave --execute
#   ROBOT=10.42.10.12 ./robot_gestures.sh handshake 10000 --execute

set -euo pipefail

GESTURE="${1:-list}"
DURATION_MS=10000
EXECUTE=""

if [[ $# -ge 2 && "$2" != "--execute" ]]; then
  DURATION_MS="$2"
fi
if [[ "${2:-}" == "--execute" || "${3:-}" == "--execute" ]]; then
  EXECUTE="--execute"
fi

case "$GESTURE" in
  handshake)
    MOTION_ID='/agibot/data/resources/default/motion/右手握手/woshou1_Skeleton0.mcap'
    ;;
  wave)
    MOTION_ID='/agibot/data/resources/default/motion/右手挥手/huishou_Skeleton0.mcap'
    ;;
  thumbs_up)
    MOTION_ID='/agibot/data/resources/default/motion/右手点赞/danshoudianzan_Skeleton0_ta.mcap'
    ;;
  finger_heart)
    MOTION_ID='/agibot/data/resources/default/motion/手指比心/手指比心_ta.mcap'
    ;;
  double_thumbs_up)
    MOTION_ID='/agibot/data/resources/default/motion/双手点赞/20260728_163231_ta.mcap'
    ;;
  fist_bow)
    MOTION_ID='/agibot/data/resources/default/motion/抱拳礼/baoquanli_ma_ta.mcap'
    ;;
  bow)
    MOTION_ID='/agibot/data/resources/default/motion/鞠躬感谢/jugongzhixie2_Skeleton1.mcap'
    ;;
  fist_bump_left)
    MOTION_ID='/agibot/data/resources/default/motion/向左碰拳/zuoshoupengquan_ma_ta.mcap'
    ;;
  fist_bump_right)
    MOTION_ID='/agibot/data/resources/default/motion/向右碰拳/youshoupengquan_ma_ta.mcap'
    ;;
  watch)
    MOTION_ID='/agibot/data/resources/default/motion/看看手表/kanbiao_Skeleton0_ta.mcap'
    ;;
  list|--help|-h)
    cat <<'EOF'
Usage: ROBOT=10.42.10.12 ./robot_gestures.sh GESTURE [duration-ms] [--execute]

Available gestures:
  handshake          right-hand handshake
  wave               right-hand wave
  thumbs_up          right-hand thumbs-up
  finger_heart       finger-heart gesture
  double_thumbs_up   thumbs-up with both hands
  fist_bow           traditional fist-and-palm greeting
  bow                bow / thank-you gesture
  fist_bump_left     left-side fist bump
  fist_bump_right    right-side fist bump
  watch              look-at-watch gesture

Without --execute, this only previews the selected motion.
EOF
    exit 0
    ;;
  *)
    echo "Unknown gesture: $GESTURE" >&2
    echo "Run: $0 list" >&2
    exit 2
    ;;
esac

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/play_motion.sh" "$MOTION_ID" "$DURATION_MS" $EXECUTE
