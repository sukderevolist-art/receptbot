import asyncio
import json
import logging
from urllib.parse import urlencode
from urllib.request import Request, urlopen

try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass

from config import load_settings
from database import init_db, is_recipe_published, save_published_recipe
from formatter import format_recipe_post
from parser import Recipe, find_recipe
from scheduler import start_scheduler


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

settings = load_settings()
API_URL = f"https://api.telegram.org/bot{settings.bot_token}"


async def handle_message(message: dict) -> None:
    text = (message.get("text") or "").strip()
    chat_id = message["chat"]["id"]

    if text.startswith("/start"):
        await send_message(
            chat_id,
        "Бот запущен. Я буду публиковать рецепты в канал каждый день по расписанию."
        )
        return

    if text.startswith("/test"):
        await send_message(chat_id, "Ищу рецепт для проверки...")
        recipe = await _get_fresh_recipe()
        if not recipe:
            await send_message(chat_id, "Не удалось найти подходящий рецепт. Подробности записаны в лог.")
            return

        await send_message(chat_id, format_recipe_post(recipe))
        return

    if text.startswith("/post_now"):
        await send_message(chat_id, "Ищу рецепт и готовлю публикацию...")
        published = await publish_recipe()
        if published:
            await send_message(chat_id, f"Готово. Рецепт опубликован в {settings.channel_id}.")
        else:
            await send_message(chat_id, "Не получилось опубликовать рецепт. Подробности записаны в лог.")
        return

    await send_message(chat_id, "Доступные команды: /start, /test, /post_now")


async def publish_recipe() -> bool:
    recipe = await _get_fresh_recipe()
    if not recipe:
        logger.error("Не удалось найти подходящий рецепт для публикации")
        return False

    post = format_recipe_post(recipe)

    try:
        await send_message(settings.channel_id, post)
    except Exception:
        logger.exception("Ошибка при публикации рецепта в канал %s", settings.channel_id)
        return False

    save_published_recipe(recipe.title, recipe.source_url)
    logger.info("Рецепт опубликован: %s (%s)", recipe.title, recipe.source_url)
    return True


async def _get_fresh_recipe(max_attempts: int = 5) -> Recipe | None:
    for attempt in range(1, max_attempts + 1):
        try:
            recipe = await asyncio.to_thread(find_recipe)
        except Exception:
            logger.exception("Ошибка при поиске рецепта, попытка %d", attempt)
            continue

        if is_recipe_published(recipe.source_url):
            logger.info("Рецепт уже публиковался: %s", recipe.source_url)
            continue

        return recipe

    return None


async def send_message(chat_id: int | str, text: str) -> dict:
    return await asyncio.to_thread(
        _telegram_request,
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        },
    )


async def polling_loop() -> None:
    offset = 0

    while True:
        try:
            result = await asyncio.to_thread(
                _telegram_request,
                "getUpdates",
                {"offset": offset, "timeout": 30, "allowed_updates": json.dumps(["message"])},
            )
        except Exception as error:
            logger.warning("Не удалось получить сообщения Telegram: %s", error)
            await asyncio.sleep(5)
            continue

        for update in result.get("result", []):
            offset = max(offset, update["update_id"] + 1)
            message = update.get("message")
            if not message:
                continue

            try:
                await handle_message(message)
            except Exception:
                logger.exception("Ошибка при обработке сообщения")


def _telegram_request(method: str, params: dict) -> dict:
    data = urlencode(params).encode("utf-8")
    request = Request(f"{API_URL}/{method}", data=data, method="POST")

    with urlopen(request, timeout=45) as response:
        payload = json.loads(response.read().decode("utf-8"))

    if not payload.get("ok"):
        raise RuntimeError(f"Telegram API error: {payload}")

    return payload


async def main() -> None:
    init_db()
    logger.info("Бот запускается. Канал: %s", settings.channel_id)
    start_scheduler(publish_recipe, settings.post_time, settings.timezone)
    await polling_loop()


if __name__ == "__main__":
    asyncio.run(main())
