
import argparse
import requests

ROBOT = "192.168.2.196"
URL = (
    f"http://{ROBOT}:56444/rpc/"
    "aimdk.protocol.MotionCommandService/"
    "SendMotionCommand"
)

# Official documentation example.
# This resource must exist on the robot.
HANDSHAKE = (
    "/agibot/data/resources/default/motion/"
    "handshake/woshou1_Skeleton0.mcap"
)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually request motion playback"
    )
    args = parser.parse_args()

    payload = {
        "motion_id": HANDSHAKE,
        "duration_ms": 10000,
        "cmd_end": True,
        "cmd_pause": False,
        "cmd_reset": False,
        "cmd_repeat": False
    }

    print("Robot:", ROBOT)
    print("Motion:", HANDSHAKE)

    if not args.execute:
        print("DRY RUN: no movement command sent")
        print("Use --execute only after safety checks.")
        return

    confirmation = input(
        "Type PLAY to start the handshake motion: "
    )
    if confirmation != "PLAY":
        print("Cancelled.")
        return

    try:
        response = requests.post(
            URL, json=payload, timeout=5
        )
        response.raise_for_status()
        result = response.json()
        print("Robot response:", result)

        if (
            str(result.get("header", {}).get("code")) == "0"
            and result.get("state") == "CommonState_SUCCESS"
        ):
            print("Playback request accepted.")
        else:
            print("Playback not confirmed.")

    except requests.RequestException as exc:
        print("HTTP error:", exc)

if __name__ == "__main__":
    main()
