"""캘린더/일정 추출. AJAX API가 동작하는 유일한 기능."""

import time
import httpx
from config import BASE_URL, REQUEST_TIMEOUT, CURRENT_SEMESTER


AJAX_ENDPOINT = f"{BASE_URL}/lib/ajax/service.php"


def _semester_start_timestamp() -> int:
    """현재 학기 시작일의 Unix timestamp를 반환한다."""
    year = int(CURRENT_SEMESTER.split("-")[0])
    sem = int(CURRENT_SEMESTER.split("-")[1])
    if sem == 1:
        import datetime
        return int(datetime.datetime(year, 3, 1).timestamp())
    else:
        import datetime
        return int(datetime.datetime(year, 9, 1).timestamp())


async def extract_calendar_events(cookies: dict, sesskey: str) -> list[dict]:
    """AJAX API로 캘린더 이벤트를 추출한다."""
    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT,
        cookies=cookies,
    ) as client:
        semester_start = _semester_start_timestamp()
        payload = [
            {
                "index": 0,
                "methodname": "core_calendar_get_action_events_by_timesort",
                "args": {
                    "limitnum": 50,
                    "timesortfrom": semester_start,
                },
            }
        ]

        response = await client.post(
            AJAX_ENDPOINT,
            params={"sesskey": sesskey, "info": "core_calendar_get_action_events_by_timesort"},
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

        events = []
        if isinstance(data, list) and len(data) > 0:
            item = data[0]
            if not item.get("error"):
                raw_events = item.get("data", {}).get("events", [])
                for evt in raw_events:
                    events.append({
                        "id": evt.get("id"),
                        "name": evt.get("name"),
                        "description": evt.get("description", ""),
                        "course_name": evt.get("course", {}).get("fullname", ""),
                        "time_start": evt.get("timestart"),
                        "time_duration": evt.get("timeduration"),
                        "event_type": evt.get("eventtype"),
                        "url": evt.get("url", ""),
                    })

    print(f"  [CALENDAR] {len(events)}개 이벤트")
    return events
