from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("America/Argentina/San_Luis")
DISPLAY_FORMAT = "%d/%m/%Y %H:%M:%S"


def now_utc():
    return datetime.now(timezone.utc)


def now_local():
    return now_utc().astimezone(LOCAL_TZ)


def utc_to_local(value):
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(LOCAL_TZ)


def format_datetime_ar(value):
    local = utc_to_local(value)
    return "" if local is None else local.strftime(DISPLAY_FORMAT)


def local_day_bounds(date_value):
    start = datetime.combine(date_value, time.min, LOCAL_TZ)
    end = datetime.combine(date_value, time.max, LOCAL_TZ)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)
