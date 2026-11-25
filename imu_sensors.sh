
bash <<'ROBOT_EXTRA_CHECK'
host=$(hostname -s) || exit 1

case "${host,,}" in
    adu) computer="ADU" ;;
    mdu) computer="MDU" ;;
    hdu) computer="DU (HDU)" ;;
    du)  computer="DU" ;;
    *)
        printf 'Computer detected: UNKNOWN (hostname: %s)\n' "$host"
        exit 1
        ;;
esac

printf 'Computer detected: %s (hostname: %s)\n' "$computer" "$host"
printf 'Last boot: %s\n' "$(uptime -s)"

case "${host,,}" in
    mdu)
        printf '\n=== IMU readings ===\n'
        echo "Keep the robot stationary."
        found=0

        for name in /sys/bus/iio/devices/iio:device*/name; do
            [ -r "$name" ] || continue
            dir=${name%/name}
            printf '\n%s (%s)\n' "$(cat "$name")" "${dir##*/}"

            for sample in 1 2 3; do
                printf 'Sample %s\n' "$sample"
                for kind in anglvel accel; do
                    for axis in x y z; do
                        key="in_${kind}_${axis}_raw"
                        [ -r "$dir/$key" ] || continue
                        value=$(cat "$dir/$key") || continue
                        printf '  %s: %s\n' "$key" "$value"
                        found=1
                    done
                done
                [ "$sample" -eq 3 ] || sleep 1
            done
        done

        [ "$found" -eq 1 ] || echo "No readable gyro or accelerometer axes"
        ;;

    hdu|du)
        printf '\n=== Saved lavalier recordings ===\n'
        found=0
        for wav in /tmp/robot-lavalier.*.wav; do
            [ -s "$wav" ] || continue
            ls -lh -- "$wav"
            found=1
        done
        [ "$found" -eq 1 ] || echo "No saved lavalier recording found in /tmp"

        printf '\n=== Camera-driver messages from the last two minutes ===\n'
        if log=$(journalctl -k -b --since '2 minutes ago' --no-pager 2>&1); then
            if [ -z "$log" ] || [ "$log" = "-- No entries --" ]; then
                echo "No kernel messages visible in this window"
            else
                printf '%s\n' "$log" |
                    awk '/csi fifo overflow|csi size err|fs\/fe mis|Oops|rtmutex deadlock/ {
                        count++; last=$0
                    } END {
                        printf "Matching messages: %d\n", count
                        if (count) print last
                    }'
            fi
        else
            printf 'Could not read the kernel journal:\n%s\n' "$log"
        fi
        ;;

    adu)
        printf '\n=== Power-supply telemetry ===\n'
        found=0
        for supply in /sys/class/power_supply/*; do
            [ -r "$supply/type" ] || continue
            found=1
            printf '\n%s (%s)\n' "${supply##*/}" "$(cat "$supply/type")"

            for key in status online capacity voltage_now current_now; do
                [ -r "$supply/$key" ] || continue
                value=$(cat "$supply/$key") || continue
                case "$key" in
                    capacity)    printf '  %s: %s%%\n' "$key" "$value" ;;
                    voltage_now) printf '  %s: %s uV\n' "$key" "$value" ;;
                    current_now) printf '  %s: %s uA\n' "$key" "$value" ;;
                    *)           printf '  %s: %s\n' "$key" "$value" ;;
                esac
            done
        done
        [ "$found" -eq 1 ] || echo "No power supplies visible in sysfs"
        ;;
esac
ROBOT_EXTRA_CHECK
