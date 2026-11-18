
import time
import requests

URL = (
    "http://192.168.2.196:56322/rpc/"
    "aimdk.protocol.MotionControlJointService/"
    "GetArmJointState"
)

session = requests.Session()

try:
    while True:
        response = session.post(
            URL, json={}, timeout=3
        )
        response.raise_for_status()
        data = response.json()

        if str(data.get("header", {}).get("code")) != "0":
            print("RPC error:", data)
            break

        print("\033[2J\033[H", end="")

        for joint in data.get("states", []):
            print(
                f"{joint['name']:<30} "
                f"{joint['position']:>8.4f}"
            )

        time.sleep(0.2)

except KeyboardInterrupt:
    print("\nMonitoring stopped.")
except requests.RequestException as exc:
    print("\nConnection error:", exc)
