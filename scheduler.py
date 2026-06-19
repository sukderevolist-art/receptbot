import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


logger = logging.getLogger(__name__)


def start_scheduler(post_job, post_time: str, timezone: str) -> asyncio.Task:
    hour, minute = _parse_post_time(post_time)
    logger.info("Планировщик запущен: каждый день в %02d:%02d, %s", hour, minute, timezone)
    return asyncio.create_task(_scheduler_loop(post_job, hour, minute, timezone))


async def _scheduler_loop(post_job, hour: int, minute: int, timezone: str) -> None:
    tz = ZoneInfo(timezone)

    while True:
        now = datetime.now(tz)
        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)

        delay = (next_run - now).total_seconds()
        await asyncio.sleep(delay)

        try:
            await post_job()
        except Exception:
            logger.exception("Ошибка при выполнении публикации по расписанию")


def _parse_post_time(post_time: str) -> tuple[int, int]:
    try:
        hour_text, minute_text = post_time.split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
    except ValueError as error:
        raise RuntimeError("POST_TIME должен быть в формате HH:MM") from error

    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise RuntimeError("POST_TIME должен быть реальным временем, например 10:00")

    return hour, minute
