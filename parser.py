import json
import logging
import random
import re
from dataclasses import dataclass
from html import unescape
from typing import Any
from urllib.parse import urljoin
from urllib.request import Request, urlopen

try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass


logger = logging.getLogger(__name__)

BASE_URL = "https://www.edimdoma.ru"
RECIPES_URL = f"{BASE_URL}/retsepty"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)

@dataclass(frozen=True)
class Recipe:
    title: str
    ingredients: list[str]
    steps: list[str]
    source_url: str
    tip: str = ""


FALLBACK_RECIPE = Recipe(
    title="Курица в сливочном соусе",
    ingredients=[
        "куриное филе — 500 г",
        "сливки — 200 мл",
        "чеснок — 2 зубчика",
        "лук — 1 штука",
        "растительное масло — 1 столовая ложка",
        "соль и перец — по вкусу",
    ],
    steps=[
        "нарежьте курицу небольшими кусочками",
        "обжарьте лук и курицу до легкой золотистой корочки",
        "добавьте чеснок, сливки, соль и перец",
        "тушите на слабом огне 10–15 минут до готовности",
    ],
    source_url=RECIPES_URL,
    tip="Подавайте с рисом, картофелем или пастой.",
)


def find_recipe() -> Recipe:
    """Берет один рецепт с сайта edimdoma.ru."""
    try:
        recipe_urls = _collect_recipe_urls()
    except Exception as error:
        logger.warning("Не удалось получить рецепты с сайта: %s. Использую стартовый рецепт", error)
        return FALLBACK_RECIPE

    if not recipe_urls:
        logger.warning("Не удалось найти ссылки на рецепты, использую стартовый рецепт")
        return FALLBACK_RECIPE

    random.shuffle(recipe_urls)

    for recipe_url in recipe_urls[:10]:
        try:
            recipe = _parse_recipe_page(recipe_url)
        except Exception:
            logger.exception("Ошибка при разборе рецепта: %s", recipe_url)
            continue

        if recipe.ingredients and recipe.steps:
            return recipe

    logger.warning("Не удалось получить полный рецепт, использую стартовый рецепт")
    return FALLBACK_RECIPE


def _collect_recipe_urls() -> list[str]:
    html = _get_text(RECIPES_URL)
    urls: set[str] = set()

    for href in re.findall(r'href=["\']([^"\']+)["\']', html):
        if re.search(r"/retsepty/\d+", href):
            urls.add(urljoin(BASE_URL, href.split("?")[0]))

    return list(urls)


def _parse_recipe_page(url: str) -> Recipe:
    html = _get_text(url)

    json_recipe = _extract_json_ld_recipe(html)
    if json_recipe:
        return Recipe(
            title=_clean_text(json_recipe.get("name", "")),
            ingredients=_normalize_items(json_recipe.get("recipeIngredient", []), 8),
            steps=_extract_steps_from_json(json_recipe.get("recipeInstructions", [])),
            source_url=url,
            tip="Подавайте блюдо свежим, дополнив зеленью или любимым гарниром.",
        )

    return Recipe(
        title=_extract_title(html),
        ingredients=_extract_meta_items(html, "recipeIngredient", 8),
        steps=_extract_meta_items(html, "recipeInstructions", 6),
        source_url=url,
        tip="Подавайте блюдо свежим, дополнив зеленью или любимым гарниром.",
    )


def _extract_json_ld_recipe(html: str) -> dict[str, Any] | None:
    scripts = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    for raw in scripts:
        try:
            data = json.loads(unescape(raw.strip()))
        except json.JSONDecodeError:
            continue

        recipe = _find_recipe_node(data)
        if recipe:
            return recipe

    return None


def _find_recipe_node(data: Any) -> dict[str, Any] | None:
    if isinstance(data, list):
        for item in data:
            found = _find_recipe_node(item)
            if found:
                return found

    if isinstance(data, dict):
        node_type = data.get("@type")
        if node_type == "Recipe" or (isinstance(node_type, list) and "Recipe" in node_type):
            return data

        graph = data.get("@graph")
        if graph:
            return _find_recipe_node(graph)

    return None


def _extract_steps_from_json(instructions: Any) -> list[str]:
    steps: list[str] = []

    if isinstance(instructions, str):
        steps.append(instructions)
    elif isinstance(instructions, list):
        for item in instructions:
            if isinstance(item, str):
                steps.append(item)
            elif isinstance(item, dict):
                if isinstance(item.get("itemListElement"), list):
                    steps.extend(_extract_steps_from_json(item["itemListElement"]))
                else:
                    steps.append(item.get("text") or item.get("name") or "")

    return _normalize_items(steps, 6)


def _extract_title(html: str) -> str:
    heading = re.search(r"<h1[^>]*>(.*?)</h1>", html, flags=re.IGNORECASE | re.DOTALL)
    if heading:
        return _clean_text(_strip_tags(heading.group(1)))

    title = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if title:
        return _clean_text(_strip_tags(title.group(1)).split("|")[0])

    return "Вкусный рецепт"


def _extract_meta_items(html: str, itemprop: str, limit: int) -> list[str]:
    pattern = rf'<[^>]+itemprop=["\']{re.escape(itemprop)}["\'][^>]*>(.*?)</[^>]+>'
    items = [_strip_tags(item) for item in re.findall(pattern, html, re.IGNORECASE | re.DOTALL)]
    return _normalize_items(items, limit)


def _normalize_items(items: Any, limit: int) -> list[str]:
    if isinstance(items, str) or isinstance(items, dict):
        items = [items]

    normalized: list[str] = []
    for item in _flatten_items(items or []):
        text = _clean_text(_item_to_text(item))
        if len(text) < 3:
            continue
        if len(text) > 180:
            text = text[:177].rsplit(" ", 1)[0] + "..."
        if text not in normalized:
            normalized.append(text)

    return normalized[:limit]


def _flatten_items(items: Any) -> list[Any]:
    flattened: list[Any] = []

    if isinstance(items, list):
        for item in items:
            flattened.extend(_flatten_items(item))
        return flattened

    return [items]


def _item_to_text(item: Any) -> str:
    if isinstance(item, dict):
        name = item.get("name") or item.get("text") or ""
        value = _format_amount(item.get("value") or item.get("amount") or "")
        unit = item.get("unitText") or item.get("unitCode") or item.get("unit") or ""

        parts = [_clean_text(str(part)) for part in (value, unit) if str(part).strip()]
        amount = " ".join(parts)
        if name and amount:
            return f"{name} — {amount}"
        return str(name or amount)

    return str(item)


def _format_amount(value: Any) -> str:
    text = str(value).strip()
    if not text:
        return ""

    try:
        number = float(text.replace(",", "."))
    except ValueError:
        return text

    if number.is_integer():
        return str(int(number))

    return str(number).rstrip("0").rstrip(".").replace(".", ",")


def _clean_text(value: str) -> str:
    text = unescape(value)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" \n\t\r-—")


def _strip_tags(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", value)


def _get_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=20) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")
