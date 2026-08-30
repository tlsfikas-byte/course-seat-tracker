import os
import json
import time
import requests

CRN_TO_WATCH = "10221"
SEARCH_URL = "https://courseofferings.colgate.edu/v1/courses/search?keyword=&termCode=202601&coreArea=&inquiryArea=&liberalArtsPracticeArea=&meetTimeMorning=&meetTimeAfternoon=&meetTimeEvening=&openCoursesOnly="
STATE_FILE = "state.json"
HOURLY_INTERVAL_SECONDS = 60 * 60  # only send a routine update this often

COOKIE_HEADER = os.environ["COOKIE_HEADER"]  # full raw Cookie header string
NTFY_TOPIC = os.environ["NTFY_TOPIC"]


def send_notification(title, message, urgent=False):
    requests.post(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=message.encode("utf-8"),
        headers={
            "Title": title,
            "Priority": "urgent" if urgent else "default",
        },
    )


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            data = json.load(f)
            return {
                "lastStatus": data.get("lastStatus"),
                "lastNotifyTime": data.get("lastNotifyTime", 0),
            }
    return {"lastStatus": None, "lastNotifyTime": 0}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def main():
    response = requests.get(SEARCH_URL, headers={"Cookie": COOKIE_HEADER})

    if response.status_code in (401, 403):
        send_notification(
            "Cookie expired",
            "Log in and update the COOKIE_HEADER secret.",
            urgent=True,
        )
        return

    response.raise_for_status()

    try:
        courses = response.json()
    except ValueError:
        send_notification(
            "Cookie expired",
            "Got a login page instead of data — update the COOKIE_HEADER secret.",
            urgent=True,
        )
        return

    course = next((c for c in courses if c["CRN"] == CRN_TO_WATCH), None)

    if course is None:
        send_notification(
            "Course not found",
            f"CRN {CRN_TO_WATCH} missing from results — check term code.",
            urgent=True,
        )
        return

    current_status = course["STATUS"]
    state = load_state()
    last_status = state["lastStatus"]
    last_notify_time = state["lastNotifyTime"]
    now = time.time()

    print(f"{course['DISPLAY_KEY']}: {current_status} (seats: {course['SEATS']})")

    status_changed = last_status is not None and current_status != last_status

    if status_changed:
        urgent = current_status != "Closed"
        send_notification(
            course["DISPLAY_KEY"],
            f"{current_status} — {course['SEATS']}",
            urgent=urgent,
        )
        state["lastNotifyTime"] = now
    elif now - last_notify_time >= HOURLY_INTERVAL_SECONDS:
        send_notification(
            course["DISPLAY_KEY"],
            f"{current_status} — {course['SEATS']}",
        )
        state["lastNotifyTime"] = now

    state["lastStatus"] = current_status
    save_state(state)


if __name__ == "__main__":
    main()
