#!/usr/bin/env bash
# Consolidated AgiBot dashboard

unset ROS_LOCALHOST_ONLY
export ROS_DOMAIN_ID=232 ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET

adu=${ROBOT_ADU_IP:-10.42.10.11}
details="$HOME/robot_dashboard_details.sh"
plus="$HOME/robot_dashboard_plus.sh"

query() {
  curl -fsS --max-time 5 -H 'Content-Type: application/json' \
    --data "$2" "http://$adu:$1"
  printf '\n'
}

pose() {
  local output
  output=$(timeout 6s ros2 run tf2_ros tf2_echo map base_link 2>&1)
  if grep -q 'Translation:' <<< "$output"; then
    printf 'Map pose available\n'
    grep -m1 'Translation:' <<< "$output"
  elif grep -qiE 'waiting for transform|invalid frame' <<< "$output"; then
    printf 'Map pose unavailable during the six-second check\n'
  else
    printf 'Map pose check failed\n%s\n' "$output"
  fi
}

live_camera() (
  if ! command -v ffmpeg >/dev/null; then
    echo 'Live preview needs ffmpeg. Saved camera clips are still available.'
    return 1
  fi
  overlay="$HOME/foxglove_camera_ws/install/local_setup.bash"
  profile=/agibot/software/v0/entry/cfg/ros_dds_configuration.xml
  [[ -r "$overlay" && -r "$profile" ]] || {
    echo 'Missing the Foxglove message overlay or camera DDS profile.'
    return 1
  }
  source "$overlay" || return
  unset ROS_AUTOMATIC_DISCOVERY_RANGE
  export ROS_LOCALHOST_ONLY=0 FASTRTPS_DEFAULT_PROFILES_FILE="$profile"
  python3 "$HOME/robot_live_camera.py" "${ROBOT_CAMERA_BIND_IP:-192.168.2.198}"
)

while true; do
  printf '\033[2J\033[HAGIBOT DASHBOARD\nHost %s | ADU %s\n\n' "$(hostname)" "$adu"
  printf '  1  Overview\n  2  Sensors\n  3  Navigation\n  4  Advanced\n  q  Quit\n\n'
  read -rp 'Select a view: ' choice || break
  case "$choice" in
    1)
      printf '\n=== Latest navigation task ===\n'
      query '53176/rpc/aimdk.protocol.PncService/ActionGetState' '{"task_id":0}'
      printf '\n=== Localization ===\n'
      pose
      printf '\n=== Sensor status ===\n'
      bash "$plus" sensors
      bash "$details" computer
      ;;
    2)
      printf '\n  1  Live LiDAR\n  2  Live front-left camera on port 8000\n'
      printf '  3  Capture a camera clip or snapshot\n  4  Play the latest saved clip\n'
      printf '  5  Measure sensor rates\n  6  Back\n'
      read -rp 'Select a sensor view: ' sensor || break
      case "$sensor" in
        1) python3 "$HOME/robot_lidar_view.py" ;;
        2) live_camera ;;
        3) bash "$details" camera ;;
        4) bash "$plus" browser ;;
        5) bash "$plus" sensors ;;
        6) continue ;;
      esac
      ;;
    3)
      printf '\n=== Active map ===\n'
      query '50807/rpc/aimdk.protocol.MappingService/GetCurrentWorkingMap' \
        '{"command":"MappingCommand_GET_CURRENT_WORKING_MAP"}'
      pose
      bash "$details" motion
      printf '\n  1  ADU map files and localization logs\n'
      printf '  2  Recent navigation failures\n  3  Back\n'
      read -rp 'Select navigation details: ' nav || break
      case "$nav" in
        1) bash "$plus" localization ;;
        2) bash "$plus" motion ;;
        3) continue ;;
      esac
      ;;
    4) bash "$HOME/robot_dashboard_advanced.sh"; continue ;;
    q|Q) break ;;
    *) echo 'Choose 1–4 or q.' ;;
  esac
  read -rp 'Press Enter to return to the menu. ' _ || break
done
