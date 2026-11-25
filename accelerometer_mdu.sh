bash <<'ACCEL_CHECK'
shopt -s nullglob

host=$(hostname -s) || exit 1
kernel=$(uname -r)
printf 'Computer: %s\nKernel: %s\n' "$host" "$kernel"

if [[ ${host,,} != mdu ]]; then
    echo "Run this accelerometer check on MDU."
    exit 1
fi

device=/sys/bus/i2c/devices/3-0018
if [[ -d "$device" ]]; then
    printf 'I2C device: %s\n' "${device##*/}"
    for field in name modalias; do
        [[ -r "$device/$field" ]] || continue
        printf '%s: %s\n' "$field" "$(cat "$device/$field")"
    done
    if driver=$(readlink "$device/driver"); then
        printf 'Driver: %s\n' "${driver##*/}"
    else
        echo "Driver: unbound"
    fi
else
    echo "The previously observed I2C device 3-0018 is absent."
fi

printf '\n=== Kernel configuration ===\n'
if [[ -r /proc/config.gz ]]; then
    zcat /proc/config.gz | grep -Ei 'BMI08|BMG160'
elif [[ -r "/boot/config-$kernel" ]]; then
    grep -Ei 'BMI08|BMG160' "/boot/config-$kernel"
else
    echo "Kernel configuration unavailable"
fi

printf '\n=== Accelerometer readings ===\n'
echo "Keep the robot stationary."
found=0
passed=0

for iio in /sys/bus/iio/devices/iio:device*; do
    axes=()
    for axis in x y z; do
        for suffix in raw input; do
ACCEL_CHECKNVERIFIED: no readable IIO accelerometer axes found."samples."
Computer: mdu
Kernel: 6.1.118
I2C device: 3-0018
name: bmi088_accel
modalias: of:NaccelT(null)Cbosch,bmi088_accel
Driver: unbound

=== Kernel configuration ===
CONFIG_BMI088_ACCEL=y
CONFIG_BMI088_ACCEL_SPI=y
CONFIG_BMG160=y
CONFIG_BMG160_I2C=y
CONFIG_BMG160_SPI=y

=== Accelerometer readings ===
Keep the robot stationary.
UNVERIFIED: no readable IIO accelerometer axes found.
