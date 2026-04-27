from __future__ import annotations


PAGE_HINTS = {
    "dashboard": {
        "ru": "Смотрите сверху вниз: сначала KPI и пульт серии, затем активные сигналы, оценку и здоровье платформы.",
        "en": "Read top to bottom: start with the KPIs and root control room, then move to active signals, evaluation, and platform health.",
    },
    "workspace": {
        "ru": "Начните с сигнала в фокусе и ленты серий, затем проверьте пакет решения, календарь доставок и журнал.",
        "en": "Start with the focus signal and root lane, then review the decision pack, delivery calendar, and journal.",
    },
    "journal": {
        "ru": "Сначала используйте фильтры, затем смотрите ленту журнала и переходите в нужный сигнал из карточки записи.",
        "en": "Use the filters first, then scan the journal tape and jump into the relevant signal from an entry card.",
    },
    "delivery-history": {
        "ru": "Смотрите фильтры и группировку сверху, а ниже проверяйте последние события доставки и их статусы.",
        "en": "Start with the filters and grouped summary, then review the latest delivery events and their statuses below.",
    },
    "preferences": {
        "ru": "Проверьте настройки подписки и Telegram, затем календарь доставок и историю действий ниже на странице.",
        "en": "Review subscription and Telegram settings first, then check the delivery calendar and activity lower on the page.",
    },
    "signal": {
        "ru": "Смотрите hero-блок сигнала, потом анатомию решения, хронологию и Telegram-сводку справа.",
        "en": "Read the signal hero first, then the decision anatomy, timeline, and Telegram brief on the side.",
    },
    "council": {
        "ru": "\u0418\u0434\u0438\u0442\u0435 \u0441\u043b\u0435\u0432\u0430 \u043d\u0430\u043f\u0440\u0430\u0432\u043e: \u0441\u043d\u0430\u0447\u0430\u043b\u0430 \u0432\u0432\u043e\u0434\u043d\u044b\u0435 \u0434\u0430\u043d\u043d\u044b\u0435 \u0438 \u0440\u043e\u043b\u0438 \u0441\u043e\u0432\u0435\u0442\u0430, \u043f\u043e\u0442\u043e\u043c \u0441\u043a\u0435\u043f\u0442\u0438\u043a \u0438 \u0430\u0440\u0431\u0438\u0442\u0440, \u0430 \u0432 \u043a\u043e\u043d\u0446\u0435 \u0438\u0442\u043e\u0433\u043e\u0432\u044b\u0435 score \u0438 \u0442\u0435\u043a\u0443\u0449\u0438\u0439 runtime.",
        "en": "Read left to right: start with the inputs and council roles, then the skeptic and arbiter, and finish with the final scores and current runtime.",
    },
    "runtime": {
        "ru": "Сначала проверьте маршрутизацию ролей и SLA по актуальности, затем просмотрите журнал изменений runtime и последние технические решения.",
        "en": "Start with role routing and freshness SLAs, then review the runtime audit trail and the latest technical decisions.",
    },
    "tooltip_shift_intro": (
        "Ð›Ð¸Ð´ÐµÑ€ ÑÐ¼ÐµÐ½Ð¸Ð»ÑÑ Ð¿Ð¾ÑÐ»Ðµ Ð¿ÐµÑ€ÐµÐºÐ»ÑŽÑ‡ÐµÐ½Ð¸Ñ Ñ‚Ð°Ð¹Ð¼Ñ„Ñ€ÐµÐ¹Ð¼Ð°."
    ),
    "tooltip_shift_stable": (
        "ÐŸÐ¾ÑÐ»Ðµ Ð¿ÐµÑ€ÐµÐºÐ»ÑŽÑ‡ÐµÐ½Ð¸Ñ Ñ‚Ð°Ð¹Ð¼Ñ„Ñ€ÐµÐ¹Ð¼Ð° Ð»Ð¸Ð´ÐµÑ€ Ð¾ÑÑ‚Ð°Ð»ÑÑ Ñ‚ÐµÐ¼ Ð¶Ðµ."
    ),
    "tooltip_shift_was": "Ð‘Ñ‹Ð»",
    "tooltip_shift_now": "Ð¡ÐµÐ¹Ñ‡Ð°Ñ",
    "tooltip_shift_frames": "Ð¢Ð°Ð¹Ð¼Ñ„Ñ€ÐµÐ¹Ð¼Ñ‹",
    "tooltip_shift_spread": "Ð Ð°Ð·Ñ€Ñ‹Ð² A-B",
}


def page_hint(page_key: str, language: str) -> str:
    page_hints = PAGE_HINTS.get(page_key, PAGE_HINTS["workspace"])
    return page_hints["ru"] if language == "ru" else page_hints["en"]
