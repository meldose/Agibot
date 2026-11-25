bash <<'ACCEL_CHECK'
shopt -s nullglob

printf 'Computer: %s\n' "$(hostname -s)"
echo "Keep the robot stationary for three samples."

found=0
readings=0

for device in /sys/bus/iio/devices/iio:device*; do
    [ -r "$device/name" ] || continue
    name=$(cat "$device/name") || continue
    axes=()

    for axis in x y z; do
        raw="$device/in_accel_${axis}_raw"
        input="$device/in_accel_${axis}_input"
        if [ -r "$raw" ]; then
            axes+=("$raw")
        elif [ -r "$input" ]; then
            axes+=("$input")
        fi
    done

    if ((${#axes[@]} == 0)); then
        printf '%s (%s): no exposed accelerometer axes\n' "$name" "${device##*/}"
        continue
    fi

    found=1
    printf '\n%s (%s)\n' "$name" "${device##*/}"

    for file in "$device"/in_accel_scale "$device"/in_accel_{x,y,z}_scale; do
        [ -r "$file" ] || continue
        value=$(cat "$file") || continue
        printf '  %s: %s\n' "${file##*/}" "$value"
    done

    for sample in 1 2 3; do
        printf 'Sample %s\n' "$sample"
        for file in "${axes[@]}"; do
            if value=$(cat "$file" 2>/dev/null); then
                printf '  %s: %s\n' "${file##*/}" "$value"
                readings=$((readings + 1))
            else
                printf '  %s: read failed\n' "${file##*/}"
            fi
        done
        [ "$sample" -eq 3 ] || sleep 1
    done
done

if ((found == 0)); then
    echo "Accelerometer unverified: no readable IIO acceleration axes found."
elif ((readings == 0)); then
    echo "Accelerometer unverified: all sample reads failed."
else
    printf 'Successful axis reads: %s. A full three-axis check has X, Y, and Z in each sample.\n' \
        "$readings"
fi
ACCEL_CHECK
