from parser import Recipe


def format_recipe_post(recipe: Recipe) -> str:
    ingredients = "\n".join(f"— {_polish_line(item)}" for item in recipe.ingredients[:8])
    steps = "\n".join(
        f"{index}. {_polish_line(step)}"
        for index, step in enumerate(recipe.steps[:6], start=1)
    )
    tip = recipe.tip or "Готовьте с хорошим настроением и подавайте сразу после приготовления."

    post = f"""🍽 Рецепт дня: {recipe.title}

🧾 Ингредиенты:
{ingredients}

👨‍🍳 Как приготовить:
{steps}

💡 Совет:
{tip}

Источник: {recipe.source_url}"""

    return _limit_post(post)


def _polish_line(text: str) -> str:
    clean = text.strip()
    if not clean:
        return clean

    clean = clean[0].lower() + clean[1:]
    if clean.endswith("."):
        clean = clean[:-1]
    return clean


def _limit_post(text: str, limit: int = 3900) -> str:
    if len(text) <= limit:
        return text

    source_marker = "\n\nИсточник:"
    source = ""
    body = text
    if source_marker in text:
        body, source = text.rsplit(source_marker, 1)
        source = source_marker + source

    body = body[: limit - len(source) - 20].rstrip()
    return f"{body}\n\n...{source}"
