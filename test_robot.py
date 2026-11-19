
from robot import Robot


robot = Robot(ip="192.168.2.196")

try:
    print("AGIBOT A3 Ultra")
    print("=" * 45)

    print("\nCurrent action:")
    print(robot.get_action())

    print("\nAvailable actions:")
    for action in robot.get_available_actions():
        print(" -", action)

    print("\nRight arm:")
    for name, state in robot.get_right_arm().items():
        print(f"{name:<30} {state['position']:.4f}")

    print("\nLeft arm:")
    for name, state in robot.get_left_arm().items():
        print(f"{name:<30} {state['position']:.4f}")

finally:
    robot.close()
