
import math
import time
import requests

ROBOT_IP = "192.168.2.196"
DELTA = 0.03
DURATION = 3.0
RATE = 100

URL = (
    f"http://{ROBOT_IP}:56322/rpc/"
    "aimdk.protocol.MotionControlJointService/"
    "GetArmJointState"
)

JOINTS = [
    "left_shoulder_pitch_joint",
    "left_shoulder_roll_joint",
    "left_shoulder_yaw_joint",
    "left_elbow_joint",
    "left_wrist_roll_joint",
    "left_wrist_pitch_joint",
    "left_wrist_yaw_joint",
    "right_shoulder_pitch_joint",
    "right_shoulder_roll_joint",
    "right_shoulder_yaw_joint",
    "right_elbow_joint",
    "right_wrist_roll_joint",
    "right_wrist_pitch_joint",
    "right_wrist_yaw_joint",
]

TARGET = "right_elbow_joint"
ELBOW_LIMITS = (-0.95993, 1.74533)

def read_joints():
    response = requests.post(URL, json={}, timeout=3)
    response.raise_for_status()
    data = response.json()

    if str(data.get("header", {}).get("code")) != "0":
        raise RuntimeError("Joint feedback RPC failed")

    states = data["states"]
    positions = {j["name"]: float(j["position"])
                 for j in states}

    if not all(name in positions for name in JOINTS):
        raise RuntimeError("Missing joint feedback")

    values = [positions[name] for name in JOINTS]

    if not all(math.isfinite(v) for v in values):
        raise RuntimeError("Invalid joint positions")

    return values

def main():
    start = read_joints()
    index = JOINTS.index(TARGET)

    target = start[index] + DELTA

    if not ELBOW_LIMITS[0] <= target <= ELBOW_LIMITS[1]:
        raise RuntimeError("Target exceeds elbow limits")

    print("AGIBOT A3 Ultra - Right Arm")
    print("Mode: DRY RUN ONLY")
    print("Start elbow:", round(start[index], 5))
    print("Target elbow:", round(target, 5))
    print("Duration:", DURATION, "seconds")

    steps = int(DURATION * RATE)

    for step in range(steps + 1):
        t = step / steps

        # Smoothstep interpolation
        s = 3 * t**2 - 2 * t**3

        command = start.copy()
        command[index] = start[index] + DELTA * s

        # Future ROS2 command would contain all 14
        # joint positions from this array.
        if step % 50 == 0 or step == steps:
            print(
                f"t={t * DURATION:.2f}s "
                f"elbow={command[index]:.5f}"
            )

    print("\nTrajectory generated successfully.")
    print("No movement commands were sent.")

if __name__ == "__main__":
    main()
