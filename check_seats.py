import os
import json
import requests

CRN_TO_WATCH = "10221"
SEARCH_URL = "https://courseofferings.colgate.edu/v1/courses/search?keyword=&termCode=202601&coreArea=&inquiryArea=&liberalArtsPracticeArea=&meetTimeMorning=&meetTimeAfternoon=&meetTimeEvening=&openCoursesOnly="
STATE_FILE = "state.json"

COOKIE_HEADER = os.environ["COOKIE_HEADER"]  # full raw Cookie header string
NTFY_TOPIC = os.environ["NTFY_TOPIC"]


def send_notification(title, message, urgent=False):
    requests.post(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=message.encode("utf-8"),
        headers={
            "Title": title,
            "Priority": "urgent" if urgent else "default",
            "Tags": "rotating_light" if urgent else "warning",
        },
    )


def load_last_status():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f).get("lastStatus")
    return None


def save_last_status(status):
    with open(STATE_FILE, "w") as f:
        json.dump({"lastStatus": status}, f)


def main():
    response = requests.get(SEARCH_URL, headers={"Cookie": COOKIE_HEADER})

    if response.status_code in (401, 403):
        send_notification(
            "Seat tracker: cookie expired",
            "Your Colgate session cookie expired. Log in and paste a fresh one into the COOKIE_HEADER secret.",
            urgent=True,
        )
        return

    response.raise_for_status()

    try:
        courses = response.json()
    except ValueError:
        # Got a 200 OK but the body wasn't JSON - almost always means the
        # session cookie expired and we got redirected to an HTML login page instead.
        send_notification(
            "Seat tracker: cookie expired",
            "Got a non-JSON response (likely a login page). Log in and paste a fresh cookie into the COOKIE_HEADER secret.",
            urgent=True,
        )
        return

    course = next((c for c in courses if c["CRN"] == CRN_TO_WATCH), None)

    if course is None:
        send_notification(
            "Seat tracker: course not found",
            f"CRN {CRN_TO_WATCH} wasn't in the search results. The term code or filters may need updating.",
            urgent=True,
        )
        return

    current_status = course["STATUS"]
    last_status = load_last_status()
    print(f"{course['DISPLAY_KEY']}: {current_status} (seats: {course['SEATS']})")

    urgent = current_status != "Closed"
    send_notification(
        f"{course['DISPLAY_KEY']}: {current_status}",
        f"Seats: {course['SEATS']}" + (" — GO REGISTER NOW!" if urgent else ""),
        urgent=urgent,
    )

    save_last_status(current_status)


if __name__ == "__main__":
    main()
