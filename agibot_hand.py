
import requests

ROBOT_IP = "192.168.2.196"

BASE_URL = (
    f"http://{ROBOT_IP}:56322/rpc/"
    "aimdk.protocol.MotionControlActionService"
)

def rpc(method, payload=None):
    response = requests.post(
        f"{BASE_URL}/{method}",
        json=payload if payload is not None else {},
        timeout=5
    )
    response.raise_for_status()

    result = response.json()
    if str(result.get("header", {}).get("code")) != "0":
        raise RuntimeError(f"RPC failed: {result}")

    return result

def main():
    print("Connecting to AGIBOT A3 Ultra...")

    state = rpc("GetAction")
    info = state["info"]

    print("Motion state:", info["current_action"])
    print("Action status:", info["status"])

    actions = rpc("GetAvailableActions", {
        "header": {
            "timestamp": {
                "seconds": "0",
                "nanos": 0,
                "ms_since_epoch": "0"
            }
        }
    })

    print("\nAvailable actions:")
    for item in actions.get("commands", []):
        print("-", item["ext_action"])

    print("\nHand control: NOT ACTIVATED")
    print("No movement commands were sent.")

if __name__ == "__main__":
    main()
