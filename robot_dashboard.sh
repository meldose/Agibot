#!/usr/bin/env bash

unset ROS_LOCALHOST_ONLY
export ROS_DOMAIN_ID=232
export ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET

adu=${ROBOT_ADU_IP:-10.42.10.11}
map_url="http://$adu:50807/rpc/aimdk.protocol.MappingService"
nav_url="http://$adu:53176/rpc/aimdk.protocol.PncService"

section() {
  printf '\n\033[1;36m%s\033[0m\n' "$1"
}

query() {
  curl -fsS --max-time 4 \
    -H 'Content-Type: application/json' \
    --data "$2" "$1" || printf 'Query unavailable'
  printf '\n'
}

ros() {
  timeout 10s ros2 "$@" || printf 'ROS query failed or timed out.\n'
}

pause() {
  printf '\nPress Enter to return to the menu. '
  read -r _
}

while true; do
  printf '\033[H\033[2J'
  printf '\033[1mAGIBOT ROBOT DASHBOARD\033[0m\n'
  printf 'Host %s  |  ADU %s  |  ROS domain %s\n' \
    "$(hostname)" "$adu" "$ROS_DOMAIN_ID"

  printf '\n'
  printf '  1  Navigation status and active map\n'
  printf '  2  Localization and map transform\n'
  printf '  3  Base motion topic connections\n'
  printf '  4  All ROS topics and types\n'
  printf '  5  All ROS nodes\n'
  printf '  6  All ROS services and types\n'
  printf '  7  Inspect a ROS node\n'
  printf '  q  Quit\n\n'

  printf '  8  Live LiDAR\n\n'
  read -rp 'Select a view: ' choice || break
  case "$choice" in
    1)
      section 'Latest navigation task'
      query "$nav_url/ActionGetState" '{"task_id":0}'
      section 'Active map'
      query "$map_url/GetCurrentWorkingMap" \
        '{"command":"MappingCommand_GET_CURRENT_WORKING_MAP"}'
      ;;
    2)
      section 'Localization topic endpoints'
      ros topic info /slam/localization/odometry --verbose --no-daemon
      section 'Map to base_link transform (up to 8 seconds)'
      timeout 8s ros2 run tf2_ros tf2_echo map base_link
      ;;
    3)
      for topic in /cmd_vel_dbg_in /cmd_vel /cmd_vel_final; do
        section "$topic"
        ros topic info "$topic" --verbose --no-daemon
      done
      ;;
    4) ros topic list -t --no-daemon ;;
    5) ros node list --no-daemon ;;
    6) ros service list -t --no-daemon ;;
    7)
      read -rp 'Node name, for example /vectorflux_a2_main_node: ' node
      if [[ "$node" == /* ]]; then
        ros node info "$node" --no-daemon
      else
        printf 'Enter a full node name beginning with /.\n'
      fi
      ;;
    8) python3 "$HOME/robot_lidar_view.py" ;;
    8) python3 "$HOME/robot_lidar_view.py" ;;
    8) python3 "$HOME/robot_lidar_view.py" ;;
    8) python3 "$HOME/robot_lidar_view.py" ;;
    q|Q) break ;;
    *) printf 'Choose 1–8 or q.\n' ;;
  esac
  pause
done
