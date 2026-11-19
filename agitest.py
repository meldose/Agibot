
import requests

BASE = "http://192.168.2.196:56322/rpc/aimdk.protocol.MotionControlActionService"

def call_api(method):
    response = requests.post(
        f"{BASE}/{method}",
        json={},
        timeout=10
    )
    response.raise_for_status()
    return response.json()

# Read robot state
state = call_api("GetAction")
print("Current state:", state["info"]["current_action"])
print("Status:", state["info"]["status"])

# Read available actions
actions = call_api("GetAvailableActions")
print("\nAvailable actions:")
for item in actions.get("commands", []):
    print("-", item["ext_action"])
