import re


def say_hello():
    import json
    from urllib.request import Request, urlopen
    from uuid import uuid4

    payload = {
        "text": "Hello! I am your A3 Ultra assistant.",
        "priority_level": "INTERACTION_L6",
        "domain": "ai_planner",
        "trace_id": uuid4().hex,
        "is_interrupted": False,
    }
    request = Request(
        "http://10.42.10.10:59301/rpc/aimdk.protocol.TTSService/PlayTTS",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=5) as response:
            result = json.load(response)
    except (OSError, ValueError) as error:
        print(f"Speech request failed: {error}")
        return

    if isinstance(result, dict) and result.get(
        "is_sucess", result.get("is_success")
    ) is True:
        print("Speech request accepted. Listen for the greeting.")
    else:
        print("Unexpected or rejected speech response:", result)


GESTURES = {
    "both thumbs up": ("BOTH_THUMBS_UP", "双手点赞/20260728_163231_ta.mcap", 9625),
    "say cheese": ("SAY_CHEESE", "右手比耶/danshouqiezi_Skeleton0_ta.mcap", 3750),
    "cheer": ("CHEER", "右手加油/jiayou-R_Skeleton0_ta.mcap", 3584),
    "check watch": ("CHECK_WATCH", "看看手表/kanbiao_Skeleton0_ta.mcap", 8000),
    "look left": ("LOOK_LEFT", "向左看看/wbc.mcap", 5500),
    "look right": ("LOOK_RIGHT", "向右看看/wbc.mcap", 5500),
    "thanks": ("THANKS", "谢谢夸奖/wbc.mcap", 4000),
    "wave hand": ("WAVE_HAND", "右手挥手/huishou_Skeleton0.mcap", 13050),
    "thumbs up": ("THUMBS_UP", "右手点赞/danshoudianzan_Skeleton0_ta.mcap", 6800),
    "finger heart": ("FINGER_HEART", "手指比心/手指比心_ta.mcap", 6709),
    "nod": ("NOD", "点头认可/wbc.mcap", 2517),
}


def play_gesture(gesture):
    import json
    from urllib.request import Request, urlopen

    task, filename, duration_ms = gesture
    payload = {
        "motion_id": "/agibot/data/resources/default/motion/" + filename,
        "duration_ms": duration_ms,
        "cmd_end": True,
        "cmd_pause": False,
        "cmd_reset": False,
        "cmd_repeat": False,
    }
    request = Request(
        "http://10.42.10.12:56444/rpc/"
        "aimdk.protocol.MotionCommandService/SendMotionCommand",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=5) as response:
            result = json.load(response)
    except (OSError, ValueError) as error:
        print(f"Motion request failed: {error}")
        return

    if isinstance(result, dict) and result.get("state") == "CommonState_SUCCESS":
        print(f"Motion request accepted: {task}")
    else:
        print("Motion request rejected or unexpected response:", result)


def answer_weather(command):
    import json
    import re
    from urllib.parse import urlencode
    from urllib.request import Request, urlopen
    from uuid import uuid4

    question = re.fullmatch(
        r"(?:(?:what is|what's) the )?weather in (.+?)\\??",
        command.strip(),
        flags=re.IGNORECASE,
    )
    if question is None:
        return False

    city = question[1].strip()
    try:
        search = urlencode({"name": city, "count": 1, "language": "en"})
        with urlopen(
            "https://geocoding-api.open-meteo.com/v1/search?" + search,
            timeout=8,
        ) as response:
            places = json.load(response).get("results", [])
        if not places:
            print(f"I couldn't find a city named {city}.")
            return True

        place = places[0]
        query = urlencode({
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "current": "temperature_2m",
            "temperature_unit": "fahrenheit",
        })
        with urlopen(
            "https://api.open-meteo.com/v1/forecast?" + query,
            timeout=8,
        ) as response:
            temperature = json.load(response)["current"]["temperature_2m"]
        if temperature is None:
            print(f"Current temperature is unavailable for {place['name']}.")
            return True
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Weather lookup failed: {error}")
        return True

    location = ", ".join(
        place[key] for key in ("name", "admin1", "country") if place.get(key)
    )
    answer = f"It is {temperature:.0f} degrees Fahrenheit in {location}."
    print(answer)

    payload = {
        "text": answer,
        "priority_level": "INTERACTION_L6",
        "domain": "ai_planner",
        "trace_id": uuid4().hex,
        "is_interrupted": False,
    }
    request = Request(
        "http://10.42.10.10:59301/rpc/aimdk.protocol.TTSService/PlayTTS",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=5) as response:
            result = json.load(response)
        if not isinstance(result, dict) or result.get(
            "is_sucess", result.get("is_success")
        ) is not True:
            print(f"Speaker request rejected: {result}")
    except (OSError, ValueError) as error:
        print(f"Speaker request failed: {error}")
    return True


def plan(command):
    steps = re.split(
        r'\b(?:and then|then|and)\b',
        command.lower()
    )

    tasks = []

    for step in steps:
        if "open" in step and "hand" in step:
            tasks.append("OPEN_HAND")
        elif "close" in step and "hand" in step:
            tasks.append("CLOSE_HAND")
        elif "wave" in step:
            tasks.append("WAVE_HAND")
        elif "hello" in step:
            tasks.append("SAY_HELLO")
        elif "walk" in step:
            tasks.append("WALK")
        elif "stop" in step:
            tasks.append("STOP")
        else:
            tasks.append("UNKNOWN: " + step.strip())

    return tasks

print("AGIBOT AI TASK PLANNER")

while True:
    command = input("\nEnter task: ")

    if command.lower() == "exit":
        break

    key = " ".join(command.casefold().replace("_", " ").split())
    gesture = GESTURES.get("wave hand" if key == "wave" else key)
    if gesture is not None:
        print("\nGenerated task sequence:")
        print(f"1. {gesture[0]}")
        play_gesture(gesture)
        continue
    if key == "hi":
        command = "say hello"
    if answer_weather(command):
        continue
    tasks = plan(command)

    print("\nGenerated task sequence:")

    for i, task in enumerate(tasks, 1):
        print(f"{i}. {task}")

    if tasks == ["SAY_HELLO"]:
        say_hello()
    else:
        print("\nSimulation only. No robot movement.")
