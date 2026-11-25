bash <<'ROBOT_SENSOR_CHECK'
shopt -s nullglob

host=$(hostname -s) || exit 1
case "${host,,}" in
    adu) computer=ADU ;;
    hdu) computer='HDU (DU)' ;;
    du)  computer=DU ;;
    mdu) computer=MDU ;;
    *)   computer='Unknown' ;;
esac

printf 'Computer detected: %s (hostname: %s)\n' "$computer" "$host"
printf 'Last boot: %s\n' "$(uptime -s)"

printf '\n=== Live temperatures, fans, and electrical readings ===\n'
found=0
for chip in /sys/class/hwmon/hwmon*; do
    name=$(cat "$chip/name" 2>/dev/null) || continue
    for file in "$chip"/{temp,fan,in,curr,power}*_input; do
        [ -r "$file" ] || continue
        value=$(cat "$file") || continue
        found=1
        label="$name (${chip##*/}/${file##*/})"
        case "${file##*/}" in
            temp*) awk -v label="$label" -v value="$value" \
                'BEGIN { printf "%s: %.1f °C\n", label, value / 1000 }' ;;
            fan*)   printf '%s: %s RPM\n' "$label" "$value" ;;
            in*)    printf '%s: %s mV\n' "$label" "$value" ;;
            curr*)  printf '%s: %s mA\n' "$label" "$value" ;;
            power*) printf '%s: %s µW\n' "$label" "$value" ;;
        esac
    done
done
((found)) || echo "No readable board values"

printf '\n=== Power supplies ===\n'
found=0
for supply in /sys/class/power_supply/*; do
    type=$(cat "$supply/type" 2>/dev/null) || continue
    found=1
    printf '%s (%s)\n' "${supply##*/}" "$type"
    for key in status online capacity voltage_now current_now; do
        [ -r "$supply/$key" ] || continue
        value=$(cat "$supply/$key") || continue
        case "$key" in
            capacity)    printf '  %s: %s%%\n' "$key" "$value" ;;
            voltage_now) printf '  %s: %s µV\n' "$key" "$value" ;;
            current_now) printf '  %s: %s µA\n' "$key" "$value" ;;
            *)           printf '  %s: %s\n' "$key" "$value" ;;
        esac
    done
done
((found)) || echo "No power supplies visible in sysfs"

printf '\n=== IIO devices and stationary IMU readings ===\n'
devices=(/sys/bus/iio/devices/iio:device*)
((${#devices[@]})) || echo "No IIO devices visible"
for device in "${devices[@]}"; do
    name=$(cat "$device/name" 2>/dev/null) || continue
    printf '%s (%s)\n' "$name" "${device##*/}"
    axes=("$device"/in_anglvel_{x,y,z}_raw "$device"/in_accel_{x,y,z}_raw)
    ((${#axes[@]})) || continue
    for sample in 1 2 3; do
        printf '  Sample %s\n' "$sample"
        for axis in "${axes[@]}"; do
            value=$(cat "$axis") || continue
            printf '    %s: %s\n' "${axis##*/}" "$value"
        done
        [ "$sample" -eq 3 ] || sleep 1
    done
done

printf '\n=== Camera inventory ===\n'
cameras=(/sys/class/video4linux/video*/name)
((${#cameras[@]})) || echo "No V4L2 camera entries visible"
for file in "${cameras[@]}"; do
    dir=${file%/name}
    printf '%s: %s\n' "${dir##*/}" "$(cat "$file")"
done

printf '\n=== Audio capture inventory ===\n'
if command -v arecord >/dev/null 2>&1; then
    arecord -l
elif [ -r /proc/asound/pcm ]; then
    cat /proc/asound/pcm
else
    echo "ALSA capture inventory unavailable"
fi

printf '\n=== Saved lavalier recordings ===\n'
recordings=(/tmp/robot-lavalier.*.wav)
if ((${#recordings[@]})); then
    ls -lh -- "${recordings[@]}"
else
    echo "No saved lavalier recordings found"
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

if [[ ${host,,} == hdu || ${host,,} == du ]]; then
    printf '\n=== Camera-driver errors in the last two minutes ===\n'
    if logs=$(journalctl -k -b -q --since '2 minutes ago' --no-pager 2>&1); then
        if [ -n "$logs" ]; then
            printf '%s\n' "$logs" | awk '
                /csi fifo overflow|csi size err|fs\/fe mis|Oops|rtmutex deadlock/ {
                    count++; last=$0
                }
                END {
                    printf "Matching messages: %d\n", count
                    if (count) print last
                }'
        else
            echo "No kernel messages visible in this time window"
        fi
    else
        printf '%s\n' "$logs"
    fi
fi
ROBOT_SENSOR_CHECK
