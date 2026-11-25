#!/usr/bin/env bash

probe=$(cat <<'SENSOR_CHECK'
echo "Host: $(hostname)"
echo "Last boot: $(uptime -s)"

printf '\n=== Live board readings ===\n'
found=0
for chip in /sys/class/hwmon/hwmon*; do
    [ -r "$chip/name" ] || continue
    name=$(cat "$chip/name") || continue
    for file in "$chip"/{temp,fan,in,curr,power}*_input; do
        [ -r "$file" ] || continue
        value=$(cat "$file") || continue
        found=1
        label="$name (${chip##*/}/${file##*/})"
        case "${file##*/}" in
            temp*) awk -v label="$label" -v value="$value" \
                'BEGIN { printf "%s: %.1f C\n", label, value / 1000 }' ;;
            fan*)  printf '%s: %s RPM\n' "$label" "$value" ;;
            in*)   printf '%s: %s mV\n' "$label" "$value" ;;
            curr*) printf '%s: %s mA\n' "$label" "$value" ;;
            power*) printf '%s: %s uW\n' "$label" "$value" ;;
        esac
    done
done
[ "$found" -eq 1 ] || echo "No readable board values"

for group in iio video4linux; do
    printf '\n=== %s device inventory ===\n' "$group"
    case "$group" in
        iio) entries=(/sys/bus/iio/devices/iio:device*/name) ;;
        video4linux) entries=(/sys/class/video4linux/video*/name) ;;
    esac
    found=0
    for entry in "${entries[@]}"; do
        [ -r "$entry" ] || continue
        printf '%s: ' "$(basename "$(dirname "$entry")")"
        cat "$entry"
        found=1
    done
    [ "$found" -eq 1 ] || echo "No entries visible"
done

printf '\n=== Audio capture device inventory ===\n'
if command -v arecord >/dev/null 2>&1; then
    arecord -l
elif [ -r /proc/asound/pcm ]; then
    cat /proc/asound/pcm
else
    echo "ALSA inventory unavailable"
fi

printf '\n=== ROS topic inventory ===\n'
if command -v ros2 >/dev/null 2>&1; then
    printf 'ROS_DOMAIN_ID=%s ROS_LOCALHOST_ONLY=%s\n' \
        "${ROS_DOMAIN_ID:-unset}" "${ROS_LOCALHOST_ONLY:-unset}"
    timeout 10s ros2 topic list -t
elif command -v rostopic >/dev/null 2>&1; then
    timeout 10s rostopic list
else
    echo "ROS CLI unavailable in this shell"
fi

printf '\n=== Recent camera-driver errors ===\n'
if ! command -v journalctl >/dev/null 2>&1; then
    echo "journalctl unavailable"
elif logs=$(journalctl -k -b --since '5 minutes ago' --no-pager -q) &&
     [ -n "$logs" ]; then
    matches=$(printf '%s\n' "$logs" |
        grep -Ei 'csi fifo overflow|csi size err|fs/fe mis|Oops|rtmutex deadlock' |
        tail -n 5)
    printf '%s\n' "${matches:-No matching errors in the readable log}"
else
    echo "No readable kernel entries in the last five minutes"
fi
SENSOR_CHECK
)

check_host() {
    printf '\n========== %s (%s) ==========\n' "$1" "$2"
    if [[ "$2" == local ]]; then
        timeout 30s bash -s <<< "$probe"
    else
        timeout 30s ssh -o BatchMode=yes -o ConnectTimeout=5 "$2" bash -s <<< "$probe"
    fi
    status=$?
    if ((status != 0)); then
        printf 'Check incomplete for %s (exit %s)\n' "$1" "$status"
        return 1
    fi
}

failed=0
check_host ADU "${ADU_HOST:-agi@10.42.10.11}" || failed=1
check_host MDU "${MDU_HOST:-agi@mdu}" || failed=1
check_host DU  "${DU_HOST:-local}" || failed=1
exit "$failed"
