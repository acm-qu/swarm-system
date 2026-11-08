#!/bin/sh
# Everything a robot needs installed, in one place. Runs as root.
#
# The hub runs this once when you press Add robot, and again on Update only if this file has
# changed since (it keeps a stamp in ~/swarm-agent/.setup-done). To run it by hand on a robot:
#   sudo sh ~/swarm-agent/setup_robot.sh <robot user>
#
# Every part is optional for the agent: if a package can't be installed, the part that needs it
# stays disabled and the agent still connects to the hub. Safe to run again.
#
# To add a package: add a line to PACKAGES below (name, then what needs it), then press Update.

set -u

PACKAGES="
python3-gpiozero   wheels and ultrasonic sensor (robot_movement.py, sensors.py)
python3-lgpio      the GPIO backend gpiozero uses on a Pi 5 and newer Raspberry Pi OS
python3-smbus      arm and gyro: talk to the PCA9685 and MPU-6050 over I2C
i2c-tools          i2cdetect, to check the arm board and gyro are wired up
python3-opencv     camera (camera.py)
python3-tk         status window on the robot's desktop (status_ui.py)
"

# Software I2C buses. Each device has its own, so a wiring fault on one can't stop the other.
#   bus 3: the arm's PCA9685, GPIO5 = SDA (pin 29), GPIO6 = SCL (pin 31), see robot_movement.py
#   bus 4: the MPU-6050 gyro, GPIO19 = SDA (pin 35), GPIO26 = SCL (pin 37), see sensors.py
ARM_I2C_OVERLAY="dtoverlay=i2c-gpio,i2c_gpio_sda=5,i2c_gpio_scl=6,bus=3"
GYRO_I2C_OVERLAY="dtoverlay=i2c-gpio,i2c_gpio_sda=19,i2c_gpio_scl=26,bus=4"

ROBOT_USER="${1:-${SUDO_USER:-}}"
APT_OPTS="-q -y -o DPkg::Lock::Timeout=180"   # wait if the Pi is busy with its own updates
reboot_needed=0

say() { echo "[setup] $*"; }

if [ "$(id -u)" != "0" ]; then
    echo "Run this as root: sudo sh $0 <robot user>" >&2
    exit 1
fi
export DEBIAN_FRONTEND=noninteractive

# 1. Packages ------------------------------------------------------------------------------
say "Updating the package list"
if ! apt-get $APT_OPTS update; then
    say "Couldn't download the package list. Does the robot have internet?"
    exit 2
fi

wanted=""
for pkg in $(echo "$PACKAGES" | awk 'NF { print $1 }'); do
    if apt-cache policy "$pkg" 2>/dev/null | grep -q "Candidate: [^(]"; then
        wanted="$wanted $pkg"
    else
        say "Skipped $pkg: this system has no such package"
    fi
done

say "Installing:$wanted"
if ! apt-get $APT_OPTS install --no-install-recommends $wanted; then
    say "Installing the packages failed (see the messages above)"
    exit 1
fi

# 2. I2C buses for the arm and gyro --------------------------------------------------------
if [ -f /boot/firmware/config.txt ]; then
    boot_config=/boot/firmware/config.txt       # Raspberry Pi OS Bookworm and newer
else
    boot_config=/boot/config.txt                # older Raspberry Pi OS
fi

# add_overlay <line> <what it is>: append the line to the boot config once.
add_overlay() {
    if grep -q "^[[:space:]]*$1[[:space:]]*$" "$boot_config"; then
        say "$2 is already turned on in $boot_config"
        return
    fi
    [ -f "$boot_config.swarm-backup" ] || cp "$boot_config" "$boot_config.swarm-backup"
    printf '\n[all]\n# Swarm: %s\n%s\n' "$2" "$1" >> "$boot_config"
    say "Turned on $2 in $boot_config (works after a reboot)"
    reboot_needed=1
}

if [ -f "$boot_config" ]; then
    add_overlay "$ARM_I2C_OVERLAY" "the arm's I2C bus 3 on GPIO5 (SDA) / GPIO6 (SCL)"
    add_overlay "$GYRO_I2C_OVERLAY" "the gyro's I2C bus 4 on GPIO19 (SDA) / GPIO26 (SCL)"
else
    say "No $boot_config, so the I2C buses weren't set up. Is this a Raspberry Pi?"
fi

# /dev/i2c-* only exists with the i2c-dev module loaded; load it now and on every boot.
echo "i2c-dev" > /etc/modules-load.d/swarm-i2c.conf
modprobe i2c-dev 2>/dev/null || true

# 3. Permissions ---------------------------------------------------------------------------
# The agent runs as the robot's user, which needs these groups for GPIO pins, I2C and the camera.
if [ -n "$ROBOT_USER" ] && id "$ROBOT_USER" >/dev/null 2>&1; then
    for group in gpio i2c video; do
        if getent group "$group" >/dev/null; then
            usermod -aG "$group" "$ROBOT_USER"
        fi
    done
    say "$ROBOT_USER can use GPIO, I2C and the camera"
fi

say "Done"
[ "$reboot_needed" = 1 ] && echo "SWARM_REBOOT_NEEDED"
exit 0
