from __future__ import annotations

from html import escape


def render_operator_onboarding(language: str) -> str:
    copy = _COPY["ru"] if language == "ru" else _COPY["en"]
    collapse_label = copy["collapse"]
    expand_label = copy["expand"]
    steps = "".join(
        _render_step(index, item["title"], item["body"])
        for index, item in enumerate(copy["steps"], start=1)
    )
    glossary = "".join(
        _render_glossary_item(item["term"], item["definition"])
        for item in copy["glossary"]
    )
    return (
        '<section class="panel operator-onboarding" data-operator-onboarding>'
        '<div class="panel-head">'
        "<div>"
        f'<span class="badge">{escape(copy["badge"])}</span>'
        f'<h2>{escape(copy["title"])}</h2>'
        f'<p>{escape(copy["subtitle"])}</p>'
        "</div>"
        '<div class="action-row">'
        f'<button class="button" type="button" data-operator-onboarding-collapse '
        f'data-collapse-label="{escape(collapse_label)}" '
        f'data-expand-label="{escape(expand_label)}">{escape(collapse_label)}</button>'
        f'<button class="button ghost" type="button" data-operator-onboarding-dismiss>{escape(copy["dismiss"])}</button>'
        f'<a class="button" href="/workspace/runtime">{escape(copy["prompt_link"])}</a>'
        "</div>"
        "</div>"
        '<div class="operator-onboarding-body" data-operator-onboarding-body>'
        f'<div class="operator-onboarding-grid">{steps}</div>'
        '<div class="operator-glossary" data-operator-glossary>'
        f'<div><strong>{escape(copy["glossary_title"])}</strong><p class="muted">{escape(copy["glossary_note"])}</p></div>'
        f'<div class="operator-glossary-list">{glossary}</div>'
        "</div>"
        "</div>"
        "</section>"
    )


def _render_step(index: int, title: str, body: str) -> str:
    return (
        "<article>"
        f'<span class="operator-step-number">{index}</span>'
        f"<strong>{escape(title)}</strong>"
        f'<p class="muted">{escape(body)}</p>'
        "</article>"
    )


def _render_glossary_item(term: str, definition: str) -> str:
    return (
        '<article class="operator-glossary-item">'
        f"<strong>{escape(term)}</strong>"
        f'<p class="muted">{escape(definition)}</p>'
        "</article>"
    )


_COPY = {
    "en": {
        "badge": "First 5 minutes",
        "title": "How to read the workspace",
        "subtitle": (
            "Start with data trust, then price and horizons, then the daily watchlist, "
            "and only after that the decision pack."
        ),
        "collapse": "Collapse",
        "expand": "Expand",
        "dismiss": "Hide for this browser",
        "prompt_link": "Council prompts",
        "steps": [
            {
                "title": "Check trust first",
                "body": "Trust ribbon and workspace posture show whether prices, freshness, and runtime state are usable.",
            },
            {
                "title": "Read price in context",
                "body": "Use day, week, and month charts for the selected instrument. If the feed is stale or degraded, do not treat the quote as live.",
            },
            {
                "title": "Work the queue",
                "body": "Watchlist keeps roots and signals between cycles. Filter review-due items and mark what you have checked.",
            },
            {
                "title": "Leave a decision trail",
                "body": "Decision pack, horizon comparison, and journal explain why now, what changed, and what would invalidate the idea.",
            },
        ],
        "glossary_title": "Operator glossary",
        "glossary_note": "Short definitions for the terms that matter during a live review.",
        "glossary": [
            {
                "term": "Price",
                "definition": "Only a real traceable quote is shown. Otherwise charts stay hidden or clearly degraded.",
            },
            {
                "term": "Horizons",
                "definition": "Day, week, and month describe price context; H1/H4/D1/W1 describe signal horizons.",
            },
            {
                "term": "Council",
                "definition": "Analyst, skeptic, and arbiter explain reasoning. This is decision support, not an order.",
            },
            {
                "term": "Stale/degraded",
                "definition": "Data is old, partial, or unreliable. Reduce conviction until freshness recovers.",
            },
            {
                "term": "Prompt governance",
                "definition": "Council role prompts are visible, editable, audited, and can be rolled back from runtime.",
            },
        ],
    },
    "ru": {
        "badge": "Первые 5 минут",
        "title": "Как читать workspace",
        "subtitle": (
            "Начните с доверия к данным, затем проверьте цену и горизонты, "
            "после этого разберите watchlist и только потом переходите к decision pack."
        ),
        "collapse": "Свернуть",
        "expand": "Развернуть",
        "dismiss": "Скрыть в этом браузере",
        "prompt_link": "Промпты совета",
        "steps": [
            {
                "title": "Сначала доверие",
                "body": "Trust ribbon и статус workspace показывают, можно ли использовать цены, свежесть данных и текущий runtime.",
            },
            {
                "title": "Цена в контексте",
                "body": "Смотрите дневной, недельный и месячный графики выбранного инструмента. Если поток stale или degraded, не считайте цену живой.",
            },
            {
                "title": "Разберите очередь",
                "body": "Watchlist хранит серии и сигналы между циклами. Фильтруйте review due и отмечайте то, что уже проверено.",
            },
            {
                "title": "Оставьте след решения",
                "body": "Decision pack, сравнение горизонтов и журнал объясняют: почему сейчас, что изменилось и что сломает идею.",
            },
        ],
        "glossary_title": "Глоссарий оператора",
        "glossary_note": "Короткие определения терминов, которые важны во время живого разбора.",
        "glossary": [
            {
                "term": "Цена",
                "definition": "Показывается только реальная трассируемая котировка. Иначе графики скрыты или явно помечены degraded.",
            },
            {
                "term": "Горизонты",
                "definition": "День, неделя и месяц описывают контекст цены; H1/H4/D1/W1 описывают горизонты сигналов.",
            },
            {
                "term": "Совет",
                "definition": "Analyst, skeptic и arbiter объясняют логику. Это поддержка решения, а не торговый приказ.",
            },
            {
                "term": "Stale/degraded",
                "definition": "Данные устарели, неполные или ненадежные. Снижайте доверие, пока свежесть не восстановится.",
            },
            {
                "term": "Prompt governance",
                "definition": "Промпты ролей совета видимы, редактируемы, аудируются и откатываются через runtime.",
            },
        ],
    },
}
