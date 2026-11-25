bash <<'ROBOT_SENSOR_CHECK'
host=$(hostname -s)
case "${host,,}" in
    adu) role="ADU" ;;
    mdu) role="MDU" ;;
    hdu) role="DU (HDU)" ;;
    du)  role="DU" ;;
    *)   role="Unrecognized hostname" ;;
esac

printf 'Computer: %s\nHostname: %s\nLast boot: %s\n' \
    "$role" "$host" "$(uptime -s)"

printf '\n=== Live board readings ===\n'
found=0
for chip in /sys/class/hwmon/hwmon*; do
    [ -r "$chip/name" ] || continue
    name=$(cat "$chip/name") || continue
    for file in "$chip"/{temp,fan,in,curr,power}*_input; do
        [ -r "$file" ] || continue
        value=$(cat "$file") || continue
        label="$name (${chip##*/}/${file##*/})"
        found=1
        case "${file##*/}" in
            temp*)  awk -v label="$label" -v value="$value" \
                'BEGIN { printf "%s: %.1f C\n", label, value / 1000 }' ;;
            fan*)   printf '%s: %s RPM\n' "$label" "$value" ;;
            in*)    printf '%s: %s mV\n' "$label" "$value" ;;
            curr*)  printf '%s: %s mA\n' "$label" "$value" ;;
            power*) printf '%s: %s uW\n' "$label" "$value" ;;
        esac
    done
done
[ "$found" -eq 1 ] || echo "No readable board values"

printf '\n=== Analog sensor and camera inventory ===\n'
found=0
for entry in /sys/bus/iio/devices/iio:device*/name \
             /sys/class/video4linux/video*/name; do
    [ -r "$entry" ] || continue
    name=$(cat "$entry") || continue
    printf '%s: %s\n' "$(basename "$(dirname "$entry")")" "$name"
    found=1
done
[ "$found" -eq 1 ] || echo "No entries visible"

printf '\n=== Audio capture inventory ===\n'
if command -v arecord >/dev/null 2>&1; then
    if audio=$(arecord -l 2>&1); then
        printf '%s\n' "$audio" | awk '
            /^card / { print; count++ }
            END { if (!count) print "No capture devices listed" }
        '
    else
        printf '%s\n' "$audio"
    fi
elif [ -r /proc/asound/pcm ]; then
    cat /proc/asound/pcm
else
    echo "ALSA inventory unavailable"
fi

printf '\n=== ROS topics ===\n'
if command -v ros2 >/dev/null 2>&1; then
    printf 'ROS_DOMAIN_ID=%s ROS_LOCALHOST_ONLY=%s\n' \
        "${ROS_DOMAIN_ID:-unset}" "${ROS_LOCALHOST_ONLY:-unset}"
    timeout 10s ros2 topic list -t || echo "ROS 2 lookup failed or timed out"
elif command -v rostopic >/dev/null 2>&1; then
    timeout 10s rostopic list || echo "ROS lookup failed or timed out"
else
    echo "ROS CLI unavailable in this shell"
fi
ROBOT_SENSOR_CHECK
