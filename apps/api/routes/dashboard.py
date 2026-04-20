from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime
from html import escape
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse

from libs.bootstrap.container import get_app_container
from libs.dashboard.contracts import (
    DashboardQualityPair,
    DashboardSnapshot,
    DecisionTimelineItem,
    DeliveryHistoryWorkspaceSnapshot,
    HorizonComparisonSnapshot,
    InstrumentMarketSnapshot,
    JournalWorkspaceSnapshot,
    RuntimeControlSnapshot,
    RuntimeFreshnessPolicyUpdate,
    RuntimeModelRouteUpdate,
    SignalChangeSummary,
    WatchlistEntry,
    WatchlistEntryCreate,
    WorkspaceActionItem,
    WorkspaceSignalSnapshot,
    WorkspaceSnapshot,
)
from libs.domain.contracts import JournalEntryKind, SignalStatus, SignalWorkflowState
from libs.notifications.contracts import TelegramNotificationSendRequest, TelegramNotificationSendResult
from libs.preferences.contracts import (
    NotificationDeliveryActivityAction,
    NotificationDeliveryActivityExportFormat,
    NotificationDeliveryActivityFilters,
    NotificationDeliveryActivityGroup,
    NotificationDeliveryActivityItem,
    NotificationDeliveryActivityPagination,
    NotificationDeliveryWindow,
    NotificationEventKind,
    NotificationDeliverySkipRequest,
    NotificationPreferenceUpdate,
    NotificationPreferenceWorkspaceSnapshot,
)
from libs.runtime.feature_flags import is_feature_enabled

router = APIRouter(tags=["dashboard"])

LANGUAGE_COOKIE = "imoex_lang"
SUPPORTED_LANGUAGES = {"ru", "en"}
MOSCOW_TIMEZONE = ZoneInfo("Europe/Moscow")


def _ensure_dashboard_enabled() -> None:
    if not is_feature_enabled("dashboard_ui"):
        raise HTTPException(status_code=404, detail="Dashboard feature is disabled.")


def _resolve_language(request: Request) -> str:
    candidate = (
        request.query_params.get("lang")
        or request.cookies.get(LANGUAGE_COOKIE)
        or "ru"
    )
    candidate = candidate.lower().strip()
    return candidate if candidate in SUPPORTED_LANGUAGES else "ru"


def _page_hint(page_key: str, language: str) -> str:
    hints = {
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
    }
    page_hints = hints.get(page_key, hints["workspace"])
    return page_hints["ru"] if language == "ru" else page_hints["en"]


def _localize_html(html: str, language: str) -> str:
    html = html.replace("Â·", "·")
    if language != "ru":
        return html
    replacements = (
        ("<title>IMOEX Signal Dashboard</title>", "<title>Панель сигналов IMOEX</title>"),
        ("<title>IMOEX Workspace</title>", "<title>Рабочее пространство IMOEX</title>"),
        ("<title>Journal Workspace</title>", "<title>Журнал сигналов</title>"),
        ("<title>Delivery History</title>", "<title>История доставок</title>"),
        ("<title>Notification Preferences</title>", "<title>Настройки уведомлений</title>"),
        ("<div class=\"panel-head\"><h2>Root Control Room</h2>", "<div class=\"panel-head\"><h2>Пульт серии</h2>"),
        (">Open deep-dive JSON</a>", ">Открыть JSON deep-dive</a>"),
        ("<h1>Signal room for ", "<h1>Сигнальная панель для "),
        (">Open JSON snapshot</a>", ">Открыть JSON-снимок</a>"),
        ("<h2>Active Signal Spotlight</h2>", "<h2>Ключевые активные сигналы</h2>"),
        (">Open API list</a>", ">Открыть список API</a>"),
        ("<h2>Recent Signal Tape</h2>", "<h2>Лента последних сигналов</h2>"),
        ("<h2>Evaluation</h2>", "<h2>Оценка</h2>"),
        (">Open report</a>", ">Открыть отчёт</a>"),
        ("<h2>Platform Health</h2>", "<h2>Здоровье платформы</h2>"),
        (">Open health JSON</a>", ">Открыть JSON health</a>"),
        ("<h2>Source Quality</h2>", "<h2>Качество источников</h2>"),
        (">Open quality API</a>", ">Открыть API качества</a>"),
        ("<h2>Snapshot Payload</h2>", "<h2>Снимок данных</h2>"),
        ("<h2>Context band</h2>", "<h2>Контекст</h2>"),
        ("<h1>What should I do with ", "<h1>Что делать с "),
        (" right now?</h1>", " прямо сейчас?</h1>"),
        (">Open workspace JSON</a>", ">Открыть JSON рабочего пространства</a>"),
        (">Preferences</a>", ">Настройки</a>"),
        (">Delivery history</a>", ">История доставок</a>"),
        (">Open ops console</a>", ">Открыть ops-консоль</a>"),
        (">Inspect active signals API</a>", ">Открыть API активных сигналов</a>"),
        ("<h2>Focus signal</h2>", "<h2>Сигнал в фокусе</h2>"),
        ("<h2>Root lane</h2>", "<h2>Лента серий</h2>"),
        ("<h2>Signal lane</h2>", "<h2>Лента сигналов</h2>"),
        ("<h2>Decision pack</h2>", "<h2>Пакет решения</h2>"),
        (">Open full signal page</a>", ">Открыть страницу сигнала</a>"),
        (">Open signal JSON</a>", ">Открыть JSON сигнала</a>"),
        ("<h2>Visual pulse</h2>", "<h2>Визуальный пульс</h2>"),
        ("<h2>Quick capture</h2>", "<h2>Быстрая запись</h2>"),
        (">Save journal note</button>", ">Сохранить заметку</button>"),
        ("<h2>Action plan</h2>", "<h2>План действий</h2>"),
        ("<h2>Telegram brief</h2>", "<h2>Сводка Telegram</h2>"),
        ("<h2>Delivery calendar</h2>", "<h2>Календарь доставок</h2>"),
        ("<h2>Delivery activity</h2>", "<h2>Активность доставок</h2>"),
        ("<h2>Evaluation and health</h2>", "<h2>Оценка и здоровье</h2>"),
        ("<h2>Source quality</h2>", "<h2>Качество источников</h2>"),
        ("<h2>Raw snapshot</h2>", "<h2>Сырые данные</h2>"),
        (">Telegram JSON</a>", ">JSON Telegram</a>"),
        (">Admin health</a>", ">Health админки</a>"),
        ("<h1>Trading memory for the signal system</h1>", "<h1>Память торговой системы</h1>"),
        (">Open journal JSON</a>", ">Открыть JSON журнала</a>"),
        (">Open workspace</a>", ">Открыть рабочее пространство</a>"),
        ("<h2>Filters</h2>", "<h2>Фильтры</h2>"),
        ("<h2>Decision log</h2>", "<h2>Журнал решений</h2>"),
        ("What the user decided, why the current call exists, and what needs to change next.", "Что пользователь решил, почему текущий вывод выглядит именно так и что должно измениться дальше."),
        ("<h2>Journal tape</h2>", "<h2>Лента журнала</h2>"),
        ("<h2>Current signal lane</h2>", "<h2>Текущая лента сигналов</h2>"),
        ("<h1>Audit trail for Telegram delivery</h1>", "<h1>Журнал доставки в Telegram</h1>"),
        (">Open history JSON</a>", ">Открыть JSON истории</a>"),
        (">Journal</a>", ">Журнал</a>"),
        ("<h2>Root scope</h2>", "<h2>Серия</h2>"),
        ("<h2>Grouped summary</h2>", "<h2>Сводка по группам</h2>"),
        ("<h1>Control what reaches you and when</h1>", "<h1>Управляйте тем, что приходит и когда</h1>"),
        (">Open preferences JSON</a>", ">Открыть JSON настроек</a>"),
        (">Back to workspace</a>", ">Назад в рабочее пространство</a>"),
        (">Open journal</a>", ">Открыть журнал</a>"),
        ("<h2>Subscription settings</h2>", "<h2>Настройки подписки</h2>"),
        (">Save preferences</button>", ">Сохранить настройки</button>"),
        ("<h2>Current summary</h2>", "<h2>Текущая сводка</h2>"),
        (">Open page JSON</a>", ">Открыть JSON страницы</a>"),
        (">Open signal API</a>", ">Открыть API сигнала</a>"),
        (">Open deep-dive</a>", ">Открыть deep-dive</a>"),
        ("<h2>Probability map</h2>", "<h2>Карта вероятностей</h2>"),
        ("<h2>Signal chart</h2>", "<h2>График сигнала</h2>"),
        ("<h2>Horizon pulse</h2>", "<h2>Пульс горизонтов</h2>"),
        ("<h2>Decision anatomy</h2>", "<h2>Анатомия решения</h2>"),
        ("<h2>Resolution</h2>", "<h2>Резюме</h2>"),
        ("<h2>Lifecycle timeline</h2>", "<h2>Хронология</h2>"),
        ("<h2>Related signals</h2>", "<h2>Связанные сигналы</h2>"),
        (">Open signal page</a>", ">Открыть страницу сигнала</a>"),
        (">Open in workspace</a>", ">Открыть в рабочем пространстве</a>"),
        ("No active signals yet.", "Пока нет активных сигналов."),
        ("No recent signals yet.", "Пока нет недавних сигналов."),
        ("No signals available for the selected root yet.", "Для выбранной серии пока нет сигналов."),
        ("No drivers recorded yet.", "Драйверы пока не зафиксированы."),
        ("No objections recorded yet.", "Возражения пока не зафиксированы."),
        ("No invalidation conditions recorded yet.", "Условия инвалидации пока не зафиксированы."),
        ("No journal entries yet. Capture thesis and risk before acting.", "Записей в журнале пока нет. Зафиксируйте тезис и риск перед действием."),
        ("No focus signal yet", "Сигнала в фокусе пока нет"),
        ("Select a root or wait for the next recalculation cycle.", "Выберите серию или дождитесь следующего цикла пересчёта."),
        ("watch mode", "режим наблюдения"),
        ("Telegram preview is not available.", "Предпросмотр Telegram недоступен."),
        ("This browser workspace", "Рабочее пространство в браузере"),
        ("Browser workspace + Telegram brief", "Рабочее пространство в браузере + сводка Telegram"),
        ("Ready to send.", "Готово к отправке."),
        ("Preview available even if delivery is not configured yet.", "Предпросмотр доступен, даже если доставка ещё не настроена."),
        ("Short title", "Короткий заголовок"),
        ("Write what changed, why it matters, and what you will watch next.", "Опишите, что изменилось, почему это важно и что вы будете отслеживать дальше."),
        ("What changed, what risk you see, and what should be watched next.", "Что изменилось, какой риск вы видите и что нужно отслеживать дальше."),
        ("Select a signal first.", "Сначала выберите сигнал."),
        ("Title and note are required.", "Нужны заголовок и заметка."),
        ("Saving...", "Сохраняем..."),
        ("Journal save failed.", "Не удалось сохранить заметку."),
        ("Saved. Reloading...", "Сохранено. Перезагружаем..."),
        ("Delivery action failed.", "Не удалось выполнить действие доставки."),
        ("Updating next run...", "Обновляем следующий запуск..."),
        ("Skip-next action failed.", "Не удалось пропустить следующий запуск."),
        ("Next run updated. Reloading...", "Следующий запуск обновлён. Перезагружаем..."),
        ("Undoing skip...", "Отменяем пропуск..."),
        ("Undo-skip action failed.", "Не удалось отменить пропуск."),
        ("Skip removed. Reloading...", "Пропуск снят. Перезагружаем..."),
        ("Preferences save failed.", "Не удалось сохранить настройки."),
        ("Sending...", "Отправляем..."),
        ("Sending with quiet-hours override...", "Отправляем с игнорированием тихих часов..."),
        ("Pick a signal first to enable quick capture.", "Сначала выберите сигнал, чтобы включить быструю запись."),
        ("Manual send", "Ручная отправка"),
        ("Manual send with quiet-hours override", "Ручная отправка с игнорированием тихих часов"),
        ("Scheduled delivery", "Плановая доставка"),
        ("Skip next", "Пропустить следующий"),
        ("Undo skip", "Отменить пропуск"),
        ("Mute next digest", "Заглушить следующий digest"),
        ("Skip next brief", "Пропустить следующий brief"),
        ("All events", "Все события"),
        ("All roots", "Все серии"),
        ("All statuses", "Все статусы"),
        ("By event", "По событию"),
        ("By root", "По серии"),
        ("By status", "По статусу"),
        ("Event kind", "Тип события"),
        ("Root scope", "Серия"),
        ("<strong>Status</strong>", "<strong>Статус</strong>"),
        (">Previous</a>", ">Назад</a>"),
        (">Next</a>", ">Вперёд</a>"),
        ("Export CSV", "Экспорт CSV"),
        ("Export JSONL", "Экспорт JSONL"),
        ("No chart data available yet.", "Данных для графика пока нет."),
        ("No lifecycle events recorded yet.", "Событий жизненного цикла пока нет."),
        ("No horizon pulse data available yet.", "Данных по пульсу горизонтов пока нет."),
        ("No delivery windows configured yet.", "Окна доставки пока не настроены."),
        ("No delivery actions recorded yet.", "Действий доставки пока не зафиксировано."),
        ("User Workspace | Signals-only", "Рабочее пространство | Только сигналы"),
        ("The primary user experience is this browser workspace at <strong>/workspace</strong>.", "Основной пользовательский экран находится здесь: <strong>/workspace</strong>."),
        ("Telegram gives the portable brief, and <strong>/dashboard</strong> remains the operations console.", "Telegram даёт компактную сводку, а <strong>/dashboard</strong> остаётся операционной консолью."),
        ("<span>Primary surface</span>", "<span>Основной экран</span>"),
        ("<span>Bias</span>", "<span>Направление</span>"),
        ("<span>Confidence</span>", "<span>Уверенность</span>"),
        ("<span>Skeptic</span>", "<span>Скепсис</span>"),
        ("Each card answers whether this root deserves attention now.", "Каждая карточка показывает, заслуживает ли серия внимания прямо сейчас."),
        ("<span>Session</span>", "<span>Сессия</span>"),
        ("Trading day ", "Торговый день "),
        ("<span>Active contract</span>", "<span>Активный контракт</span>"),
        ("<span>Roll risk</span>", "<span>Риск ролла</span>"),
        ("<span>Universe</span>", "<span>Вселенная</span>"),
        ("Pick the signal you want to review in detail.", "Выберите сигнал, который хотите разобрать подробнее."),
        ("The minimum context a human needs before acting.", "Минимальный контекст, нужный человеку перед действием."),
        ("<span>Priority</span>", "<span>Приоритет</span>"),
        ("<span>Freshness</span>", "<span>Актуальность</span>"),
        ("<span>Expiry risk</span>", "<span>Риск экспирации</span>"),
        ("<span>Decision</span>", "<span>Решение</span>"),
        ("<span>Why this is the current call</span>", "<span>Почему сейчас именно такой вывод</span>"),
        ("<span>What should change next</span>", "<span>Что должно измениться дальше</span>"),
        ("<h3>Why now</h3>", "<h3>Почему сейчас</h3>"),
        ("<h3>Pushback</h3>", "<h3>Сдерживающие факторы</h3>"),
        ("<h3>Invalidation</h3>", "<h3>Что отменяет сценарий</h3>"),
        ("Provider comparison stays visible to the user, not only to ops.", "Сравнение провайдеров видно пользователю, а не только ops-команде."),
        ("Useful when you need to inspect the exact payload behind the page.", "Полезно, когда нужно посмотреть точный payload за страницей."),
        ("Delivery History | User Workflow", "История доставок | Пользовательский сценарий"),
        ("This page keeps the full user-facing history of Telegram sends, suppressions, skip controls and scheduled delivery outcomes.", "На этой странице хранится полная пользовательская история Telegram-отправок, подавлений, пропусков и результатов плановой доставки."),
        ("Selected root: ", "Выбранная серия: "),
        ("Telegram enabled: ", "Telegram включён: "),
        ("Telegram configured: ", "Telegram настроен: "),
        ("Total events: ", "Всего событий: "),
        ("Current page: ", "Текущая страница: "),
        ("The same audit trail as the workspace block, but with a longer page size and dedicated navigation.", "Это тот же журнал действий, что и в рабочем пространстве, но с большим размером страницы и отдельной навигацией."),
        ("This is the user-facing journal hub: thesis notes, risk notes, execution notes and post-mortems across the current signal inventory.", "Это пользовательский центр журнала: тезисы, риски, заметки по исполнению и post-mortem по текущему набору сигналов."),
        ("Total entries", "Всего записей"),
        ("Thesis ", "Тезисы "),
        ("Risk ", "Риски "),
        ("Post-mortems ", "Пост-мортемы "),
        ("This page controls the single local user profile: default root, subscribed roots and horizons, event subscriptions, minimum priority and quiet hours for Telegram delivery.", "Эта страница управляет локальным профилем пользователя: серией по умолчанию, подписками на серии и горизонты, событиями, минимальным приоритетом и тихими часами для Telegram-доставки."),
        ("Default root: ", "Серия по умолчанию: "),
        ("Quiet hours: ", "Тихие часы: "),
        ("Quiet-hours delivery: ", "Доставка в тихие часы: "),
        ("Default root", "Серия по умолчанию"),
        ("Suppress delivery during quiet hours", "Подавлять доставку в тихие часы"),
        ("Preview still works, sends are paused unless overridden.", "Предпросмотр работает, а отправка стоит на паузе, если её не переопределить."),
        ("No related signals in the current filter window.", "В текущем окне фильтра связанных сигналов нет."),
        ("No decision cards available for the current filter window.", "В текущем окне фильтра карточек решений пока нет."),
        ("Latest note: none yet | updated ", "Последняя заметка: пока нет | обновлено "),
        ("Latest note: ", "Последняя заметка: "),
        ("No related signals available right now.", "Сейчас связанных сигналов нет."),
        ("Signal is still active; no resolution record yet.", "Сигнал всё ещё активен; записи о разрешении пока нет."),
        ("Resolved at ", "Разрешён в "),
        (" | return ", " | доходность "),
        ("Writes straight into the signal journal.", "Пишет прямо в журнал сигнала."),
        ("Writes directly to the signal journal.", "Пишет напрямую в журнал сигнала."),
        ("Delivery action completed.", "Действие доставки выполнено."),
        ("IMOEX Signals · Dashboard", "Сигналы IMOEX · Дашборд"),
        ("Delivery-layer dashboard over the live signal pipeline: roots, current signal inventory, evaluation status, source quality and operational health in one place.", "Операционный дашборд поверх живого сигнального контура: серии, текущий инвентарь сигналов, оценка, качество источников и здоровье платформы в одном месте."),
        ("Inspect signals API", "Открыть API сигналов"),
        ("Inspect admin health", "Открыть health админки"),
        ("Resolved signals", "Разрешённые сигналы"),
        ("Journal Workspace | User Workflow", "Журнал | Пользовательский сценарий"),
        ("<span>Total</span>", "<span>Всего</span>"),
        ("<span>Thesis</span>", "<span>Тезисы</span>"),
        ("<span>Risk</span>", "<span>Риски</span>"),
        ("<span>Post-mortems</span>", "<span>Пост-мортемы</span>"),
        ("Signal Detail | User Workflow", "Сигнал | Пользовательский сценарий"),
        ("Signal id: ", "Идентификатор сигнала: "),
        ("Live Root", "Текущая серия"),
        ("Active Signals", "Активные сигналы"),
        ("Roll Share", "Доля ролла"),
        ("Resolved", "Разрешено"),
        ("Platform", "Платформа"),
        ("Current dashboard focus root.", "Текущая серия в фокусе дашборда."),
        ("Visible active signals for the selected root.", "Видимые активные сигналы для выбранной серии."),
        ("Visible active сигналов for the selected root.", "Видимые активные сигналы для выбранной серии."),
        ("Current MOEX session classification.", "Текущая классификация сессии MOEX."),
        ("Share migrating into the next contract.", "Доля, переходящая в следующий контракт."),
        ("Signals available for calibration and quality checks.", "Сигналы, доступные для калибровки и проверок качества."),
        ("Operational health snapshot across DB, sources and backups.", "Снимок операционного состояния по БД, источникам и резервным копиям."),
        ("DB status", "Состояние БД"),
        ("Active / resolved", "Активные / разрешённые"),
        ("Backups", "Резервные копии"),
        ("contracts ", "контрактов "),
        ("latest ", "последний "),
        ("mismatch ", "расхождение "),
        ("Universe", "Вселенная"),
        ("Session", "Сессия"),
        ("Trading Day", "Торговый день"),
        ("Rule Set", "Набор правил"),
        ("Next Contract", "Следующий контракт"),
        ("Days To Last Trade", "Дней до последней торговли"),
        ("Next Share", "Доля следующего"),
        ("<span>Up</span>", "<span>Рост</span>"),
        ("<span>Down</span>", "<span>Падение</span>"),
        ("<span>No edge</span>", "<span>Без преимущества</span>"),
        ("<h3>Drivers</h3>", "<h3>Драйверы</h3>"),
        ("<h3>Objections</h3>", "<h3>Возражения</h3>"),
        ("<h3>Data sources</h3>", "<h3>Источники данных</h3>"),
        ("Same root across horizons, using point-in-time features and active signal probabilities.", "Одна и та же серия по всем горизонтам с использованием point-in-time признаков и вероятностей активных сигналов."),
        ("Signal room for ", "Сигнальная панель для "),
        ("suppressed during quiet hours", "подавляется в тихие часы"),
        ("allowed during quiet hours", "разрешена в тихие часы"),
        ("Send now", "Отправить сейчас"),
        ("Send now ignoring quiet hours", "Отправить сейчас, игнорируя тихие часы"),
        ("User Workflow", "Пользовательский сценарий"),
        ("signals ", "сигналов "),
        ("no signal ids", "без id сигналов"),
        ("provider message ", "сообщение провайдера "),
        ("not scheduled", "не запланировано"),
        ("never", "никогда"),
        ("profile default", "профиль по умолчанию"),
    )
    for source, target in replacements:
        html = html.replace(source, target)
    html = html.replace("<span>Status</span>", "<span>\u0421\u0442\u0430\u0442\u0443\u0441</span>")
    html = html.replace("<strong>Confidence</strong>", "<strong>\u0423\u0432\u0435\u0440\u0435\u043d\u043d\u043e\u0441\u0442\u044c</strong>")
    html = html.replace("<span>Contract state</span>", "<span>\u0421\u043e\u0441\u0442\u043e\u044f\u043d\u0438\u0435 \u043a\u043e\u043d\u0442\u0440\u0430\u043a\u0442\u0430</span>")
    html = html.replace("<span>Evaluation</span>", "<span>\u041e\u0446\u0435\u043d\u043a\u0430</span>")
    html = html.replace("Subscribed roots", "\u041f\u043e\u0434\u043f\u0438\u0441\u0430\u043d\u043d\u044b\u0435 \u0441\u0435\u0440\u0438\u0438")
    html = html.replace("Subscribed horizons", "\u041f\u043e\u0434\u043f\u0438\u0441\u0430\u043d\u043d\u044b\u0435 \u0433\u043e\u0440\u0438\u0437\u043e\u043d\u0442\u044b")
    html = html.replace("Telegram events", "\u0421\u043e\u0431\u044b\u0442\u0438\u044f Telegram")
    html = html.replace("Digest limit", "\u041b\u0438\u043c\u0438\u0442 \u0434\u0430\u0439\u0434\u0436\u0435\u0441\u0442\u0430")
    html = html.replace("Min priority", "\u041c\u0438\u043d. \u043f\u0440\u0438\u043e\u0440\u0438\u0442\u0435\u0442")
    html = html.replace("Quiet hours start", "\u041d\u0430\u0447\u0430\u043b\u043e \u0442\u0438\u0445\u0438\u0445 \u0447\u0430\u0441\u043e\u0432")
    html = html.replace("Quiet hours end", "\u041a\u043e\u043d\u0435\u0446 \u0442\u0438\u0445\u0438\u0445 \u0447\u0430\u0441\u043e\u0432")
    html = html.replace("Quiet-hours policy", "\u041f\u043e\u043b\u0438\u0442\u0438\u043a\u0430 \u0442\u0438\u0445\u0438\u0445 \u0447\u0430\u0441\u043e\u0432")
    html = html.replace("suppress sends", "\u043f\u043e\u0434\u0430\u0432\u043b\u044f\u0442\u044c \u043e\u0442\u043f\u0440\u0430\u0432\u043a\u0443")
    html = html.replace("allow sends", "\u0440\u0430\u0437\u0440\u0435\u0448\u0430\u0442\u044c \u043e\u0442\u043f\u0440\u0430\u0432\u043a\u0443")
    html = html.replace("No journal entries yet.", "\u0417\u0430\u043f\u0438\u0441\u0435\u0439 \u0432 \u0436\u0443\u0440\u043d\u0430\u043b\u0435 \u043f\u043e\u043a\u0430 \u043d\u0435\u0442.")
    html = html.replace("| roll ", " | \u0440\u043e\u043b\u043b ")
    html = re.sub(
        r">Next ([^<]+)</p>",
        lambda match: ">" + "\u0421\u043b\u0435\u0434\u0443\u044e\u0449\u0438\u0439 " + match.group(1) + "</p>",
        html,
    )
    html = html.replace("<h2>Models and data feeds</h2>", "<h2>Модели и источники данных</h2>")
    html = html.replace(
        "Visible role routing and the live price-source ownership for this root.",
        "Здесь видно, какие роли закреплены за моделями и чей price API сейчас даёт данные по этой серии.",
    )
    html = html.replace("<label>LLM runtime</label>", "<label>LLM-стек</label>")
    html = html.replace("<label>LLM owner</label>", "<label>Владелец LLM</label>")
    html = html.replace("<label>Data mode</label>", "<label>Режим данных</label>")
    html = html.replace("<label>Latest market data</label>", "<label>Последние рыночные данные</label>")
    html = html.replace("<h3>Role routing</h3>", "<h3>Ролевая маршрутизация</h3>")
    html = html.replace("<h3>Market-data feeds</h3>", "<h3>Потоки рыночных данных</h3>")
    html = html.replace("No model roles configured yet.", "Роли моделей пока не настроены.")
    html = html.replace(
        "No market-data feeds are attached to this root yet.",
        "Для этой серии пока не привязаны рыночные источники.",
    )
    html = html.replace("No detail available.", "Детали пока не указаны.")
    html = html.replace(
        "Temporary fixed mapping until configurable role routing is added.",
        "Временная жёсткая привязка до появления управляемой маршрутизации ролей.",
    )
    html = html.replace("Trend / volatility analyst", "Аналитик тренда и волатильности")
    html = html.replace("Flow / liquidity analyst", "Аналитик потока и ликвидности")
    html = html.replace("OI / roll analyst", "Аналитик OI и ролла")
    html = html.replace("Macro-event analyst", "Аналитик макро-событий")
    html = html.replace("Broker market-data API", "Брокерский API рыночных данных")
    html = html.replace("Exchange reference API", "Биржевой справочный API")
    html = html.replace("Secondary market-data API", "Вторичный API рыночных данных")
    html = html.replace("Shadow market-data API", "Теневой API рыночных данных")
    html = html.replace("Latest market data", "Последние рыночные данные")
    html = html.replace("Data mode", "Режим данных")
    html = html.replace("Live", "Живой поток")
    html = html.replace("Snapshot", "Снимок")
    html = html.replace("Degraded feed", "Деградировавший источник")
    html = html.replace(
        "At least one fresh market-data API is healthy for this root.",
        "Для этой серии есть хотя бы один свежий и здоровый рыночный API.",
    )
    html = html.replace(
        "Healthy reference data is available, but live broker feeds are not fully active.",
        "Справочные данные доступны, но live-брокерские источники работают не полностью.",
    )
    html = html.replace(
        "Primary price source is degraded or unavailable.",
        "Основной источник цен деградировал или недоступен.",
    )
    html = html.replace(
        "Reference truth for calendar, contract metadata and baseline bars.",
        "Базовый биржевой источник для календаря, метаданных контрактов и эталонных баров.",
    )
    html = html.replace(
        "Finam adapter is available but `FINAM_SECRET_TOKEN` or `FINAM_JWT_TOKEN` is not configured.",
        "Адаптер Finam доступен, но `FINAM_SECRET_TOKEN` или `FINAM_JWT_TOKEN` не настроен.",
    )
    html = html.replace("Skeptic", "Скептик")
    html = html.replace("Arbiter", "Арбитр")
    html = html.replace("Broker market-data API", "Брокерский API рыночных данных")
    html = html.replace("Exchange reference API", "Биржевой справочный API")
    html = html.replace("Secondary market-data API", "Вторичный API рыночных данных")
    html = html.replace("Shadow market-data API", "Теневой API рыночных данных")
    html = html.replace("Macro-event calendar", "Календарь макро-событий")
    html = html.replace(" &middot; last ", " &middot; обновлено ")
    html = html.replace("Navigation", "Навигация")
    html = html.replace("Move around the workspace", "Переходы")
    html = html.replace(
        "Jump between the main pages for the current root and signal.",
        "Переходите между основными страницами для текущей серии и сигнала.",
    )
    html = html.replace("Current root", "Текущая серия")
    html = html.replace("Switch instrument", "Инструмент")
    html = html.replace("Current instrument", "Текущий инструмент")
    html = html.replace("Workspace", "Рабочее пространство")
    html = html.replace("Operations", "Операционный дашборд")
    html = html.replace("Journal", "Журнал")
    html = html.replace("Preferences", "Настройки")
    html = html.replace("Delivery history", "История доставок")
    html = html.replace("Signal detail", "Детали сигнала")
    html = html.replace("Days To Expiry", "Дней до экспирации")
    html = html.replace("Until contract expiry", "До экспирации контракта")
    html = html.replace("Price Source", "Источник цены")
    html = html.replace("Updated ", "Обновлено ")
    html = html.replace("No market-data feed is attached yet.", "Источник рыночных данных пока не подключен.")
    html = html.replace("<span>Workflow</span>", "<span>\u0421\u0442\u0430\u0442\u0443\u0441 \u0440\u0430\u0431\u043e\u0442\u044b</span>")
    html = html.replace("watching", "\u043d\u0430\u0431\u043b\u044e\u0434\u0430\u044e")
    html = html.replace("reviewing", "\u043f\u0440\u043e\u0432\u0435\u0440\u044f\u044e")
    html = html.replace("ignored", "\u0438\u0433\u043d\u043e\u0440\u0438\u0440\u0443\u044e")
    html = html.replace("escalated", "\u044d\u0441\u043a\u0430\u043b\u0438\u0440\u0443\u044e")
    html = html.replace("Pick a signal first", "\u0421\u043d\u0430\u0447\u0430\u043b\u0430 \u0432\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0441\u0438\u0433\u043d\u0430\u043b")
    html = html.replace(
        "Select a signal to set how you want to handle it.",
        "\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0441\u0438\u0433\u043d\u0430\u043b, \u0447\u0442\u043e\u0431\u044b \u0437\u0430\u0434\u0430\u0442\u044c, \u043a\u0430\u043a \u0432\u044b \u0445\u043e\u0442\u0438\u0442\u0435 \u0441 \u043d\u0438\u043c \u0440\u0430\u0431\u043e\u0442\u0430\u0442\u044c.",
    )
    html = html.replace(
        "Keep this setup in view and wait for stronger confirmation.",
        "\u0414\u0435\u0440\u0436\u0438\u0442\u0435 \u044d\u0442\u043e\u0442 \u0441\u0435\u0442\u0430\u043f \u0432 \u043f\u043e\u043b\u0435 \u0437\u0440\u0435\u043d\u0438\u044f \u0438 \u0436\u0434\u0438\u0442\u0435 \u0431\u043e\u043b\u0435\u0435 \u0441\u0438\u043b\u044c\u043d\u043e\u0433\u043e \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0438\u044f.",
    )
    html = html.replace(
        "Manually verify the setup before taking action.",
        "\u041f\u0440\u043e\u0432\u0435\u0440\u044c\u0442\u0435 \u0441\u0435\u0442\u0430\u043f \u0432\u0440\u0443\u0447\u043d\u0443\u044e \u043f\u0435\u0440\u0435\u0434 \u0434\u0435\u0439\u0441\u0442\u0432\u0438\u0435\u043c.",
    )
    html = html.replace(
        "This signal is deprioritized until the context changes.",
        "\u042d\u0442\u043e\u0442 \u0441\u0438\u0433\u043d\u0430\u043b \u0441\u043d\u044f\u0442 \u0441 \u043f\u0440\u0438\u043e\u0440\u0438\u0442\u0435\u0442\u0430, \u043f\u043e\u043a\u0430 \u043a\u043e\u043d\u0442\u0435\u043a\u0441\u0442 \u043d\u0435 \u0438\u0437\u043c\u0435\u043d\u0438\u0442\u0441\u044f.",
    )
    html = html.replace(
        "This signal needs a higher-attention review right now.",
        "\u042d\u0442\u043e\u0442 \u0441\u0438\u0433\u043d\u0430\u043b \u043f\u0440\u043e\u0441\u0438\u0442 \u043f\u043e\u0432\u044b\u0448\u0435\u043d\u043d\u043e\u0433\u043e \u0432\u043d\u0438\u043c\u0430\u043d\u0438\u044f \u043f\u0440\u044f\u043c\u043e \u0441\u0435\u0439\u0447\u0430\u0441.",
    )
    html = html.replace("Updating workflow...", "\u041e\u0431\u043d\u043e\u0432\u043b\u044f\u0435\u043c \u0441\u0442\u0430\u0442\u0443\u0441...")
    html = html.replace("Workflow update failed.", "\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043e\u0431\u043d\u043e\u0432\u0438\u0442\u044c \u0441\u0442\u0430\u0442\u0443\u0441.")
    html = html.replace(
        "Workflow updated. Refreshing...",
        "\u0421\u0442\u0430\u0442\u0443\u0441 \u043e\u0431\u043d\u043e\u0432\u043b\u0451\u043d. \u041e\u0431\u043d\u043e\u0432\u043b\u044f\u0435\u043c \u0441\u0442\u0440\u0430\u043d\u0438\u0446\u0443...",
    )
    html = html.replace("workflow ", "\u0441\u0442\u0430\u0442\u0443\u0441 ")
    regex_replacements = (
        (r">confidence ", ">уверенность "),
        (r">skeptic ", ">скепсис "),
        (r">priority ", ">приоритет "),
        (r">signal probability ", ">вероятность сигнала "),
        (r">return score ", ">оценка доходности "),
        (r">volatility ", ">волатильность "),
        (r"\| trend ", "| тренд "),
        (r">author ", ">автор "),
        (r"\| created ", "| создано "),
        (r">root ", ">серия "),
        (r"\| next ", "| след. запуск "),
        (r">subscription on", ">подписка включена"),
        (r">subscription off", ">подписка выключена"),
        (r">skip next pending", ">следующий пропуск: да"),
        (r">skip next off", ">следующий пропуск: нет"),
        (r">last run ", ">последний запуск "),
        (r">Page ([0-9]+) of ([0-9]+) \| ([0-9]+) total events \| page size ([0-9]+)</p>", r">Страница \1 из \2 | всего событий \3 | размер страницы \4</p>"),
        (r"Analyst consensus remains net bullish; horizon=", "Консенсус аналитиков остаётся бычьим; горизонт="),
        (r"Analyst consensus remains net bearish; horizon=", "Консенсус аналитиков остаётся медвежьим; горизонт="),
        (r"Analyst consensus remains net neutral; horizon=", "Консенсус аналитиков остаётся нейтральным; горизонт="),
        (r"Delivery-layer dashboard over the live signal pipeline:\s*roots, current signal inventory,\s*evaluation status, source quality and operational health in one place\.", "Операционный дашборд поверх живого сигнального контура: серии, текущий инвентарь сигналов, оценка, качество источников и здоровье платформы в одном месте."),
        (r"No active setup yet; keep root on watch\.", "Активного сетапа пока нет; держите серию под наблюдением."),
        (r"Consensus is mixed and arbiter keeps the setup near no-edge; horizon=", "Консенсус смешанный, и арбитр удерживает сценарий рядом с no-edge; горизонт="),
        (r"roll_state=", "состояние_ролла="),
        (r"состояние_ролла=stable", "состояние_ролла=стабильно"),
        (r"skeptic=pass", "скептик=пройдено"),
        (r"skeptic_score=", "оценка_скептика="),
        (r"breakout_state=", "состояние_пробоя="),
        (r"trend_slope=", "наклон_тренда="),
        (r"realized_volatility=", "реализованная_волатильность="),
        (r"liquidity_score=", "оценка_ликвидности="),
        (r"vwap_distance_bps=", "отклонение_vwap_бпс="),
        (r"no material skeptic objections for the current horizon", "существенных возражений скептика для текущего горизонта нет"),
        (r"OI logic currently uses roll proxies until exchange OI feed is connected", "логика OI пока использует прокси ролла, пока не подключён биржевой поток открытого интереса"),
        (r"trend slope flips sign on the next feature refresh", "наклон тренда меняет знак на следующем обновлении признаков"),
        (r"liquidity ranking drops on the next weekly universe refresh", "рейтинг ликвидности снижается на следующем недельном обновлении вселенной"),
        (r"next contract share accelerates above the current roll threshold", "доля следующего контракта ускоряется выше текущего порога ролла"),
        (r"Session is ([^,]+), skeptic verdict is ([^,]+), roll share is ([^.]+)\.", r"Сессия: \1, вердикт скептика: \2, доля ролла: \3."),
        (r"Capture the reason for acting, the main risk, and whether market structure still matches the analyst drivers\.", "Зафиксируйте причину действия, главный риск и то, соответствует ли структура рынка драйверам аналитика."),
        (r"Send the midday digest using the current user delivery preferences\.", "Отправить дневной дайджест с использованием текущих пользовательских настроек доставки."),
        (r"Send the end-of-day resolution brief for resolved signals\.", "Отправить вечернюю сводку по разрешённым сигналам."),
        (r"Send the post-mortem brief after the journal window closes\.", "Отправить пост-мортем сводку после закрытия окна журнала."),
        (r"Send the opening signal alert to the configured Telegram chat\.", "Отправить стартовый alert по сигналу в настроенный чат Telegram."),
        (r"Probability of upward continuation\.", "Вероятность продолжения вверх."),
        (r"Probability of downward continuation\.", "Вероятность продолжения вниз."),
        (r"Final calibrated confidence\.", "Итоговая откалиброванная уверенность."),
        (r"Skeptic approval score\.", "Оценка одобрения скептика."),
        (r"Higher means contract transition risk is more relevant\.", "Чем выше значение, тем важнее риск перехода между контрактами."),
        (r"Higher means expiry proximity matters more\.", "Чем выше значение, тем значимее близость экспирации."),
        (r"no-edge", "без преимущества"),
        (r">bullish ·", ">бычий ·"),
        (r">bearish ·", ">медвежий ·"),
        (r">no_edge<", ">без_преимущества<"),
        (r"· bullish<", "· бычий<"),
        (r"· bearish<", "· медвежий<"),
        (r"· no_edge<", "· без_преимущества<"),
        (r">bullish \|", ">бычий |"),
        (r">bearish \|", ">медвежий |"),
        (r">neutral \|", ">нейтральный |"),
        (r"\| active<", "| активен<"),
        (r"\| resolved<", "| разрешён<"),
        (r"\| invalidated<", "| инвалидирован<"),
        (r"<strong>main</strong>", "<strong>основная</strong>"),
        (r"<strong>selected</strong>", "<strong>выбрана</strong>"),
        (r"<p>degraded</p>", "<p>ухудшено</p>"),
        (r"<p>ok</p>", "<p>ок</p>"),
        (r"<strong>pass</strong>", "<strong>пройдено</strong>"),
        (r"<strong>digest</strong>", "<strong>дайджест</strong>"),
        (r"<strong>resolution</strong>", "<strong>разрешение</strong>"),
        (r"<strong>post_mortem</strong>", "<strong>пост-мортем</strong>"),
        (r"<strong>signal_open</strong>", "<strong>открытие сигнала</strong>"),
        (r">digest \|", ">дайджест |"),
        (r">resolution \|", ">разрешение |"),
        (r">post_mortem \|", ">пост-мортем |"),
        (r">signal_open \|", ">открытие сигнала |"),
    )
    for pattern, target in regex_replacements:
        html = re.sub(pattern, target, html)
    html = html.replace(
        "<label>Reference sync</label>",
        "<label>\u0421\u0438\u043d\u0445\u0440\u043e\u043d\u0438\u0437\u0430\u0446\u0438\u044f \u0441\u043f\u0440\u0430\u0432\u043e\u0447\u043d\u0438\u043a\u0430</label>",
    )
    html = html.replace(
        "<label>Latest reference sync</label>",
        "<label>\u041f\u043e\u0441\u043b\u0435\u0434\u043d\u044f\u044f \u0441\u0438\u043d\u0445\u0440\u043e\u043d\u0438\u0437\u0430\u0446\u0438\u044f \u0441\u043f\u0440\u0430\u0432\u043e\u0447\u043d\u0438\u043a\u0430</label>",
    )
    html = html.replace("Latest reference sync", "\u041f\u043e\u0441\u043b\u0435\u0434\u043d\u044f\u044f \u0441\u0438\u043d\u0445\u0440\u043e\u043d\u0438\u0437\u0430\u0446\u0438\u044f \u0441\u043f\u0440\u0430\u0432\u043e\u0447\u043d\u0438\u043a\u0430")
    html = html.replace("Reference sync", "\u0421\u0438\u043d\u0445\u0440\u043e\u043d\u0438\u0437\u0430\u0446\u0438\u044f \u0441\u043f\u0440\u0430\u0432\u043e\u0447\u043d\u0438\u043a\u0430")
    html = html.replace("Bundled fallback", "\u0412\u0441\u0442\u0440\u043e\u0435\u043d\u043d\u044b\u0439 \u0441\u043f\u0440\u0430\u0432\u043e\u0447\u043d\u0438\u043a")
    html = html.replace("Fresh", "\u0421\u0432\u0435\u0436\u043e")
    html = html.replace("Stale", "\u0423\u0441\u0442\u0430\u0440\u0435\u043b\u043e")
    html = html.replace("Fallback", "\u0420\u0435\u0437\u0435\u0440\u0432")
    html = html.replace(
        "Using bundled contract metadata until MOEX ISS sync succeeds.",
        "\u0418\u0441\u043f\u043e\u043b\u044c\u0437\u0443\u044e\u0442\u0441\u044f \u0432\u0441\u0442\u0440\u043e\u0435\u043d\u043d\u044b\u0435 \u043c\u0435\u0442\u0430\u0434\u0430\u043d\u043d\u044b\u0435 \u043a\u043e\u043d\u0442\u0440\u0430\u043a\u0442\u043e\u0432, \u043f\u043e\u043a\u0430 \u0441\u0438\u043d\u0445\u0440\u043e\u043d\u0438\u0437\u0430\u0446\u0438\u044f \u0441 MOEX ISS \u043d\u0435 \u043f\u0440\u043e\u0448\u043b\u0430 \u0443\u0441\u043f\u0435\u0448\u043d\u043e.",
    )
    html = html.replace(
        "Reference metadata is synced from MOEX ISS.",
        "\u0421\u043f\u0440\u0430\u0432\u043e\u0447\u043d\u0438\u043a \u043a\u043e\u043d\u0442\u0440\u0430\u043a\u0442\u043e\u0432 \u0441\u0438\u043d\u0445\u0440\u043e\u043d\u0438\u0437\u0438\u0440\u043e\u0432\u0430\u043d \u0438\u0437 MOEX ISS.",
    )
    html = html.replace(
        "Last MOEX ISS sync is older than the target interval; using the latest saved snapshot.",
        "\u041f\u043e\u0441\u043b\u0435\u0434\u043d\u044f\u044f \u0441\u0438\u043d\u0445\u0440\u043e\u043d\u0438\u0437\u0430\u0446\u0438\u044f MOEX ISS \u0441\u0442\u0430\u0440\u0448\u0435 \u0446\u0435\u043b\u0435\u0432\u043e\u0433\u043e \u0438\u043d\u0442\u0435\u0440\u0432\u0430\u043b\u0430; \u0438\u0441\u043f\u043e\u043b\u044c\u0437\u0443\u0435\u0442\u0441\u044f \u043f\u043e\u0441\u043b\u0435\u0434\u043d\u0438\u0439 \u0441\u043e\u0445\u0440\u0430\u043d\u0451\u043d\u043d\u044b\u0439 snapshot.",
    )
    html = html.replace("Decision flow", "\u041a\u0430\u043a \u044d\u0442\u043e \u0440\u0430\u0431\u043e\u0442\u0430\u0435\u0442")
    html = html.replace(
        "Temporary fixed mapping until configurable role routing is added.",
        "\u041f\u043e\u043a\u0430 \u0440\u043e\u043b\u044c \u0436\u0451\u0441\u0442\u043a\u043e \u0437\u0430\u043a\u0440\u0435\u043f\u043b\u0435\u043d\u0430 \u0437\u0430 \u044d\u0442\u043e\u0439 \u043c\u043e\u0434\u0435\u043b\u044c\u044e, \u043f\u043e\u043a\u0430 \u043d\u0435 \u043f\u043e\u044f\u0432\u0438\u043b\u0430\u0441\u044c \u0443\u043f\u0440\u0430\u0432\u043b\u044f\u0435\u043c\u0430\u044f \u043c\u0430\u0440\u0448\u0440\u0443\u0442\u0438\u0437\u0430\u0446\u0438\u044f \u0440\u043e\u043b\u0435\u0439.",
    )
    html = html.replace("No detail available.", "\u041f\u043e\u043a\u0430 \u043d\u0435\u0442 \u0434\u043e\u043f\u043e\u043b\u043d\u0438\u0442\u0435\u043b\u044c\u043d\u044b\u0445 \u0434\u0435\u0442\u0430\u043b\u0435\u0439.")
    html = html.replace("No model roles configured yet.", "\u0420\u043e\u043b\u0438 \u043c\u043e\u0434\u0435\u043b\u0435\u0439 \u043f\u043e\u043a\u0430 \u043d\u0435 \u043d\u0430\u0441\u0442\u0440\u043e\u0435\u043d\u044b.")
    html = html.replace(
        "No market-data feeds are attached to this root yet.",
        "\u0414\u043b\u044f \u044d\u0442\u043e\u0439 \u0441\u0435\u0440\u0438\u0438 \u0438\u0441\u0442\u043e\u0447\u043d\u0438\u043a\u0438 \u0440\u044b\u043d\u043e\u0447\u043d\u044b\u0445 \u0434\u0430\u043d\u043d\u044b\u0445 \u043f\u043e\u043a\u0430 \u043d\u0435 \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u044b.",
    )
    return html


def _decorate_html_page(html: str, *, language: str, page_key: str) -> str:
    html = _localize_html(html, language)
    html = html.replace('<html lang="en">', f'<html lang="{language}">', 1)
    utility_style = """
  <style>
    .utility-shell {
      width: min(1320px, calc(100% - 28px));
      margin: 18px auto 0;
    }
    .utility-bar {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 12px 16px;
      border-radius: 18px;
      border: 1px solid rgba(23, 34, 44, 0.12);
      background: rgba(255, 250, 241, 0.82);
      box-shadow: 0 10px 26px rgba(23, 34, 44, 0.08);
      backdrop-filter: blur(12px);
    }
    .utility-controls {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 10px;
    }
    .utility-label {
      font-size: 13px;
      font-weight: 600;
      color: #425057;
    }
    .utility-select,
    .utility-button {
      min-height: 40px;
      border-radius: 12px;
      border: 1px solid rgba(23, 34, 44, 0.12);
      background: rgba(255, 255, 255, 0.8);
      color: #17222c;
      font: inherit;
    }
    .utility-select {
      padding: 0 12px;
    }
    .utility-button {
      padding: 0 14px;
      cursor: pointer;
      font-weight: 600;
    }
    .utility-hint {
      margin-top: 10px;
      padding: 12px 14px;
      border-radius: 16px;
      background: rgba(25, 58, 82, 0.08);
      color: #23323d;
      line-height: 1.5;
      border: 1px solid rgba(25, 58, 82, 0.12);
    }
  </style>
"""
    language_label = "Язык" if language == "ru" else "Language"
    hint_button_label = "Куда смотреть?" if language == "ru" else "Where to look?"
    hint = escape(_page_hint(page_key, language))
    utility_markup = f"""
  <div class="utility-shell">
    <div class="utility-bar">
      <div class="utility-controls">
        <label class="utility-label" for="ui-language-select">{language_label}</label>
        <select class="utility-select" id="ui-language-select" data-language-select>
          <option value="ru">Русский</option>
          <option value="en">English</option>
        </select>
      </div>
      <button class="utility-button" type="button" data-hint-toggle aria-expanded="false">{hint_button_label}</button>
    </div>
    <div class="utility-hint" data-hint-box data-message="{hint}" hidden></div>
  </div>
"""
    utility_script = f"""
  <script>
    (() => {{
      const select = document.querySelector("[data-language-select]");
      const hintButton = document.querySelector("[data-hint-toggle]");
      const hintBox = document.querySelector("[data-hint-box]");
      const swapPage = async (nextUrl) => {{
        try {{
          const response = await fetch(nextUrl, {{
            credentials: "same-origin",
            headers: {{ "X-Requested-With": "imoex-ui" }},
          }});
          if (!response.ok) {{
            window.location.assign(nextUrl);
            return;
          }}
          const htmlText = await response.text();
          history.replaceState({{}}, "", nextUrl);
          document.open();
          document.write(htmlText);
          document.close();
        }} catch {{
          window.location.assign(nextUrl);
        }}
      }};
      window.__imoexSwapPage = swapPage;
      window.__imoexRefreshPage = async (nextUrl) => {{
        await swapPage(nextUrl || window.location.href);
      }};
      document.addEventListener("click", async (event) => {{
        const link = event.target.closest("a[data-swap-link]");
        if (!link || event.defaultPrevented || event.button !== 0) {{
          return;
        }}
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || link.target) {{
          return;
        }}
        event.preventDefault();
        await swapPage(link.href);
      }});
      if (select) {{
        select.value = "{language}";
        select.addEventListener("change", async () => {{
          document.cookie = "{LANGUAGE_COOKIE}=" + encodeURIComponent(select.value) + "; path=/; max-age=31536000; SameSite=Lax";
          const nextUrl = new URL(window.location.href);
          nextUrl.searchParams.set("lang", select.value);
          await swapPage(nextUrl.toString());
        }});
      }}
      const rootSwitch = document.querySelector("[data-root-switch]");
      if (rootSwitch) {{
        rootSwitch.addEventListener("change", async () => {{
          const nextRoot = rootSwitch.value;
          if (!nextRoot) {{
            return;
          }}
          const nextUrl = new URL(window.location.href);
          const pageKey = rootSwitch.dataset.pageKey || "";
          const fallbackPath = rootSwitch.dataset.fallbackPath || "/workspace";
          nextUrl.searchParams.delete("signal_id");
          if (pageKey === "signal") {{
            nextUrl.pathname = fallbackPath;
            nextUrl.search = "";
          }}
          nextUrl.searchParams.set("root", nextRoot);
          if (pageKey === "delivery-history") {{
            nextUrl.searchParams.set("activity_root_scope", nextRoot);
          }}
          await swapPage(nextUrl.toString());
        }});
      }}
      if (hintButton && hintBox) {{
        hintButton.addEventListener("click", () => {{
          const hidden = hintBox.hasAttribute("hidden");
          if (hidden) {{
            hintBox.textContent = hintBox.dataset.message || "";
            hintBox.removeAttribute("hidden");
            hintButton.setAttribute("aria-expanded", "true");
            return;
          }}
          hintBox.setAttribute("hidden", "hidden");
          hintButton.setAttribute("aria-expanded", "false");
        }});
      }}
    }})();
  </script>
"""
    html = html.replace("</head>", utility_style + "\n</head>", 1)
    html = html.replace("<body>", "<body>\n" + utility_markup, 1)
    html = html.replace("</body>", utility_script + "\n</body>", 1)
    return html


def _build_delivery_windows(*, selected_root: str | None = None) -> list[NotificationDeliveryWindow]:
    container = get_app_container()
    preferences = container.preference_service.get_preferences()
    plan = container.scheduler_service.plan()
    windows: list[NotificationDeliveryWindow] = []
    for job in plan.jobs:
        if job.command != "notify-telegram":
            continue
        event_kind = NotificationEventKind(str(job.payload.get("event_kind") or "digest"))
        root_scope = str(job.payload.get("root") or selected_root or preferences.default_root or "profile default")
        windows.append(
            NotificationDeliveryWindow(
                job_id=job.job_id,
                label=job.description,
                event_kind=event_kind,
                root_scope=root_scope,
                next_run_at=job.next_run_at,
                due_now=job.due_now,
                subscription_enabled=event_kind in preferences.subscribed_event_kinds,
                skip_next_pending=event_kind in preferences.skip_next_event_kinds,
                quiet_hours_policy=(
                    "suppressed during quiet hours"
                    if preferences.suppress_during_quiet_hours
                    else "allowed during quiet hours"
                ),
                last_run_status=job.last_run_status,
                last_run_detail=job.last_run_detail,
            )
        )
    return windows


def _build_delivery_activity_snapshot(
    *,
    selected_root: str | None = None,
    root_scope: str | None = None,
    event_kind: NotificationEventKind | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 8,
    limit: int = 8,
    source_limit: int = 64,
) -> tuple[
    list[NotificationDeliveryActivityItem],
    NotificationDeliveryActivityFilters,
    list[NotificationDeliveryActivityGroup],
    list[NotificationDeliveryActivityGroup],
    list[NotificationDeliveryActivityGroup],
    NotificationDeliveryActivityPagination,
]:
    container = get_app_container()
    normalized_page = max(1, int(page))
    normalized_page_size = max(1, min(int(page_size), 50))
    effective_root_scope = root_scope or selected_root
    total_items = container.repository.count_notification_delivery_events(
        profile_id="default",
        root_code=effective_root_scope,
        event_kind=event_kind.value if event_kind is not None else None,
        status=status,
    )
    total_pages = max(1, (total_items + normalized_page_size - 1) // normalized_page_size)
    normalized_page = min(normalized_page, total_pages)
    offset = (normalized_page - 1) * normalized_page_size
    effective_source_limit = max(source_limit, offset + normalized_page_size, 128)
    rows = container.repository.list_recent_notification_delivery_events(
        profile_id="default",
        root_code=effective_root_scope,
        offset=0,
        limit=effective_source_limit,
    )
    paged_rows = container.repository.list_recent_notification_delivery_events(
        profile_id="default",
        root_code=effective_root_scope,
        event_kind=event_kind.value if event_kind is not None else None,
        status=status,
        offset=offset,
        limit=normalized_page_size,
    )
    all_items: list[NotificationDeliveryActivityItem] = []
    for row in rows:
        try:
            signal_ids = json.loads(row.signal_ids_json)
        except json.JSONDecodeError:
            signal_ids = []
        all_items.append(
            NotificationDeliveryActivityItem(
                activity_id=row.activity_id,
                action=NotificationDeliveryActivityAction(row.action),
                event_kind=NotificationEventKind(row.event_kind),
                delivery_source=row.delivery_source,
                root_scope=row.root_code,
                status=row.status,
                detail=row.detail,
                signal_ids=[str(item) for item in signal_ids if isinstance(item, str)],
                provider_message_id=row.provider_message_id,
                created_at=row.created_at,
            )
        )
    paged_ids = {row.activity_id for row in paged_rows}
    paged_items = [item for item in all_items if item.activity_id in paged_ids]
    paged_items.sort(key=lambda item: item.created_at, reverse=True)
    paged_items = paged_items[:limit]
    return (
        paged_items,
        NotificationDeliveryActivityFilters(
            root_scope=effective_root_scope,
            event_kind=event_kind,
            status=status,
        ),
        _group_delivery_activity(
            all_items,
            value_getter=lambda item: item.event_kind.value,
            label_getter=lambda item: item.event_kind.value,
        ),
        _group_delivery_activity(
            all_items,
            value_getter=lambda item: item.root_scope or "profile default",
            label_getter=lambda item: item.root_scope or "profile default",
        ),
        _group_delivery_activity(
            all_items,
            value_getter=lambda item: item.status,
            label_getter=lambda item: item.status,
        ),
        NotificationDeliveryActivityPagination(
            page=normalized_page,
            page_size=normalized_page_size,
            total_items=total_items,
            total_pages=total_pages,
            has_previous=normalized_page > 1,
            has_next=normalized_page < total_pages,
        ),
    )


def _group_delivery_activity(items, *, value_getter, label_getter) -> list[NotificationDeliveryActivityGroup]:
    grouped: dict[str, NotificationDeliveryActivityGroup] = {}
    for item in items:
        value = str(value_getter(item))
        if value not in grouped:
            grouped[value] = NotificationDeliveryActivityGroup(
                value=value,
                label=str(label_getter(item)),
                count=0,
            )
        grouped[value].count += 1
    return sorted(grouped.values(), key=lambda entry: (-entry.count, entry.label))


def _build_workspace_snapshot(
    root: str | None = None,
    signal_id: str | None = None,
    activity_event_kind: NotificationEventKind | None = None,
    activity_status: str | None = None,
    activity_page: int = 1,
    activity_page_size: int = 8,
) -> WorkspaceSnapshot:
    container = get_app_container()
    resolved_root = root
    if resolved_root is None:
        resolved_root = container.preference_service.resolve_default_root()
    snapshot = container.dashboard_service.build_workspace_snapshot(root=resolved_root, signal_id=signal_id)
    preview = container.telegram_notification_service.preview(root=snapshot.selected_root, limit=3)
    (
        delivery_activity,
        delivery_activity_filters,
        delivery_activity_by_event_kind,
        delivery_activity_by_root_scope,
        delivery_activity_by_status,
        delivery_activity_pagination,
    ) = _build_delivery_activity_snapshot(
        selected_root=snapshot.selected_root,
        event_kind=activity_event_kind,
        status=activity_status,
        page=activity_page,
        page_size=activity_page_size,
    )
    return snapshot.model_copy(
        update={
            "telegram_preview_message": preview.message,
            "telegram_delivery_ready": bool(preview.enabled and preview.configured),
            "delivery_windows": _build_delivery_windows(selected_root=snapshot.selected_root),
            "delivery_activity": delivery_activity,
            "delivery_activity_filters": delivery_activity_filters,
            "delivery_activity_by_event_kind": delivery_activity_by_event_kind,
            "delivery_activity_by_root_scope": delivery_activity_by_root_scope,
            "delivery_activity_by_status": delivery_activity_by_status,
            "delivery_activity_pagination": delivery_activity_pagination,
        },
        deep=True,
    )


def _build_preference_workspace_snapshot(
    *,
    activity_root_scope: str | None = None,
    activity_event_kind: NotificationEventKind | None = None,
    activity_status: str | None = None,
    activity_page: int = 1,
    activity_page_size: int = 12,
) -> NotificationPreferenceWorkspaceSnapshot:
    container = get_app_container()
    snapshot = container.preference_service.build_workspace_snapshot()
    (
        delivery_activity,
        delivery_activity_filters,
        delivery_activity_by_event_kind,
        delivery_activity_by_root_scope,
        delivery_activity_by_status,
        delivery_activity_pagination,
    ) = _build_delivery_activity_snapshot(
        root_scope=activity_root_scope,
        event_kind=activity_event_kind,
        status=activity_status,
        limit=activity_page_size,
        page=activity_page,
        page_size=activity_page_size,
    )
    return snapshot.model_copy(
        update={
            "delivery_windows": _build_delivery_windows(selected_root=snapshot.preferences.default_root),
            "delivery_activity": delivery_activity,
            "delivery_activity_filters": delivery_activity_filters,
            "delivery_activity_by_event_kind": delivery_activity_by_event_kind,
            "delivery_activity_by_root_scope": delivery_activity_by_root_scope,
            "delivery_activity_by_status": delivery_activity_by_status,
            "delivery_activity_pagination": delivery_activity_pagination,
        },
        deep=True,
    )


def _build_signal_workspace_snapshot(signal_id: str) -> WorkspaceSignalSnapshot:
    container = get_app_container()
    snapshot = container.dashboard_service.build_signal_snapshot(signal_id=signal_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail=f"Unknown signal: {signal_id}")
    preview = container.telegram_notification_service.preview(root=snapshot.signal.root, limit=3)
    return snapshot.model_copy(
        update={
            "telegram_preview_message": preview.message,
            "telegram_delivery_ready": bool(preview.enabled and preview.configured),
        },
        deep=True,
    )


def _build_delivery_history_snapshot(
    *,
    selected_root: str | None = None,
    activity_root_scope: str | None = None,
    activity_event_kind: NotificationEventKind | None = None,
    activity_status: str | None = None,
    activity_page: int = 1,
    activity_page_size: int = 24,
) -> DeliveryHistoryWorkspaceSnapshot:
    container = get_app_container()
    roots = container.contract_master_service.list_roots()
    resolved_root = selected_root or container.preference_service.resolve_default_root()
    preference_snapshot = container.preference_service.build_workspace_snapshot()
    (
        delivery_activity,
        delivery_activity_filters,
        delivery_activity_by_event_kind,
        delivery_activity_by_root_scope,
        delivery_activity_by_status,
        delivery_activity_pagination,
    ) = _build_delivery_activity_snapshot(
        selected_root=resolved_root,
        root_scope=activity_root_scope,
        event_kind=activity_event_kind,
        status=activity_status,
        page=activity_page,
        page_size=activity_page_size,
        limit=activity_page_size,
        source_limit=max(256, activity_page_size * 8),
    )
    return DeliveryHistoryWorkspaceSnapshot(
        generated_at=datetime.now(UTC),
        roots=roots,
        selected_root=resolved_root,
        delivery_activity=delivery_activity,
        delivery_activity_filters=delivery_activity_filters,
        delivery_activity_by_event_kind=delivery_activity_by_event_kind,
        delivery_activity_by_root_scope=delivery_activity_by_root_scope,
        delivery_activity_by_status=delivery_activity_by_status,
        delivery_activity_pagination=delivery_activity_pagination,
        telegram_configured=bool(preference_snapshot.telegram_configured),
        telegram_enabled=bool(preference_snapshot.telegram_enabled),
    )


@router.get("/", include_in_schema=False)
async def get_root_redirect() -> RedirectResponse:
    _ensure_dashboard_enabled()
    return RedirectResponse(url="/workspace", status_code=307)


@router.get("/api/v1/workspace", response_model=WorkspaceSnapshot)
async def get_workspace_snapshot(
    root: str | None = None,
    signal_id: str | None = None,
    activity_event_kind: NotificationEventKind | None = None,
    activity_status: str | None = None,
    activity_page: int = 1,
    activity_page_size: int = 8,
) -> WorkspaceSnapshot:
    _ensure_dashboard_enabled()
    return _build_workspace_snapshot(
        root=root,
        signal_id=signal_id,
        activity_event_kind=activity_event_kind,
        activity_status=activity_status,
        activity_page=activity_page,
        activity_page_size=activity_page_size,
    )


@router.get("/api/v1/workspace/compare", response_model=HorizonComparisonSnapshot | None)
async def get_workspace_compare_snapshot(root: str) -> HorizonComparisonSnapshot | None:
    _ensure_dashboard_enabled()
    return get_app_container().dashboard_service.build_horizon_comparison_snapshot(root=root)


@router.get("/api/v1/workspace/market-preview", response_model=InstrumentMarketSnapshot | None)
async def get_workspace_market_preview(root: str) -> InstrumentMarketSnapshot | None:
    _ensure_dashboard_enabled()
    return get_app_container().dashboard_service.build_root_market_snapshot(root=root)


@router.get("/api/v1/workspace/watchlist", response_model=list[WatchlistEntry])
async def get_workspace_watchlist() -> list[WatchlistEntry]:
    _ensure_dashboard_enabled()
    return get_app_container().dashboard_service.build_workspace_snapshot().watchlist


@router.post("/api/v1/workspace/watchlist", response_model=list[WatchlistEntry])
async def add_workspace_watchlist_entry(payload: WatchlistEntryCreate) -> list[WatchlistEntry]:
    _ensure_dashboard_enabled()
    return get_app_container().dashboard_service.add_watchlist_entry(
        root_code=payload.root_code,
        signal_id=payload.signal_id,
        note=payload.note,
    )


@router.delete("/api/v1/workspace/watchlist/{watch_key}", response_model=list[WatchlistEntry])
async def delete_workspace_watchlist_entry(watch_key: str) -> list[WatchlistEntry]:
    _ensure_dashboard_enabled()
    return get_app_container().dashboard_service.remove_watchlist_entry(watch_key)


@router.get("/api/v1/workspace/signals/{signal_id}/diff", response_model=SignalChangeSummary | None)
async def get_workspace_signal_diff(signal_id: str) -> SignalChangeSummary | None:
    _ensure_dashboard_enabled()
    return get_app_container().dashboard_service.build_signal_diff(signal_id=signal_id)


@router.get("/api/v1/workspace/signals/{signal_id}/decision-log", response_model=list[DecisionTimelineItem])
async def get_workspace_signal_decision_log(signal_id: str) -> list[DecisionTimelineItem]:
    _ensure_dashboard_enabled()
    return get_app_container().dashboard_service.build_decision_log(signal_id=signal_id)


@router.get("/api/v1/workspace/preferences", response_model=NotificationPreferenceWorkspaceSnapshot)
async def get_workspace_preferences_snapshot(
    activity_root_scope: str | None = None,
    activity_event_kind: NotificationEventKind | None = None,
    activity_status: str | None = None,
    activity_page: int = 1,
    activity_page_size: int = 12,
) -> NotificationPreferenceWorkspaceSnapshot:
    _ensure_dashboard_enabled()
    return _build_preference_workspace_snapshot(
        activity_root_scope=activity_root_scope,
        activity_event_kind=activity_event_kind,
        activity_status=activity_status,
        activity_page=activity_page,
        activity_page_size=activity_page_size,
    )


@router.post("/api/v1/workspace/preferences", response_model=NotificationPreferenceWorkspaceSnapshot)
async def update_workspace_preferences(payload: NotificationPreferenceUpdate) -> NotificationPreferenceWorkspaceSnapshot:
    _ensure_dashboard_enabled()
    container = get_app_container()
    container.preference_service.update_preferences(payload)
    return _build_preference_workspace_snapshot()


@router.get("/api/v1/runtime/control-panel", response_model=RuntimeControlSnapshot)
async def get_runtime_control_snapshot() -> RuntimeControlSnapshot:
    _ensure_dashboard_enabled()
    return get_app_container().runtime_control_service.get_snapshot()


@router.post("/api/v1/runtime/control-panel/model-route", response_model=RuntimeControlSnapshot)
async def update_runtime_model_route(payload: RuntimeModelRouteUpdate) -> RuntimeControlSnapshot:
    _ensure_dashboard_enabled()
    return get_app_container().runtime_control_service.update_model_route(payload)


@router.post("/api/v1/runtime/control-panel/model-route/reset", response_model=RuntimeControlSnapshot)
async def reset_runtime_model_routes() -> RuntimeControlSnapshot:
    _ensure_dashboard_enabled()
    return get_app_container().runtime_control_service.reset_model_routes()


@router.post("/api/v1/runtime/control-panel/freshness-policy", response_model=RuntimeControlSnapshot)
async def update_runtime_freshness_policy(payload: RuntimeFreshnessPolicyUpdate) -> RuntimeControlSnapshot:
    _ensure_dashboard_enabled()
    return get_app_container().runtime_control_service.update_freshness_policy(payload)


@router.get("/workspace/runtime", response_class=HTMLResponse)
async def get_runtime_control_page(request: Request, root: str | None = None) -> HTMLResponse:
    _ensure_dashboard_enabled()
    language = _resolve_language(request)
    dashboard_snapshot = get_app_container().dashboard_service.build_snapshot(root=root)
    runtime_snapshot = get_app_container().runtime_control_service.get_snapshot()
    return HTMLResponse(
        _decorate_html_page(
            _render_runtime_control_page(runtime_snapshot, dashboard_snapshot=dashboard_snapshot, language=language),
            language=language,
            page_key="runtime",
        )
    )


@router.post("/api/v1/workspace/delivery/send-now", response_model=TelegramNotificationSendResult)
async def send_workspace_delivery_now(payload: TelegramNotificationSendRequest) -> TelegramNotificationSendResult:
    _ensure_dashboard_enabled()
    return get_app_container().telegram_notification_service.send(payload)


@router.post("/api/v1/workspace/delivery/skip-next", response_model=NotificationPreferenceWorkspaceSnapshot)
async def skip_next_workspace_delivery(payload: NotificationDeliverySkipRequest) -> NotificationPreferenceWorkspaceSnapshot:
    _ensure_dashboard_enabled()
    container = get_app_container()
    container.preference_service.mark_skip_next_event(payload.event_kind)
    return _build_preference_workspace_snapshot()


@router.post("/api/v1/workspace/delivery/undo-skip", response_model=NotificationPreferenceWorkspaceSnapshot)
async def undo_skip_workspace_delivery(payload: NotificationDeliverySkipRequest) -> NotificationPreferenceWorkspaceSnapshot:
    _ensure_dashboard_enabled()
    container = get_app_container()
    container.preference_service.clear_skip_next_event(payload.event_kind)
    return _build_preference_workspace_snapshot()


@router.get("/workspace", response_class=HTMLResponse)
async def get_workspace_page(
    request: Request,
    root: str | None = None,
    signal_id: str | None = None,
    activity_event_kind: NotificationEventKind | None = None,
    activity_status: str | None = None,
    activity_page: int = 1,
    activity_page_size: int = 8,
) -> HTMLResponse:
    _ensure_dashboard_enabled()
    language = _resolve_language(request)
    snapshot = _build_workspace_snapshot(
        root=root,
        signal_id=signal_id,
        activity_event_kind=activity_event_kind,
        activity_status=activity_status,
        activity_page=activity_page,
        activity_page_size=activity_page_size,
    )
    return HTMLResponse(
        _decorate_html_page(_render_workspace(snapshot, language=language), language=language, page_key="workspace")
    )


@router.get("/workspace/council", response_class=HTMLResponse)
async def get_workspace_council_page(
    request: Request,
    root: str | None = None,
    signal_id: str | None = None,
) -> HTMLResponse:
    _ensure_dashboard_enabled()
    language = _resolve_language(request)
    snapshot = _build_workspace_snapshot(root=root, signal_id=signal_id)
    return HTMLResponse(_decorate_html_page(_render_council_page(snapshot, language=language), language=language, page_key="council"))


@router.get("/workspace/preferences", response_class=HTMLResponse)
async def get_workspace_preferences_page(
    request: Request,
    root: str | None = None,
    activity_root_scope: str | None = None,
    activity_event_kind: NotificationEventKind | None = None,
    activity_status: str | None = None,
    activity_page: int = 1,
    activity_page_size: int = 12,
) -> HTMLResponse:
    _ensure_dashboard_enabled()
    language = _resolve_language(request)
    snapshot = _build_preference_workspace_snapshot(
        activity_root_scope=activity_root_scope,
        activity_event_kind=activity_event_kind,
        activity_status=activity_status,
        activity_page=activity_page,
        activity_page_size=activity_page_size,
    )
    return HTMLResponse(
        _decorate_html_page(
            _render_workspace_preferences(snapshot, root_context=root),
            language=language,
            page_key="preferences",
        )
    )


@router.get("/api/v1/workspace/delivery-history", response_model=DeliveryHistoryWorkspaceSnapshot)
async def get_workspace_delivery_history_snapshot(
    root: str | None = None,
    activity_root_scope: str | None = None,
    activity_event_kind: NotificationEventKind | None = None,
    activity_status: str | None = None,
    activity_page: int = 1,
    activity_page_size: int = 24,
) -> DeliveryHistoryWorkspaceSnapshot:
    _ensure_dashboard_enabled()
    return _build_delivery_history_snapshot(
        selected_root=root,
        activity_root_scope=activity_root_scope,
        activity_event_kind=activity_event_kind,
        activity_status=activity_status,
        activity_page=activity_page,
        activity_page_size=activity_page_size,
    )


@router.get("/workspace/delivery-history", response_class=HTMLResponse)
async def get_workspace_delivery_history_page(
    request: Request,
    root: str | None = None,
    activity_root_scope: str | None = None,
    activity_event_kind: NotificationEventKind | None = None,
    activity_status: str | None = None,
    activity_page: int = 1,
    activity_page_size: int = 24,
) -> HTMLResponse:
    _ensure_dashboard_enabled()
    language = _resolve_language(request)
    snapshot = _build_delivery_history_snapshot(
        selected_root=root,
        activity_root_scope=activity_root_scope,
        activity_event_kind=activity_event_kind,
        activity_status=activity_status,
        activity_page=activity_page,
        activity_page_size=activity_page_size,
    )
    return HTMLResponse(_decorate_html_page(_render_delivery_history_workspace(snapshot), language=language, page_key="delivery-history"))


@router.get("/api/v1/workspace/delivery/activity/export")
async def export_workspace_delivery_activity(
    root: str | None = None,
    signal_id: str | None = None,
    activity_root_scope: str | None = None,
    activity_event_kind: NotificationEventKind | None = None,
    activity_status: str | None = None,
    export_format: NotificationDeliveryActivityExportFormat = NotificationDeliveryActivityExportFormat.CSV,
) -> PlainTextResponse:
    _ensure_dashboard_enabled()
    snapshot = _build_delivery_activity_snapshot(
        selected_root=root,
        root_scope=activity_root_scope,
        event_kind=activity_event_kind,
        status=activity_status,
        page=1,
        page_size=500,
        limit=500,
        source_limit=500,
    )
    items = snapshot[0]
    if export_format == NotificationDeliveryActivityExportFormat.JSONL:
        body = "\n".join(json.dumps(item.model_dump(mode="json"), ensure_ascii=False) for item in items)
        return PlainTextResponse(body, media_type="application/x-ndjson")
    lines = [
        "activity_id,action,event_kind,delivery_source,root_scope,status,detail,signal_count,provider_message_id,created_at"
    ]
    for item in items:
        cells = [
            item.activity_id,
            item.action.value,
            item.event_kind.value,
            item.delivery_source or "",
            item.root_scope or "",
            item.status,
            item.detail.replace('"', "'"),
            str(len(item.signal_ids)),
            item.provider_message_id or "",
            item.created_at.isoformat(),
        ]
        lines.append(",".join(f'"{cell}"' for cell in cells))
    return PlainTextResponse("\n".join(lines), media_type="text/csv")


@router.get("/api/v1/workspace/journal", response_model=JournalWorkspaceSnapshot)
async def get_workspace_journal_snapshot(
    root: str | None = None,
    status: SignalStatus | None = None,
    kind: JournalEntryKind | None = None,
    signal_id: str | None = None,
) -> JournalWorkspaceSnapshot:
    _ensure_dashboard_enabled()
    return get_app_container().dashboard_service.build_journal_snapshot(
        root=root,
        status=status,
        kind=kind,
        signal_id=signal_id,
    )


@router.get("/workspace/journal", response_class=HTMLResponse)
async def get_workspace_journal_page(
    request: Request,
    root: str | None = None,
    status: SignalStatus | None = None,
    kind: JournalEntryKind | None = None,
    signal_id: str | None = None,
) -> HTMLResponse:
    _ensure_dashboard_enabled()
    language = _resolve_language(request)
    snapshot = get_app_container().dashboard_service.build_journal_snapshot(
        root=root,
        status=status,
        kind=kind,
        signal_id=signal_id,
    )
    return HTMLResponse(_decorate_html_page(_render_journal_workspace(snapshot), language=language, page_key="journal"))


@router.get("/api/v1/workspace/signals/{signal_id}", response_model=WorkspaceSignalSnapshot)
async def get_workspace_signal_snapshot(signal_id: str) -> WorkspaceSignalSnapshot:
    _ensure_dashboard_enabled()
    return _build_signal_workspace_snapshot(signal_id)


@router.get("/workspace/signals/{signal_id}", response_class=HTMLResponse)
async def get_workspace_signal_page(request: Request, signal_id: str) -> HTMLResponse:
    _ensure_dashboard_enabled()
    language = _resolve_language(request)
    snapshot = _build_signal_workspace_snapshot(signal_id)
    return HTMLResponse(
        _decorate_html_page(_render_signal_workspace(snapshot, language=language), language=language, page_key="signal")
    )


@router.get("/api/v1/dashboard", response_model=DashboardSnapshot)
async def get_dashboard_snapshot(root: str | None = None) -> DashboardSnapshot:
    _ensure_dashboard_enabled()
    return get_app_container().dashboard_service.build_snapshot(root=root)


@router.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard_page(request: Request, root: str | None = None) -> HTMLResponse:
    _ensure_dashboard_enabled()
    language = _resolve_language(request)
    snapshot = get_app_container().dashboard_service.build_snapshot(root=root)
    return HTMLResponse(
        _decorate_html_page(_render_dashboard(snapshot, language=language), language=language, page_key="dashboard")
    )


def _render_dashboard(snapshot: DashboardSnapshot, *, language: str) -> str:
    sidebar = _render_page_sidebar("dashboard", root=snapshot.selected_root, roots=snapshot.roots)
    sidebar_styles = _render_page_sidebar_styles("1240px")
    root_links = "".join(
        (
            f'<a class="root-pill{" is-active" if item.root_code == snapshot.selected_root else ""}" '
            f'href="/dashboard?root={escape(item.root_code)}">'
            f'<span>{escape(item.root_code)}</span>'
            f'<small>{escape(item.base_asset)}</small>'
            "</a>"
        )
        for item in snapshot.roots
    )
    kpis = "".join(
        (
            f'<article class="kpi-card tone-{escape(item.tone)}">'
            f"<span>{escape(item.label)}</span>"
            f"<strong>{escape(item.value)}</strong>"
            f"<p>{escape(item.detail or '')}</p>"
            "</article>"
        )
        for item in snapshot.kpis
    )
    spotlight = "".join(_render_signal_card(item) for item in snapshot.spotlight_signals) or '<p class="empty">No active signals yet.</p>'
    recent = "".join(_render_signal_row(item) for item in snapshot.recent_signals) or '<p class="empty">No recent signals yet.</p>'
    quality = "".join(_render_quality_pair(item) for item in snapshot.quality_pairs)
    session_block = ""
    if snapshot.root_details is not None:
        root = snapshot.root_details.root
        session = snapshot.root_details.session
        continuous = snapshot.root_details.continuous_series
        market_data_context = _render_market_data_context(snapshot.control_panel)
        expiry_summary = _format_expiry_countdown(
            continuous.days_to_expiry,
            continuous.expiry_date,
            language=language,
        )
        session_block = (
            '<section class="panel spotlight">'
            '<div class="panel-head"><h2>Root Control Room</h2>'
            f'<a class="ghost-link" href="/api/v1/roots/{escape(root.root_code)}/deep-dive">Open deep-dive JSON</a>'
            "</div>"
            '<div class="spotlight-grid">'
            f'<div><label>Universe</label><strong>{escape(root.universe_status.value)}</strong></div>'
            f'<div><label>Session</label><strong>{escape(session.session_type.value)}</strong></div>'
            f'<div><label>Trading Day</label><strong>{escape(session.trading_day.isoformat())}</strong></div>'
            f'<div><label>Rule Set</label><strong>{escape(session.effective_rule_set)}</strong></div>'
            f'<div><label>Active Contract</label><strong>{escape(continuous.active_contract)}</strong></div>'
            f'<div><label>Next Contract</label><strong>{escape(continuous.next_contract)}</strong></div>'
            f'<div><label>Days To Expiry</label><strong>{escape(expiry_summary)}</strong></div>'
            f'<div><label>Days To Last Trade</label><strong>{continuous.days_to_last_trade}</strong></div>'
            f'<div><label>Next Share</label><strong>{continuous.next_contract_share:.0%}</strong></div>'
            f"{market_data_context}"
            "</div>"
            "</section>"
        )

    payload = escape(json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>IMOEX Signal Dashboard</title>
  <style>
    :root {{
      --bg-1: #f4efe6;
      --bg-2: #dceae4;
      --ink: #16222b;
      --muted: #5f6d73;
      --panel: rgba(255, 251, 245, 0.82);
      --line: rgba(22, 34, 43, 0.08);
      --teal: #116b6a;
      --orange: #c46b1d;
      --red: #b8483b;
      --green: #2f7f54;
      --shadow: 0 20px 50px rgba(17, 34, 43, 0.12);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      font-family: "Trebuchet MS", "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(196, 107, 29, 0.18), transparent 30%),
        radial-gradient(circle at right, rgba(17, 107, 106, 0.18), transparent 25%),
        linear-gradient(160deg, var(--bg-1), var(--bg-2));
      min-height: 100vh;
    }}
    a {{ color: inherit; text-decoration: none; }}
    .shell {{
      width: min(1240px, calc(100% - 32px));
      margin: 24px auto 40px;
    }}
    .hero, .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      box-shadow: var(--shadow);
      backdrop-filter: blur(16px);
      border-radius: 28px;
    }}
    .hero {{
      padding: 28px;
      position: relative;
      overflow: hidden;
    }}
    .hero::after {{
      content: "";
      position: absolute;
      inset: auto -40px -50px auto;
      width: 220px;
      height: 220px;
      background: linear-gradient(135deg, rgba(17, 107, 106, 0.2), rgba(196, 107, 29, 0.08));
      border-radius: 44px;
      transform: rotate(18deg);
    }}
    .eyebrow {{
      display: inline-flex;
      gap: 10px;
      align-items: center;
      padding: 8px 14px;
      border-radius: 999px;
      background: rgba(17, 107, 106, 0.08);
      color: var(--teal);
      font-size: 12px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    h1 {{
      margin: 14px 0 10px;
      font-family: Georgia, "Palatino Linotype", serif;
      font-size: clamp(34px, 6vw, 58px);
      line-height: 0.95;
      max-width: 8ch;
    }}
    .hero p {{
      max-width: 700px;
      color: var(--muted);
      font-size: 16px;
      line-height: 1.55;
    }}
    .hero-actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-top: 18px;
    }}
    .hero-actions a {{
      padding: 12px 16px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.6);
    }}
    .hero-actions a.primary {{
      background: var(--ink);
      color: #fff8f0;
    }}
    .root-strip {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
      gap: 12px;
      margin: 20px 0 22px;
    }}
    .root-pill {{
      padding: 14px 16px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.62);
      display: flex;
      flex-direction: column;
      gap: 4px;
      transition: transform 120ms ease, border-color 120ms ease;
    }}
    .root-pill:hover {{ transform: translateY(-1px); }}
    .root-pill span {{ font-size: 20px; font-weight: 700; }}
    .root-pill small {{ color: var(--muted); }}
    .root-pill.is-active {{
      border-color: rgba(17, 107, 106, 0.35);
      background: linear-gradient(135deg, rgba(17, 107, 106, 0.12), rgba(255, 255, 255, 0.78));
    }}
    .kpi-grid, .content-grid {{
      display: grid;
      gap: 16px;
    }}
    .kpi-grid {{
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      margin-bottom: 16px;
    }}
    .kpi-card {{
      padding: 16px 18px;
      border-radius: 20px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.62);
    }}
    .kpi-card span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 12px;
    }}
    .kpi-card strong {{
      font-size: 28px;
      line-height: 1;
      display: block;
      margin-bottom: 8px;
    }}
    .kpi-card p {{ margin: 0; color: var(--muted); font-size: 13px; line-height: 1.4; }}
    .tone-positive strong {{ color: var(--green); }}
    .tone-warning strong {{ color: var(--orange); }}
    .tone-negative strong {{ color: var(--red); }}
    .content-grid {{
      grid-template-columns: minmax(0, 1.35fr) minmax(0, 1fr);
      align-items: start;
    }}
    .stack {{ display: grid; gap: 16px; }}
    .panel {{ padding: 22px; }}
    .panel-head {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 12px;
      margin-bottom: 18px;
    }}
    .panel h2 {{
      margin: 0;
      font-size: 22px;
      font-family: Georgia, "Palatino Linotype", serif;
    }}
    .ghost-link {{ color: var(--teal); font-size: 14px; }}
    .signal-card {{
      padding: 16px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.7);
      display: grid;
      gap: 10px;
      margin-bottom: 12px;
    }}
    .signal-card:last-child {{ margin-bottom: 0; }}
    .signal-top, .signal-meta, .signal-row {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      gap: 10px;
      align-items: center;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 7px 10px;
      border-radius: 999px;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      background: rgba(17, 107, 106, 0.09);
      color: var(--teal);
    }}
    .workflow-chip {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 7px 10px;
      border-radius: 999px;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      background: rgba(25, 58, 82, 0.08);
      color: var(--navy);
    }}
    .workflow-chip.tone-review {{
      background: rgba(182, 109, 31, 0.14);
      color: var(--amber);
    }}
    .workflow-chip.tone-ignore {{
      background: rgba(94, 107, 115, 0.14);
      color: var(--muted);
    }}
    .workflow-chip.tone-escalate {{
      background: rgba(182, 75, 61, 0.14);
      color: var(--coral);
    }}
    .workflow-panel {{
      display: grid;
      gap: 12px;
      padding: 14px 16px;
      border-radius: 20px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.62);
      margin: 14px 0;
    }}
    .workflow-meta {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: flex-start;
    }}
    .workflow-meta span {{
      display: block;
      margin-bottom: 6px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 11px;
    }}
    .workflow-summary {{
      margin: 0;
      color: var(--muted);
      line-height: 1.5;
    }}
    .workflow-actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .workflow-button {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 10px 12px;
      border-radius: 12px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.84);
      color: var(--ink);
      font: inherit;
      font-weight: 600;
      cursor: pointer;
    }}
    .workflow-button:disabled {{
      opacity: 0.55;
      cursor: not-allowed;
    }}
    .workflow-button.is-active {{
      border-color: transparent;
      color: #fff8ef;
    }}
    .workflow-button.tone-watch.is-active {{
      background: var(--navy);
    }}
    .workflow-button.tone-review.is-active {{
      background: var(--amber);
    }}
    .workflow-button.tone-ignore.is-active {{
      background: var(--muted);
    }}
    .workflow-button.tone-escalate.is-active {{
      background: var(--coral);
    }}
    .workflow-button.tone-ready.is-active {{
      background: var(--teal);
    }}
    .workflow-button.tone-resolved.is-active {{
      background: rgba(23, 56, 79, 0.72);
    }}
    .signal-summary, .metric-list p, .signal-row small, .empty {{
      color: var(--muted);
      line-height: 1.45;
    }}
    .signal-table {{
      display: grid;
      gap: 10px;
    }}
    .signal-row {{
      padding: 14px 0;
      border-top: 1px solid var(--line);
    }}
    .signal-row:first-child {{ border-top: 0; padding-top: 0; }}
    .signal-row:last-child {{ padding-bottom: 0; }}
    .metric-list {{
      display: grid;
      gap: 12px;
    }}
    .metric-list article {{
      padding: 14px 16px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.62);
      display: grid;
      gap: 8px;
      align-content: start;
    }}
    .metric-list strong {{ display: block; margin-bottom: 4px; }}
    .spotlight-grid,
    .control-summary-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
      gap: 14px;
    }}
    .spotlight-grid div,
    .control-summary-card {{
      padding: 14px 16px;
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.66);
      border: 1px solid var(--line);
      display: grid;
      gap: 8px;
      align-content: start;
      min-height: 108px;
    }}
    .spotlight-grid label,
    .control-summary-card label {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 8px;
    }}
    .spotlight-grid strong,
    .control-summary-card strong {{
      display: block;
      font-size: 18px;
      line-height: 1.25;
      overflow-wrap: anywhere;
    }}
    .control-summary-card small {{
      color: var(--muted);
      line-height: 1.45;
    }}
    .control-summary-card.is-wide {{
      grid-column: span 2;
    }}
    @media (max-width: 760px) {{
      .control-summary-card.is-wide {{
        grid-column: span 1;
      }}
    }}
    pre {{
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: Consolas, "Courier New", monospace;
      font-size: 12px;
      color: var(--muted);
    }}
    @media (max-width: 960px) {{
      .content-grid {{ grid-template-columns: 1fr; }}
      .shell {{ width: min(100% - 18px, 1240px); }}
      .hero {{ padding: 22px; }}
    }}
    {sidebar_styles}
  </style>
</head>
<body>
  <div class="page-shell">
  {sidebar}
  <main class="shell">
    <section class="hero">
      <span class="eyebrow">IMOEX Signals · Dashboard</span>
      <h1>Signal room for {escape(snapshot.selected_root)}</h1>
      <p>
        Delivery-layer dashboard over the live signal pipeline: roots, current signal inventory,
        evaluation status, source quality and operational health in one place.
      </p>
      <div class="hero-actions">
        <a class="primary" href="/api/v1/dashboard?root={escape(snapshot.selected_root)}">Open JSON snapshot</a>
        <a href="/api/v1/signals?root={escape(snapshot.selected_root)}">Inspect signals API</a>
        <a href="/api/v1/admin/health">Inspect admin health</a>
      </div>
    </section>
    <section class="root-strip">{root_links}</section>
    <section class="kpi-grid">{kpis}</section>
    <section class="content-grid">
      <div class="stack">
        <section class="panel">
          <div class="panel-head">
            <h2>Active Signal Spotlight</h2>
            <a class="ghost-link" href="/api/v1/signals?root={escape(snapshot.selected_root)}&status=active">Open API list</a>
          </div>
          {spotlight}
        </section>
        {session_block}
        <section class="panel">
          <div class="panel-head">
            <h2>Recent Signal Tape</h2>
          </div>
          <div class="signal-table">{recent}</div>
        </section>
      </div>
      <div class="stack">
        <section class="panel">
          <div class="panel-head">
            <h2>Evaluation</h2>
            <a class="ghost-link" href="/api/v1/quality/evaluation-report?root={escape(snapshot.selected_root)}">Open report</a>
          </div>
          <div class="metric-list">
            <article><strong>Resolved signals</strong><p>{snapshot.evaluation.resolved_signals}</p></article>
            <article><strong>Brier score</strong><p>{_format_optional(snapshot.evaluation.brier_score)}</p></article>
            <article><strong>Log loss</strong><p>{_format_optional(snapshot.evaluation.log_loss)}</p></article>
            <article><strong>Top-{snapshot.evaluation.top_k} precision</strong><p>{_format_optional(snapshot.evaluation.top_k_precision)}</p></article>
          </div>
        </section>
        <section class="panel">
          <div class="panel-head">
            <h2>Platform Health</h2>
            <a class="ghost-link" href="/api/v1/admin/health">Open health JSON</a>
          </div>
          <div class="metric-list">
            <article><strong>Status</strong><p>{escape(snapshot.admin_health.status)}</p></article>
            <article><strong>DB status</strong><p>{escape(snapshot.admin_health.database_status)}</p></article>
            <article><strong>Active / resolved</strong><p>{snapshot.admin_health.active_signals} / {snapshot.admin_health.resolved_signals}</p></article>
            <article><strong>Backups</strong><p>{snapshot.admin_health.backup_artifacts}</p></article>
          </div>
        </section>
        <section class="panel">
          <div class="panel-head">
            <h2>Source Quality</h2>
            <a class="ghost-link" href="/api/v1/quality/summary?provider_a=moex&provider_b=finam">Open quality API</a>
          </div>
          <div class="metric-list">{quality}</div>
        </section>
        <section class="panel">
          <div class="panel-head">
            <h2>Snapshot Payload</h2>
          </div>
          <pre id="dashboard-data">{payload}</pre>
        </section>
      </div>
    </section>
  </main>
  </div>
</body>
</html>"""


def _render_runtime_control_page(
    snapshot: RuntimeControlSnapshot,
    *,
    dashboard_snapshot: DashboardSnapshot,
    language: str,
) -> str:
    sidebar = _render_page_sidebar("runtime", root=dashboard_snapshot.selected_root, roots=dashboard_snapshot.roots)
    sidebar_styles = _render_page_sidebar_styles("1320px")
    panel = dashboard_snapshot.control_panel
    confidence = dashboard_snapshot.system_confidence
    is_ru = language == "ru"
    copy = {
        "eyebrow": "Runtime control | Operator workflow" if not is_ru else "Управление runtime | Операторский сценарий",
        "title": "Runtime control panel" if not is_ru else "Пульт управления runtime",
        "intro": (
            "Edit role routing, adjust freshness SLAs, and keep an audit trail of every runtime change."
            if not is_ru
            else "Меняйте маршрутизацию ролей, корректируйте SLA по актуальности и держите под рукой журнал всех изменений runtime."
        ),
        "open_json": "Open runtime JSON" if not is_ru else "Открыть JSON runtime",
        "open_dashboard": "Open operations dashboard" if not is_ru else "Открыть ops-дашборд",
        "open_workspace": "Open workspace" if not is_ru else "Открыть рабочее пространство",
        "summary": "Current runtime summary" if not is_ru else "Текущая сводка runtime",
        "routes": "Editable role routing" if not is_ru else "Редактируемая маршрутизация ролей",
        "freshness": "Freshness policy" if not is_ru else "Политика актуальности",
        "audit": "Audit trail" if not is_ru else "Журнал изменений",
        "save": "Save route" if not is_ru else "Сохранить маршрут",
        "reset": "Reset routes to defaults" if not is_ru else "Сбросить маршруты к умолчанию",
        "save_policy": "Save freshness policy" if not is_ru else "Сохранить политику",
        "status_idle": "Runtime control is ready." if not is_ru else "Пульт runtime готов к работе.",
        "status_saving": "Saving runtime change..." if not is_ru else "Сохраняем изменение runtime...",
        "status_saved": "Runtime control updated. Refreshing..." if not is_ru else "Runtime обновлён. Перезагружаем страницу...",
        "status_failed": "Runtime update failed." if not is_ru else "Не удалось обновить runtime.",
    }
    reference_line = (
        f"{_control_panel_reference_sync_label(panel.reference_sync.status)} · "
        f"{_control_panel_reference_sync_source(panel.reference_sync.source)}"
    )
    summary_cards = (
        f'<article><span>{"Selected root" if not is_ru else "Выбранная серия"}</span>'
        f'<strong>{escape(dashboard_snapshot.selected_root)}</strong>'
        f'<p class="muted">{escape(confidence.label)} · score {confidence.score}</p></article>'
        f'<article><span>{"Data mode" if not is_ru else "Режим данных"}</span>'
        f'<strong>{escape(_control_panel_data_mode_label(panel.data_mode))}</strong>'
        f'<p class="muted">{escape(panel.data_mode_detail or "")}</p></article>'
        f'<article><span>{"Reference sync" if not is_ru else "Справочник"}</span>'
        f'<strong>{escape(reference_line)}</strong>'
        f'<p class="muted">{escape(_format_timestamp(panel.reference_sync.last_sync_at))}</p></article>'
        f'<article><span>{"Generated at" if not is_ru else "Снимок на"}</span>'
        f'<strong>{escape(_format_timestamp(snapshot.generated_at))}</strong>'
        f'<p class="muted">{escape(_format_timestamp(panel.latest_market_data_at))} · market data</p></article>'
    )
    route_cards = "".join(
        (
            '<article class="route-card">'
            f'<div class="route-head"><div><strong>{escape(item.role_label)}</strong><p class="muted">{escape(item.role_key)}</p></div>'
            f'<span class="badge">{escape(item.control_mode)}</span></div>'
            f'<form class="route-form" data-runtime-route-form>'
            f'<input type="hidden" name="role_key" value="{escape(item.role_key)}">'
            '<div class="field-grid">'
            f'<label><span>{"Owner" if not is_ru else "Владелец"}</span><input name="owner" value="{escape(item.owner)}" required></label>'
            f'<label><span>{"Product" if not is_ru else "Продукт"}</span><input name="product" value="{escape(item.product)}" required></label>'
            f'<label><span>{"Model" if not is_ru else "Модель"}</span><input name="model" value="{escape(item.model)}" required></label>'
            f'<label><span>{"Control mode" if not is_ru else "Режим управления"}</span>'
            f'<select name="control_mode"><option value="editable"{" selected" if item.control_mode == "editable" else ""}>editable</option>'
            f'<option value="fixed"{" selected" if item.control_mode == "fixed" else ""}>fixed</option></select></label>'
            "</div>"
            f'<label class="detail-field"><span>{"Detail" if not is_ru else "Пояснение"}</span><textarea name="detail" rows="2">{escape(item.detail or "")}</textarea></label>'
            f'<button class="button primary" type="submit">{escape(copy["save"])}</button>'
            "</form>"
            "</article>"
        )
        for item in snapshot.model_routes
    ) or f'<p class="empty">{"No model routes configured yet." if not is_ru else "Маршруты ролей пока не настроены."}</p>'
    freshness = snapshot.freshness_policy
    audit_cards = "".join(
        (
            '<article class="audit-card">'
            f'<div class="audit-head"><strong>{escape(item.detail)}</strong><span>{escape(item.action)}</span></div>'
            f'<p class="muted">{escape(item.category)}'
            f'{" · " + escape(item.target_key) if item.target_key else ""} | {escape(_format_timestamp(item.created_at))}</p>'
            f'<pre>{escape(json.dumps(item.payload, ensure_ascii=False, indent=2))}</pre>'
            "</article>"
        )
        for item in snapshot.audit_trail
    ) or f'<p class="empty">{"No runtime audit events yet." if not is_ru else "В журнале runtime пока нет событий."}</p>'
    payload = escape(json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False))
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(copy["title"])}</title>
  <style>
    :root {{
      --bg: #f5efe5;
      --paper: rgba(255, 250, 242, 0.92);
      --ink: #18222b;
      --muted: #5b6871;
      --line: rgba(24, 34, 43, 0.1);
      --navy: #17384f;
      --teal: #116866;
      --amber: #ba7021;
      --red: #b44a3d;
      --shadow: 0 18px 46px rgba(24, 34, 43, 0.11);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      font-family: "Segoe UI", "Trebuchet MS", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(23, 56, 79, 0.12), transparent 25%),
        radial-gradient(circle at right, rgba(17, 104, 102, 0.16), transparent 22%),
        linear-gradient(180deg, #fbf7f0, var(--bg));
    }}
    a {{ color: inherit; text-decoration: none; }}
    .shell {{ width: 100%; margin: 0; display: grid; gap: 16px; }}
    .hero, .panel {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 30px;
      box-shadow: var(--shadow);
      padding: 24px;
      backdrop-filter: blur(12px);
    }}
    .hero {{
      display: grid;
      grid-template-columns: minmax(0, 1.3fr) minmax(280px, 0.95fr);
      gap: 18px;
    }}
    .eyebrow {{
      display: inline-flex;
      gap: 8px;
      align-items: center;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(23, 56, 79, 0.08);
      color: var(--navy);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 12px;
    }}
    h1 {{
      margin: 14px 0 10px;
      font-family: Georgia, "Palatino Linotype", serif;
      font-size: clamp(34px, 5vw, 56px);
      line-height: 0.98;
      max-width: 11ch;
    }}
    h2 {{
      margin: 0;
      font-family: Georgia, "Palatino Linotype", serif;
      font-size: 22px;
    }}
    .muted, .empty, pre {{ color: var(--muted); line-height: 1.55; }}
    .hero-actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 16px;
    }}
    .button {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 11px 15px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.68);
      color: var(--ink);
      font: inherit;
      font-weight: 700;
      cursor: pointer;
    }}
    .button.primary {{
      background: var(--navy);
      border-color: transparent;
      color: #fbf7f0;
    }}
    .summary-grid, .route-grid, .audit-grid, .field-grid {{
      display: grid;
      gap: 14px;
    }}
    .summary-grid {{
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
    }}
    .summary-grid article, .route-card, .audit-card {{
      border: 1px solid var(--line);
      border-radius: 22px;
      background: rgba(255, 255, 255, 0.68);
      padding: 18px;
    }}
    .summary-grid span, .field-grid span, .detail-field span {{
      display: block;
      margin-bottom: 8px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 11px;
    }}
    .route-grid {{
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    }}
    .route-head, .audit-head, .panel-head {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: baseline;
      margin-bottom: 14px;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      padding: 7px 11px;
      border-radius: 999px;
      background: rgba(17, 104, 102, 0.1);
      color: var(--teal);
      font-size: 12px;
      font-weight: 700;
    }}
    .route-form {{
      display: grid;
      gap: 12px;
    }}
    .field-grid {{
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }}
    label {{
      display: grid;
      gap: 6px;
      font-weight: 600;
    }}
    input, select, textarea {{
      width: 100%;
      padding: 11px 12px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.88);
      color: var(--ink);
      font: inherit;
    }}
    textarea {{
      resize: vertical;
      min-height: 84px;
    }}
    .detail-field {{
      grid-column: 1 / -1;
    }}
    .policy-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 14px;
      margin-top: 14px;
    }}
    .status {{
      min-height: 24px;
      font-weight: 600;
      color: var(--teal);
    }}
    .status[data-tone="error"] {{
      color: var(--red);
    }}
    pre {{
      margin: 0;
      padding: 12px 14px;
      border-radius: 16px;
      background: rgba(24, 34, 43, 0.04);
      overflow: auto;
      white-space: pre-wrap;
      word-break: break-word;
    }}
    .panel-note {{
      margin: 0 0 14px;
      color: var(--muted);
      line-height: 1.55;
    }}
    @media (max-width: 980px) {{
      .hero {{
        grid-template-columns: 1fr;
      }}
      .field-grid {{
        grid-template-columns: 1fr;
      }}
    }}
    {sidebar_styles}
  </style>
</head>
<body>
  <div class="page-shell">
  {sidebar}
  <main class="shell">
    <section class="hero">
      <div>
        <span class="eyebrow">{escape(copy["eyebrow"])}</span>
        <h1>{escape(copy["title"])}</h1>
        <p class="muted">{escape(copy["intro"])}</p>
        <div class="hero-actions">
          <a class="button primary" href="/api/v1/runtime/control-panel" data-swap-link>{escape(copy["open_json"])}</a>
          <a class="button" href="/dashboard?root={escape(dashboard_snapshot.selected_root)}" data-swap-link>{escape(copy["open_dashboard"])}</a>
          <a class="button" href="/workspace?root={escape(dashboard_snapshot.selected_root)}" data-swap-link>{escape(copy["open_workspace"])}</a>
        </div>
      </div>
      <aside class="panel" style="padding:18px;">
        <div class="panel-head"><h2>{escape(copy["summary"])}</h2></div>
        <div class="summary-grid">{summary_cards}</div>
      </aside>
    </section>
    <section class="panel">
      <div class="panel-head">
        <h2>{escape(copy["routes"])}</h2>
        <button class="button" type="button" data-runtime-reset>{escape(copy["reset"])}</button>
      </div>
      <p class="panel-note">{"Roles can be edited one by one and each save writes to the runtime audit trail." if not is_ru else "Роли редактируются по одной, и каждое сохранение попадает в журнал runtime."}</p>
      <div class="route-grid">{route_cards}</div>
    </section>
    <section class="panel">
      <div class="panel-head"><h2>{escape(copy["freshness"])}</h2></div>
      <p class="panel-note">{"Tune how the app classifies market data as fresh, aging, stale, or degraded." if not is_ru else "Настройте, как приложение относит рыночные данные к fresh, aging, stale и degraded."}</p>
      <form data-runtime-policy-form>
        <div class="policy-grid">
          <label><span>fresh</span><input type="number" min="1" name="fresh_max_seconds" value="{freshness.fresh_max_seconds}" required></label>
          <label><span>aging</span><input type="number" min="1" name="aging_max_seconds" value="{freshness.aging_max_seconds}" required></label>
          <label><span>stale</span><input type="number" min="1" name="stale_max_seconds" value="{freshness.stale_max_seconds}" required></label>
          <label><span>degraded</span><input type="number" min="1" name="degraded_max_seconds" value="{freshness.degraded_max_seconds}" required></label>
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin-top:14px;">
          <button class="button primary" type="submit">{escape(copy["save_policy"])}</button>
          <div class="status" data-runtime-status>{escape(copy["status_idle"])}</div>
        </div>
      </form>
    </section>
    <section class="panel">
      <div class="panel-head"><h2>{escape(copy["audit"])}</h2></div>
      <p class="panel-note">{"Each runtime write is visible here with the structured payload that changed." if not is_ru else "Здесь видна каждая запись в runtime вместе со структурированным payload изменённых данных."}</p>
      <div class="audit-grid">{audit_cards}</div>
    </section>
    <script id="runtime-control-data" type="application/json">{payload}</script>
  </main>
  </div>
  <script>
    (() => {{
      const status = document.querySelector("[data-runtime-status]");
      const setStatus = (message, tone = "ok") => {{
        if (!status) {{
          return;
        }}
        status.textContent = message;
        status.dataset.tone = tone === "error" ? "error" : "ok";
      }};
      const postJson = async (url, payload) => {{
        const response = await fetch(url, {{
          method: "POST",
          credentials: "same-origin",
          headers: {{
            "Content-Type": "application/json",
            "X-Requested-With": "imoex-ui",
          }},
          body: JSON.stringify(payload),
        }});
        if (!response.ok) {{
          throw new Error(await response.text());
        }}
        return await response.json();
      }};
      document.querySelectorAll("[data-runtime-route-form]").forEach((form) => {{
        form.addEventListener("submit", async (event) => {{
          event.preventDefault();
          const formData = new FormData(form);
          const payload = Object.fromEntries(formData.entries());
          setStatus({json.dumps(copy["status_saving"], ensure_ascii=False)});
          try {{
            await postJson("/api/v1/runtime/control-panel/model-route", payload);
            setStatus({json.dumps(copy["status_saved"], ensure_ascii=False)});
            await window.__imoexRefreshPage();
          }} catch {{
            setStatus({json.dumps(copy["status_failed"], ensure_ascii=False)}, "error");
          }}
        }});
      }});
      const resetButton = document.querySelector("[data-runtime-reset]");
      if (resetButton) {{
        resetButton.addEventListener("click", async () => {{
          setStatus({json.dumps(copy["status_saving"], ensure_ascii=False)});
          try {{
            await postJson("/api/v1/runtime/control-panel/model-route/reset", {{}});
            setStatus({json.dumps(copy["status_saved"], ensure_ascii=False)});
            await window.__imoexRefreshPage();
          }} catch {{
            setStatus({json.dumps(copy["status_failed"], ensure_ascii=False)}, "error");
          }}
        }});
      }}
      const policyForm = document.querySelector("[data-runtime-policy-form]");
      if (policyForm) {{
        policyForm.addEventListener("submit", async (event) => {{
          event.preventDefault();
          const formData = new FormData(policyForm);
          const payload = Object.fromEntries(
            Array.from(formData.entries()).map(([key, value]) => [key, Number(value)])
          );
          setStatus({json.dumps(copy["status_saving"], ensure_ascii=False)});
          try {{
            await postJson("/api/v1/runtime/control-panel/freshness-policy", payload);
            setStatus({json.dumps(copy["status_saved"], ensure_ascii=False)});
            await window.__imoexRefreshPage();
          }} catch {{
            setStatus({json.dumps(copy["status_failed"], ensure_ascii=False)}, "error");
          }}
        }});
      }}
    }})();
  </script>
</body>
</html>"""


def _render_workspace(snapshot: WorkspaceSnapshot, *, language: str) -> str:
    sidebar = _render_page_sidebar(
        "workspace",
        root=snapshot.selected_root,
        roots=snapshot.roots,
        signal_id=snapshot.focus_signal.signal_id if snapshot.focus_signal is not None else None,
    )
    sidebar_styles = _render_page_sidebar_styles("1320px")
    focus = snapshot.focus_signal
    root_details = snapshot.root_details
    focus_visual = snapshot.focus_visual
    root_links = "".join(
        _render_root_pulse_card(item, selected_root=snapshot.selected_root, language=language)
        for item in snapshot.pulses
    )
    signal_lane = "".join(
        _render_workspace_signal_tile(item, snapshot.selected_signal_id, language=language)
        for item in snapshot.signal_lane
    ) or '<p class="empty">No signals available for the selected root yet.</p>'
    actions = "".join(_render_action_item(item) for item in snapshot.action_items)
    visual_bars = _render_metric_bars(focus_visual.metric_bars if focus_visual is not None else [], compact=True)
    visual_timeline = _render_timeline(focus_visual.timeline if focus_visual is not None else [], compact=True)
    drivers = "".join(f"<li>{escape(item)}</li>" for item in (focus.drivers if focus is not None else [])) or "<li>No drivers recorded yet.</li>"
    objections = "".join(f"<li>{escape(item)}</li>" for item in (focus.objections if focus is not None else [])) or "<li>No objections recorded yet.</li>"
    invalidations = "".join(f"<li>{escape(item)}</li>" for item in (focus.invalidation_conditions if focus is not None else [])) or "<li>No invalidation conditions recorded yet.</li>"
    journal_rows = "".join(_render_journal_entry(item) for item in (focus.journal_entries if focus is not None else [])) or '<p class="empty">No journal entries yet. Capture thesis and risk before acting.</p>'

    focus_header = "No focus signal yet"
    focus_summary = "Select a root or wait for the next recalculation cycle."
    focus_badge = "scan mode"
    confidence = "n/a"
    skeptic = "n/a"
    workflow_label = "watching"
    if focus is not None:
        focus_header = f"{focus.root} | {focus.contract} | {focus.horizon.value}"
        focus_summary = focus.summary
        focus_badge = f"{focus.direction_final.value} | {focus.status.value}"
        confidence = f"{focus.confidence_final:.2f}"
        skeptic = f"{focus.skeptic_score:.2f}"
        workflow_label = _workflow_state_label(focus.workflow_state)

    session_band = ""
    if root_details is not None:
        market_data_context = _render_market_data_context(snapshot.control_panel)
        expiry_summary = _format_expiry_countdown(
            root_details.continuous_series.days_to_expiry,
            root_details.continuous_series.expiry_date,
            language=language,
        )
        session_band = (
            '<section class="panel band">'
            "<h2>Context band</h2>"
            '<div class="band-grid">'
            f'<article><span>Session</span><strong>{escape(root_details.session.session_type.value)}</strong><p>Trading day {escape(root_details.session.trading_day.isoformat())}</p></article>'
            f'<article><span>Active contract</span><strong>{escape(root_details.continuous_series.active_contract)}</strong><p>Next {escape(root_details.continuous_series.next_contract)}</p></article>'
            f'<article><span>Days To Expiry</span><strong>{escape(expiry_summary)}</strong><p>Until contract expiry</p></article>'
            f'<article><span>Roll risk</span><strong>{root_details.continuous_series.next_contract_share:.0%}</strong><p>{escape(root_details.continuous_series.roll_state)}</p></article>'
            f'<article><span>Universe</span><strong>{escape(root_details.root.universe_status.value)}</strong><p>Liquidity rank {root_details.root.liquidity_rank}</p></article>'
            f"{market_data_context}"
            "</div>"
            "</section>"
        )

    telegram_preview = escape(snapshot.telegram_preview_message or "Telegram preview is not available.")
    delivery_windows = _render_delivery_windows(snapshot.delivery_windows)
    delivery_activity = _render_delivery_activity(snapshot.delivery_activity)
    delivery_activity_controls = _render_delivery_activity_controls(
        base_path="/workspace",
        root=snapshot.selected_root,
        signal_id=snapshot.selected_signal_id,
        filters=snapshot.delivery_activity_filters,
        by_event_kind=snapshot.delivery_activity_by_event_kind,
        by_root_scope=snapshot.delivery_activity_by_root_scope,
        by_status=snapshot.delivery_activity_by_status,
    )
    delivery_activity_footer = _render_delivery_activity_footer(
        base_path="/workspace",
        export_path="/api/v1/workspace/delivery/activity/export",
        root=snapshot.selected_root,
        signal_id=snapshot.selected_signal_id,
        filters=snapshot.delivery_activity_filters,
        pagination=snapshot.delivery_activity_pagination,
    )
    quality = "".join(_render_quality_pair(item) for item in snapshot.quality_pairs)
    payload = escape(json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False))
    selected_signal_id = escape(snapshot.selected_signal_id or "")
    form_disabled = "disabled" if focus is None else ""
    workflow_panel = _render_workflow_panel(focus, status_id="workspace-workflow-status")
    primary_label = "This browser workspace"
    if snapshot.telegram_delivery_ready:
        primary_label = "Browser workspace + Telegram brief"
    trust_ribbon = _render_trust_ribbon(snapshot.trust_ribbon)
    watchlist = _render_watchlist(snapshot.watchlist)
    comparison = _render_horizon_comparison(snapshot.comparison)
    diff_block = _render_signal_diff(snapshot.focus_signal_diff)
    confidence_block = _render_confidence_decomposition(snapshot.focus_confidence)
    decision_preview = _render_decision_timeline(snapshot.decision_log_preview, title="Decision log preview")
    review_bundle = _render_review_bundle(snapshot.review_bundle)
    market_panel = _render_market_snapshot(snapshot.market_snapshot, language=language)
    root_preview_messages = json.dumps(
        {
            "loading": "Загружаем мини-график..." if language == "ru" else "Loading preview...",
            "unavailable": "Мини-просмотр недоступен." if language == "ru" else "Preview is unavailable.",
            "pick": "Выберите таймфрейм" if language == "ru" else "Pick a timeframe",
            "updated": "Обновлено" if language == "ru" else "Updated",
            "last": "Последняя" if language == "ru" else "Last",
            "open": "Открытие" if language == "ru" else "Open",
            "change": "Изменение" if language == "ru" else "Change",
            "range": "Диапазон" if language == "ru" else "Range",
        },
        ensure_ascii=False,
    )
    root_preview_timeframes = json.dumps(
        {
            "1D": "День" if language == "ru" else "Day",
            "1W": "Неделя" if language == "ru" else "Week",
            "1M": "Месяц" if language == "ru" else "Month",
        },
        ensure_ascii=False,
    )
    signal_preview_messages = json.dumps(
        {
            "loading": "Загружаем сигнал..." if language == "ru" else "Loading signal...",
            "unavailable": (
                "Мини-просмотр сигнала недоступен."
                if language == "ru"
                else "Signal preview is unavailable."
            ),
            "updated": "Обновлено" if language == "ru" else "Updated",
            "confidence": "Уверенность" if language == "ru" else "Confidence",
            "skeptic": "Скептик" if language == "ru" else "Skeptic",
            "priority": "Приоритет" if language == "ru" else "Priority",
            "workflow": "Workflow",
            "price": "Цена" if language == "ru" else "Price",
            "diff": "Что изменилось" if language == "ru" else "What changed",
            "timeline": "Последнее событие" if language == "ru" else "Latest event",
            "none": "пока нет" if language == "ru" else "none yet",
        },
        ensure_ascii=False,
    )
    compare_copy = {
        "title": "Compare mode",
        "subtitle": (
            "Закрепите две серии и два сигнала, чтобы сравнивать инструменты и сетапы бок о бок."
            if language == "ru"
            else "Pin two root series and two signal previews to compare instruments and setups side by side."
        ),
        "status_empty": "Сравнение пока пустое" if language == "ru" else "Compare board is empty",
        "clear_all": "Сбросить все" if language == "ru" else "Reset all",
        "root_slot": "Серия" if language == "ru" else "Root series",
        "signal_slot": "Сигнал" if language == "ru" else "Signal preview",
        "root_section_title": "Серия vs серия" if language == "ru" else "Root vs root",
        "root_section_note": (
            "Закрепите два инструмента из Root lane и переключайте таймфрейм прямо на доске."
            if language == "ru"
            else "Pin two instruments from Root lane and change their timeframe directly on the board."
        ),
        "signal_section_title": "Сигнал vs сигнал" if language == "ru" else "Signal vs signal",
        "signal_section_note": (
            "Держите рядом два сетапа и сравнивайте confidence, diff и последнее событие."
            if language == "ru"
            else "Keep two setups side by side and compare confidence, diff, and latest event."
        ),
        "empty_root": (
            "Закрепите mini-preview из Root lane."
            if language == "ru"
            else "Pin a mini-preview from Root lane."
        ),
        "empty_signal": (
            "Закрепите mini-preview из Signal lane."
            if language == "ru"
            else "Pin a mini-preview from Signal lane."
        ),
        "slot_a": "A",
        "slot_b": "B",
        "loading": "Загрузка..." if language == "ru" else "Loading...",
        "clear": "Убрать" if language == "ru" else "Clear",
        "focus": "В фокус" if language == "ru" else "Focus",
        "open": "Открыть" if language == "ru" else "Open",
        "confidence": "Уверенность" if language == "ru" else "Confidence",
        "skeptic": "Скептик" if language == "ru" else "Skeptic",
        "priority": "Приоритет" if language == "ru" else "Priority",
        "workflow": "Workflow",
        "price": "Цена" if language == "ru" else "Price",
        "diff": "Что изменилось" if language == "ru" else "What changed",
        "timeline": "Последнее событие" if language == "ru" else "Latest event",
        "last": "Последняя" if language == "ru" else "Last",
        "open_label": "Открытие" if language == "ru" else "Open",
        "change": "Изменение" if language == "ru" else "Change",
        "range": "Диапазон" if language == "ru" else "Range",
        "updated": "Обновлено" if language == "ru" else "Updated",
    }
    compare_messages = json.dumps(compare_copy, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>IMOEX Workspace</title>
  <style>
    :root {{
      --bg: #f6f1e7;
      --paper: rgba(255, 250, 241, 0.88);
      --ink: #17222c;
      --muted: #5e6b73;
      --line: rgba(23, 34, 44, 0.1);
      --navy: #193a52;
      --teal: #0f6c67;
      --amber: #b66d1f;
      --coral: #b64b3d;
      --mint: #2f7d5b;
      --shadow: 0 18px 46px rgba(23, 34, 44, 0.11);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      font-family: "Segoe UI", "Trebuchet MS", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(182, 109, 31, 0.17), transparent 26%),
        radial-gradient(circle at top right, rgba(15, 108, 103, 0.18), transparent 24%),
        linear-gradient(180deg, #fbf7f0, var(--bg));
    }}
    a {{ color: inherit; text-decoration: none; }}
    .shell {{ width: min(1320px, calc(100% - 28px)); margin: 18px auto 36px; }}
    .hero, .panel {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 30px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(14px);
    }}
    .hero {{
      display: grid;
      grid-template-columns: minmax(0, 1.55fr) minmax(300px, 0.9fr);
      gap: 18px;
      padding: 24px;
      overflow: hidden;
    }}
    .hero-copy, .panel {{ animation: rise 320ms ease; }}
    .eyebrow {{
      display: inline-flex;
      gap: 8px;
      align-items: center;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(25, 58, 82, 0.08);
      color: var(--navy);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 12px;
    }}
    h1 {{
      margin: 14px 0 10px;
      font-family: Georgia, "Palatino Linotype", serif;
      font-size: clamp(34px, 5vw, 58px);
      line-height: 0.96;
      max-width: 10ch;
    }}
    h2 {{
      margin: 0;
      font-family: Georgia, "Palatino Linotype", serif;
      font-size: 22px;
    }}
    h3 {{ margin: 0 0 10px; font-size: 16px; }}
    .hero-copy p, .muted, .empty {{
      color: var(--muted);
      line-height: 1.55;
    }}
    .hero-actions, .top-links {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 18px;
    }}
    .button {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 12px 16px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.62);
      font-weight: 600;
      cursor: pointer;
    }}
    .button.primary {{
      background: var(--navy);
      border-color: transparent;
      color: #fdf8f0;
    }}
    .hero-side {{
      padding: 18px;
      border-radius: 24px;
      background: linear-gradient(160deg, rgba(25, 58, 82, 0.96), rgba(15, 108, 103, 0.88));
      color: #f5efe6;
      display: grid;
      gap: 14px;
      animation: rise 420ms ease;
    }}
    .hero-side p, .hero-side small {{ color: rgba(245, 239, 230, 0.82); line-height: 1.5; }}
    .hero-kpis {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }}
    .hero-kpis article {{
      padding: 12px;
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.1);
    }}
    .hero-kpis span, .focus-grid span, .metric-list span, .band-grid span {{
      display: block;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 8px;
      color: rgba(245, 239, 230, 0.74);
    }}
    .layout {{
      display: grid;
      grid-template-columns: minmax(0, 1.5fr) minmax(320px, 0.92fr);
      gap: 16px;
      margin-top: 16px;
      align-items: start;
    }}
    .stack {{
      display: grid;
      gap: 16px;
      align-content: start;
    }}
    .panel {{ padding: 22px; }}
    .panel-head {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      gap: 12px;
      align-items: baseline;
      margin-bottom: 16px;
    }}
    .rail {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 12px;
    }}
    .rail-card {{
      display: grid;
      gap: 12px;
      padding: 16px;
      border-radius: 22px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.62);
      transition: transform 140ms ease, border-color 140ms ease;
      position: relative;
    }}
    .rail-card:hover {{ transform: translateY(-2px); }}
    .rail-card.is-active {{
      border-color: rgba(25, 58, 82, 0.35);
      background: linear-gradient(145deg, rgba(25, 58, 82, 0.12), rgba(255, 255, 255, 0.72));
    }}
    .rail-card-link {{
      display: grid;
      gap: 6px;
    }}
    .rail-card strong {{ font-size: 24px; }}
    .rail-card span {{ color: var(--muted); font-size: 14px; }}
    .rail-card small {{ line-height: 1.45; min-height: 44px; }}
    .rail-card em {{ font-style: normal; color: var(--navy); font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; }}
    .rail-card-footer {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      flex-wrap: wrap;
    }}
    .rail-card-tabs {{
      display: inline-flex;
      gap: 6px;
      flex-wrap: wrap;
    }}
    .rail-preview-button {{
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.84);
      color: var(--ink);
      font: inherit;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.08em;
      padding: 7px 10px;
      cursor: pointer;
      text-transform: uppercase;
    }}
    .rail-preview-button.is-active {{
      background: var(--navy);
      color: #fff8ef;
      border-color: transparent;
    }}
    .rail-open-link {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 8px 12px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.78);
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }}
    .rail-preview-popover {{
      position: absolute;
      top: calc(100% + 8px);
      left: 0;
      right: 0;
      z-index: 8;
      display: grid;
      gap: 10px;
      padding: 14px;
      border-radius: 18px;
      border: 1px solid rgba(25, 58, 82, 0.16);
      background: rgba(255, 251, 245, 0.97);
      box-shadow: 0 18px 36px rgba(15, 36, 48, 0.16);
      backdrop-filter: blur(16px);
    }}
    .rail-preview-popover[hidden] {{
      display: none;
    }}
    .rail-preview-head {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: baseline;
    }}
    .rail-preview-head strong {{
      font-size: 15px;
    }}
    .rail-preview-head small {{
      color: var(--muted);
      min-height: 0;
    }}
    .rail-preview-chart {{
      min-height: 96px;
    }}
    .rail-preview-chart svg {{
      width: 100%;
      height: 96px;
      display: block;
      border-radius: 14px;
      background: linear-gradient(180deg, rgba(15, 108, 103, 0.06), rgba(255, 255, 255, 0.78));
    }}
    .rail-preview-chart .empty {{
      min-height: 96px;
      display: grid;
      place-items: center;
      padding: 10px;
      text-align: center;
      border-radius: 14px;
      background: rgba(255, 255, 255, 0.74);
      border: 1px dashed var(--line);
    }}
    .rail-preview-meta {{
      display: grid;
      gap: 4px;
      font-size: 12px;
      color: var(--muted);
    }}
    .signal-lane, .action-list, .journal-list, .metric-list {{
      display: grid;
      gap: 12px;
    }}
    .visual-grid, .timeline-list {{
      display: grid;
      gap: 12px;
    }}
    .signal-tile, .focus-grid article, .metric-list article, .band-grid article, .action-card, .journal-entry, .delivery-card {{
        padding: 14px 16px;
        border-radius: 18px;
        border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.68);
      display: grid;
      gap: 8px;
      align-content: start;
    }}
    .signal-tile.is-focus {{
      border-color: rgba(15, 108, 103, 0.34);
      box-shadow: inset 0 0 0 1px rgba(15, 108, 103, 0.14);
    }}
    .signal-tile {{
      position: relative;
    }}
    .signal-tile-link {{
      display: grid;
      gap: 10px;
    }}
    .signal-tile-footer {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      flex-wrap: wrap;
    }}
    .signal-preview-tabs {{
      display: inline-flex;
      gap: 6px;
      flex-wrap: wrap;
    }}
    .signal-preview-button {{
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.84);
      color: var(--ink);
      font: inherit;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.08em;
      padding: 7px 10px;
      cursor: pointer;
      text-transform: uppercase;
    }}
    .signal-preview-button.is-active {{
      background: var(--teal);
      color: #fff8ef;
      border-color: transparent;
    }}
    .signal-preview-popover {{
      position: absolute;
      top: calc(100% + 8px);
      left: 0;
      right: 0;
      z-index: 8;
      display: grid;
      gap: 12px;
      padding: 14px;
      border-radius: 18px;
      border: 1px solid rgba(15, 108, 103, 0.16);
      background: rgba(255, 251, 245, 0.98);
      box-shadow: 0 18px 36px rgba(15, 36, 48, 0.16);
      backdrop-filter: blur(16px);
    }}
    .signal-preview-popover[hidden] {{
      display: none;
    }}
    .signal-preview-head {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: baseline;
    }}
    .signal-preview-head strong {{
      font-size: 15px;
    }}
    .signal-preview-head small {{
      color: var(--muted);
      min-height: 0;
    }}
    .signal-preview-chart {{
      min-height: 96px;
    }}
    .signal-preview-chart svg {{
      width: 100%;
      height: 96px;
      display: block;
      border-radius: 14px;
      background: linear-gradient(180deg, rgba(15, 108, 103, 0.06), rgba(255, 255, 255, 0.78));
    }}
    .signal-preview-chart .empty {{
      min-height: 96px;
      display: grid;
      place-items: center;
      padding: 10px;
      text-align: center;
      border-radius: 14px;
      background: rgba(255, 255, 255, 0.74);
      border: 1px dashed var(--line);
    }}
    .signal-preview-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
      gap: 8px;
    }}
    .signal-preview-grid article {{
      padding: 10px 12px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.74);
      display: grid;
      gap: 4px;
    }}
    .signal-preview-grid span {{
      color: var(--muted);
      font-size: 11px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .signal-preview-summary {{
      display: grid;
      gap: 6px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }}
    .signal-preview-summary strong {{
      color: var(--ink);
      font-size: 14px;
    }}
    .signal-preview-actions {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .preview-pin-button {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 8px 12px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.82);
      color: var(--ink);
      font: inherit;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      cursor: pointer;
    }}
    .preview-pin-button.is-active {{
      background: rgba(25, 58, 82, 0.12);
      color: var(--navy);
      border-color: rgba(25, 58, 82, 0.3);
    }}
    .compare-board {{
      display: grid;
      gap: 16px;
    }}
    .compare-sections {{
      display: grid;
      gap: 18px;
    }}
    .compare-section {{
      display: grid;
      gap: 12px;
    }}
    .compare-toolbar {{
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-end;
      gap: 8px;
      align-items: center;
    }}
    .compare-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 12px;
    }}
    .compare-card {{
      padding: 16px;
      border-radius: 22px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.68);
      display: grid;
      gap: 12px;
      align-content: start;
      min-height: 280px;
    }}
    .compare-card-head {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 10px;
    }}
    .compare-card-head strong {{
      display: block;
      font-size: 16px;
      margin-bottom: 4px;
    }}
    .compare-card-head p {{
      margin: 0;
      color: var(--muted);
      line-height: 1.45;
      font-size: 13px;
    }}
    .compare-card-actions {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }}
    .compare-tabs {{
      display: inline-flex;
      gap: 6px;
      flex-wrap: wrap;
    }}
    .compare-chart {{
      min-height: 120px;
    }}
    .compare-chart svg {{
      width: 100%;
      height: 120px;
      display: block;
      border-radius: 16px;
      background: linear-gradient(180deg, rgba(15, 108, 103, 0.06), rgba(255, 255, 255, 0.78));
    }}
    .compare-chart .empty {{
      min-height: 120px;
      display: grid;
      place-items: center;
      padding: 10px;
      text-align: center;
      border-radius: 16px;
      background: rgba(255, 255, 255, 0.74);
      border: 1px dashed var(--line);
    }}
    .compare-meta {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
      gap: 8px;
    }}
    .compare-meta article {{
      padding: 10px 12px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.74);
      display: grid;
      gap: 4px;
    }}
    .compare-meta span {{
      color: var(--muted);
      font-size: 11px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .compare-summary {{
      display: grid;
      gap: 6px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }}
    .compare-summary strong {{
      color: var(--ink);
      font-size: 14px;
    }}
    .compare-empty {{
      min-height: 160px;
      display: grid;
      place-items: center;
      text-align: center;
      padding: 16px;
      border-radius: 16px;
      border: 1px dashed var(--line);
      color: var(--muted);
      background: rgba(255, 255, 255, 0.72);
    }}
    .signal-top, .metric-row {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      gap: 10px;
      align-items: center;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 7px 10px;
      border-radius: 999px;
      background: rgba(15, 108, 103, 0.08);
      color: var(--teal);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 12px;
    }}
    .focus-card {{
      display: grid;
      gap: 16px;
      padding: 20px;
      border-radius: 24px;
      border: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.76), rgba(255, 248, 239, 0.92));
    }}
    .focus-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 12px;
    }}
    .focus-grid span, .metric-list span, .band-grid span {{
      color: var(--muted);
    }}
    .focus-grid strong, .metric-list strong, .band-grid strong {{
      font-size: 20px;
    }}
    .band-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 12px;
    }}
    .split {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px;
    }}
    .split article {{
      padding: 14px 16px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.68);
      display: grid;
      gap: 10px;
      align-content: start;
    }}
    .split ul {{
      margin: 0;
      padding-left: 18px;
      color: var(--muted);
      line-height: 1.55;
    }}
    .journal-entry strong {{ display: block; margin-bottom: 6px; }}
    .journal-entry small {{ color: var(--muted); display: block; margin-bottom: 8px; }}
    form {{ display: grid; gap: 10px; }}
    select, input, textarea {{
      width: 100%;
      padding: 12px 14px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.85);
      color: var(--ink);
      font: inherit;
    }}
    textarea {{ min-height: 120px; resize: vertical; }}
    .status {{ min-height: 20px; color: var(--teal); font-size: 14px; }}
    .filter-stack {{ display: grid; gap: 12px; margin-bottom: 14px; }}
    .filter-row {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }}
    .filter-chip {{
      display: inline-flex;
      padding: 8px 12px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.72);
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }}
    .filter-chip.is-active {{
      background: rgba(17, 104, 102, 0.12);
      color: var(--teal);
      border-color: rgba(17, 104, 102, 0.28);
    }}
    .summary-card {{
      display: flex;
      flex-direction: column;
      gap: 6px;
      padding: 14px 16px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.68);
    }}
    .control-summary-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
      gap: 12px;
    }}
    .control-summary-card {{
      padding: 14px 16px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.72);
      display: grid;
      gap: 8px;
      align-content: start;
      min-height: 110px;
    }}
    .control-summary-card label {{
      display: block;
      margin: 0;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 11px;
    }}
    .control-summary-card strong {{
      display: block;
      font-size: 22px;
      line-height: 1.2;
      overflow-wrap: anywhere;
    }}
    .control-summary-card small {{
      color: var(--muted);
      line-height: 1.45;
    }}
    .control-summary-card.is-wide {{
      grid-column: span 2;
    }}
    .metric-bar {{
      padding: 12px 14px;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.68);
    }}
    .metric-bar-head {{
      display: flex;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 8px;
      font-size: 13px;
    }}
    .metric-bar-track {{
      width: 100%;
      height: 10px;
      border-radius: 999px;
      background: rgba(23, 34, 44, 0.08);
      overflow: hidden;
    }}
    .metric-bar-fill {{
      height: 100%;
      border-radius: 999px;
      background: linear-gradient(90deg, var(--navy), var(--teal));
    }}
    .metric-bar-fill.tone-positive {{ background: linear-gradient(90deg, #2f7d5b, #57a36f); }}
    .metric-bar-fill.tone-warning {{ background: linear-gradient(90deg, #b66d1f, #d7953c); }}
    .metric-bar-fill.tone-negative {{ background: linear-gradient(90deg, #b64b3d, #df6d58); }}
    .timeline-item {{
      position: relative;
      padding: 12px 14px 12px 28px;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.68);
    }}
    .timeline-item::before {{
      content: "";
      position: absolute;
      left: 12px;
      top: 18px;
      width: 8px;
      height: 8px;
      border-radius: 999px;
      background: var(--navy);
    }}
    .timeline-item.tone-positive::before {{ background: #2f7d5b; }}
    .timeline-item.tone-warning::before {{ background: #b66d1f; }}
    .timeline-item.tone-negative::before {{ background: #b64b3d; }}
    pre {{
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: Consolas, "Courier New", monospace;
      font-size: 12px;
      color: var(--muted);
    }}
    @keyframes rise {{
      from {{ opacity: 0; transform: translateY(12px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}
    @media (max-width: 980px) {{
      .hero, .layout, .split {{
        grid-template-columns: 1fr;
      }}
      .shell {{ width: min(100% - 16px, 1320px); }}
      .hero {{ padding: 18px; }}
      .control-summary-card.is-wide {{
        grid-column: span 1;
      }}
      .rail-preview-popover {{
        position: static;
      }}
      .signal-preview-popover {{
        position: static;
      }}
    }}
    {sidebar_styles}
  </style>
</head>
<body>
  <div class="page-shell">
  {sidebar}
  <main class="shell">
    <section class="hero">
      <div class="hero-copy">
        <span class="eyebrow">User Workspace | Signals-only</span>
        <h1>What should I do with {escape(snapshot.selected_root)} right now?</h1>
        <p>
          The primary user experience is this browser workspace at <strong>/workspace</strong>.
          Telegram gives the portable brief, and <strong>/dashboard</strong> remains the operations console.
        </p>
        <div class="hero-actions">
          <a class="button primary" href="/api/v1/workspace?root={escape(snapshot.selected_root)}">Open workspace JSON</a>
          <a class="button" href="/workspace/preferences">Preferences</a>
          <a class="button" href="/workspace/delivery-history?root={escape(snapshot.selected_root)}">Delivery history</a>
          <a class="button" href="/dashboard?root={escape(snapshot.selected_root)}">Open ops console</a>
          <a class="button" href="/api/v1/signals?root={escape(snapshot.selected_root)}&status=active">Inspect active signals API</a>
        </div>
      </div>
      <aside class="hero-side">
        <div>
          <h2>Focus signal</h2>
          <p><strong>{escape(focus_header)}</strong></p>
          <small>{escape(focus_summary)}</small>
        </div>
        <div class="hero-kpis">
          <article><span>Primary surface</span><strong>{escape(primary_label)}</strong></article>
          <article><span>Bias</span><strong>{escape(focus_badge)}</strong></article>
          <article><span>Workflow</span><strong>{escape(workflow_label)}</strong></article>
          <article><span>Confidence</span><strong>{escape(confidence)}</strong></article>
          <article><span>Skeptic</span><strong>{escape(skeptic)}</strong></article>
        </div>
        <div class="top-links">
          <a class="button" href="/api/v1/notifications/telegram/preview?root={escape(snapshot.selected_root)}">Telegram JSON</a>
          <a class="button" href="/api/v1/admin/health">Admin health</a>
        </div>
      </aside>
    </section>
    {trust_ribbon}
    <section class="panel">
      <div class="panel-head">
        <h2>Root lane</h2>
        <p>Each card answers whether this root deserves attention now.</p>
      </div>
      <div class="rail">{root_links}</div>
    </section>
    {session_band}
    {market_panel}
    <section class="panel compare-board" data-compare-board>
      <div class="panel-head">
        <div>
          <h2>{escape(compare_copy["title"])}</h2>
          <p>{escape(compare_copy["subtitle"])}</p>
        </div>
        <div class="compare-toolbar">
          <span class="filter-chip is-active" data-compare-status>{escape(compare_copy["status_empty"])}</span>
          <button class="button" type="button" data-compare-clear-all>{escape(compare_copy["clear_all"])}</button>
        </div>
      </div>
      <div class="compare-sections">
        <section class="compare-section" data-compare-root-section data-compare-root>
          <div class="panel-head">
            <div>
              <h3>{escape(compare_copy["root_section_title"])}</h3>
              <p>{escape(compare_copy["root_section_note"])}</p>
            </div>
          </div>
          <div class="compare-grid">
            <article class="compare-card" data-compare-root-slot="a"></article>
            <article class="compare-card" data-compare-root-slot="b"></article>
          </div>
        </section>
        <section class="compare-section" data-compare-signal-section data-compare-signal>
          <div class="panel-head">
            <div>
              <h3>{escape(compare_copy["signal_section_title"])}</h3>
              <p>{escape(compare_copy["signal_section_note"])}</p>
            </div>
          </div>
          <div class="compare-grid">
            <article class="compare-card" data-compare-signal-slot="a"></article>
            <article class="compare-card" data-compare-signal-slot="b"></article>
          </div>
        </section>
      </div>
    </section>
    <section class="layout">
      <div class="stack">
        {watchlist}
        {comparison}
      </div>
      <div class="stack">
        {diff_block}
        {confidence_block}
        {review_bundle}
      </div>
    </section>
    <section class="layout">
      <div class="stack">
        <section class="panel">
          <div class="panel-head">
            <h2>Signal lane</h2>
            <p>Pick the signal you want to review in detail.</p>
          </div>
          <div class="signal-lane">{signal_lane}</div>
        </section>
        <section class="panel">
          <div class="panel-head">
            <h2>Decision pack</h2>
            <p>The minimum context a human needs before acting.</p>
          </div>
          <article class="focus-card">
            <div class="signal-top">
              <div>
                <strong>{escape(focus_header)}</strong>
                <p class="muted">{escape(focus_summary)}</p>
              </div>
              <span class="badge">{escape(focus_badge)}</span>
            </div>
            <div class="focus-grid">
              <article><span>Priority</span><strong>{focus.priority_score if focus is not None else "n/a"}</strong></article>
              <article><span>Freshness</span><strong>{f"{focus.freshness_score:.2f}" if focus is not None else "n/a"}</strong></article>
              <article><span>Roll risk</span><strong>{f"{focus.roll_risk:.2f}" if focus is not None else "n/a"}</strong></article>
              <article><span>Expiry risk</span><strong>{f"{focus.expiry_risk:.2f}" if focus is not None else "n/a"}</strong></article>
            </div>
            {workflow_panel}
            <div class="split">
              <article>
                <h3>Why now</h3>
                <ul>{drivers}</ul>
              </article>
              <article>
                <h3>Pushback</h3>
                <ul>{objections}</ul>
              </article>
              <article>
                <h3>Invalidation</h3>
                <ul>{invalidations}</ul>
              </article>
            </div>
            <div class="hero-actions" style="margin-top:0;">
              <a class="button primary" href="{f'/workspace/signals/{escape(focus.signal_id)}' if focus is not None else '#'}">Open full signal page</a>
              <a class="button" href="{f'/api/v1/signals/{escape(focus.signal_id)}' if focus is not None else '#'}">Open signal JSON</a>
            </div>
          </article>
        </section>
        <section class="panel">
          <div class="panel-head">
            <h2>Visual pulse</h2>
            <p>Compact chart of confidence, risk and recent lifecycle events.</p>
          </div>
          <div class="visual-grid">{visual_bars}</div>
          <div class="timeline-list" style="margin-top:16px;">{visual_timeline}</div>
        </section>
        <section class="panel">
          <div class="panel-head">
            <h2>Journal</h2>
            <p>Capture thesis, risk, execution notes and post-mortems without leaving the page.</p>
          </div>
          <div class="journal-list">{journal_rows}</div>
          <div class="panel-head" style="margin-top:18px;">
            <h2>Quick capture</h2>
            <p>{'Writes straight into the signal journal.' if focus is not None else 'Pick a signal first to enable quick capture.'}</p>
          </div>
          <form id="workspace-journal-form" data-signal-id="{selected_signal_id}">
            <select name="kind" {form_disabled}>
              <option value="thesis">Thesis</option>
              <option value="risk_note">Risk note</option>
              <option value="execution_note">Execution note</option>
              <option value="post_mortem">Post-mortem</option>
              <option value="invalidation_breach">Invalidation breach</option>
              <option value="data_anomaly">Data anomaly</option>
            </select>
            <input type="text" name="title" placeholder="Short title" {form_disabled}>
            <textarea name="note" placeholder="Write what changed, why it matters, and what you will watch next." {form_disabled}></textarea>
            <button class="button primary" type="submit" {form_disabled}>Save journal note</button>
            <div class="status" id="journal-status"></div>
          </form>
        </section>
        {decision_preview}
      </div>
      <div class="stack">
        <section class="panel">
          <div class="panel-head">
            <h2>Action plan</h2>
            <p>What the product thinks the user should do next.</p>
          </div>
          <div class="action-list">{actions}</div>
        </section>
        <section class="panel">
          <div class="panel-head">
            <h2>Telegram brief</h2>
            <p>{'Ready to send.' if snapshot.telegram_delivery_ready else 'Preview available even if delivery is not configured yet.'}</p>
          </div>
          <pre>{telegram_preview}</pre>
        </section>
        <section class="panel">
          <div class="panel-head">
            <h2>Delivery calendar</h2>
            <p>The next scheduled Telegram windows for this workspace.</p>
          </div>
          <div class="list">{delivery_windows}</div>
          <div class="status" id="delivery-action-status"></div>
        </section>
        <section class="panel">
          <div class="panel-head">
            <h2>Delivery activity</h2>
            <p>Recent sends, suppressions and one-shot calendar actions for this root.</p>
          </div>
          {delivery_activity_controls}
          <div class="list">{delivery_activity}</div>
          {delivery_activity_footer}
        </section>
        <section class="panel">
          <div class="panel-head">
            <h2>Evaluation and health</h2>
            <p>Quality and operational context next to the trading idea.</p>
          </div>
          <div class="metric-list">
            <article><span>Resolved signals</span><strong>{snapshot.evaluation.resolved_signals}</strong><p class="muted">Brier {_format_optional(snapshot.evaluation.brier_score)} | log loss {_format_optional(snapshot.evaluation.log_loss)}</p></article>
            <article><span>Platform</span><strong>{escape(snapshot.admin_health.status)}</strong><p class="muted">DB {escape(snapshot.admin_health.database_status)} | active {snapshot.admin_health.active_signals}</p></article>
          </div>
        </section>
        <section class="panel">
          <div class="panel-head">
            <h2>Source quality</h2>
            <p>Provider comparison stays visible to the user, not only to ops.</p>
          </div>
          <div class="metric-list">{quality}</div>
        </section>
        <section class="panel">
          <div class="panel-head">
            <h2>Raw snapshot</h2>
            <p>Useful when you need to inspect the exact payload behind the page.</p>
          </div>
          <pre id="workspace-data">{payload}</pre>
        </section>
      </div>
    </section>
  </main>
  <script>
    const journalForm = document.getElementById("workspace-journal-form");
    const journalStatus = document.getElementById("journal-status");
    const deliveryStatus = document.getElementById("delivery-action-status");
    if (journalForm) {{
      journalForm.addEventListener("submit", async (event) => {{
        event.preventDefault();
        const signalId = journalForm.dataset.signalId;
        if (!signalId) {{
          if (journalStatus) {{
            journalStatus.textContent = "Select a signal first.";
          }}
          return;
        }}
        const formData = new FormData(journalForm);
        const payload = {{
          kind: formData.get("kind"),
          title: formData.get("title"),
          note: formData.get("note"),
          author: "workspace",
        }};
        if (!payload.title || !payload.note) {{
          if (journalStatus) {{
            journalStatus.textContent = "Title and note are required.";
          }}
          return;
        }}
        if (journalStatus) {{
          journalStatus.textContent = "Saving...";
        }}
        const response = await fetch(`/api/v1/journal/${{signalId}}`, {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify(payload),
        }});
        if (!response.ok) {{
          if (journalStatus) {{
            journalStatus.textContent = "Journal save failed.";
          }}
          return;
        }}
        if (journalStatus) {{
          journalStatus.textContent = "Saved. Reloading...";
        }}
        const url = new URL(window.location.href);
        url.searchParams.set("signal_id", signalId);
        await window.__imoexRefreshPage(url.toString());
      }});
    }}
    const rootPreviewMessages = {root_preview_messages};
    const rootPreviewTimeframes = {root_preview_timeframes};
    const rootPreviewCache = new Map();
    const rootPreviewButtons = document.querySelectorAll("[data-root-preview-button]");
    const formatPreviewPrice = (value) => {{
      if (typeof value !== "number" || Number.isNaN(value)) {{
        return "n/a";
      }}
      if (Math.abs(value) >= 1000) {{
        return value.toLocaleString("en-US", {{ minimumFractionDigits: 2, maximumFractionDigits: 2 }}).replace(/,/g, " ");
      }}
      return value.toFixed(2);
    }};
    const formatPreviewPct = (value) => {{
      if (typeof value !== "number" || Number.isNaN(value)) {{
        return "n/a";
      }}
      return `${{value >= 0 ? "+" : ""}}${{(value * 100).toFixed(2)}}%`;
    }};
    const formatPreviewTime = (value) => {{
      if (!value) {{
        return "n/a";
      }}
      try {{
        const stamp = new Date(value);
        if (Number.isNaN(stamp.getTime())) {{
          return "n/a";
        }}
        return `${{stamp.toLocaleString("sv-SE", {{
          timeZone: "Europe/Moscow",
          year: "numeric",
          month: "2-digit",
          day: "2-digit",
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        }})}} MSK`;
      }} catch (_error) {{
        return "n/a";
      }}
    }};
    const escapePreviewText = (value) => String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
    const previewExcerpt = (value, maxLength = 160) => {{
      const text = String(value ?? "");
      if (text.length <= maxLength) {{
        return text;
      }}
      return `${{text.slice(0, Math.max(0, maxLength - 3)).trimEnd()}}...`;
    }};
    const resolvePreviewSeries = (snapshot, timeframe) => {{
      if (!snapshot) {{
        return null;
      }}
      if (timeframe === "1W") {{
        return snapshot.weekly;
      }}
      if (timeframe === "1M") {{
        return snapshot.monthly;
      }}
      return snapshot.daily;
    }};
    const renderRootPreviewChart = (series) => {{
      if (!series || !Array.isArray(series.points) || series.points.length === 0) {{
        return `<div class="empty">${{rootPreviewMessages.unavailable}}</div>`;
      }}
      const width = 248;
      const height = 96;
      const lows = series.points.map((point) => typeof point.low === "number" ? point.low : point.value);
      const highs = series.points.map((point) => typeof point.high === "number" ? point.high : point.value);
      const low = Math.min(...lows);
      const high = Math.max(...highs);
      const span = Math.max(high - low, 0.0001);
      const bodyWidth = Math.max(6, Math.min(16, width / Math.max(series.points.length * 1.9, 1)));
      const mapPriceY = (value) => height - (((value - low) / span) * (height - 16)) - 8;
      const candles = series.points.map((point, index) => {{
        const x = series.points.length === 1 ? width / 2 : (index / (series.points.length - 1)) * width;
        const openValue = typeof point.open === "number" ? point.open : point.value;
        const closeValue = typeof point.close === "number" ? point.close : point.value;
        const highValue = typeof point.high === "number" ? point.high : Math.max(openValue, closeValue);
        const lowValue = typeof point.low === "number" ? point.low : Math.min(openValue, closeValue);
        const openY = mapPriceY(openValue);
        const closeY = mapPriceY(closeValue);
        const highY = mapPriceY(highValue);
        const lowY = mapPriceY(lowValue);
        const bodyTop = Math.min(openY, closeY);
        const bodyHeight = Math.max(Math.abs(closeY - openY), 3);
        const tone = closeValue >= openValue ? "#2f7e57" : "#b44a3d";
        return `<line x1="${{x.toFixed(1)}}" y1="${{highY.toFixed(1)}}" x2="${{x.toFixed(1)}}" y2="${{lowY.toFixed(1)}}" stroke="${{tone}}" stroke-width="1.8" stroke-linecap="round"></line><rect x="${{(x - (bodyWidth / 2)).toFixed(1)}}" y="${{bodyTop.toFixed(1)}}" width="${{bodyWidth.toFixed(1)}}" height="${{bodyHeight.toFixed(1)}}" rx="2" fill="${{tone}}" fill-opacity="0.92"></rect>`;
      }}).join("");
      return `<svg viewBox="0 0 248 96" preserveAspectRatio="none"><line x1="0" y1="${{mapPriceY(series.open_price).toFixed(1)}}" x2="248" y2="${{mapPriceY(series.open_price).toFixed(1)}}" stroke="rgba(21,32,42,0.08)" stroke-width="1" stroke-dasharray="4 4"></line>${{candles}}</svg>`;
    }};
    const setRootPreviewContent = (rootCode, timeframe, snapshot) => {{
      const card = document.querySelector(`[data-root-preview-card][data-root-code="${{rootCode}}"]`);
      if (!card) {{
        return;
      }}
      const popover = card.querySelector("[data-root-preview-popover]");
      const labelNode = card.querySelector("[data-root-preview-label]");
      const updatedNode = card.querySelector("[data-root-preview-updated]");
      const chartNode = card.querySelector("[data-root-preview-chart]");
      const metaNode = card.querySelector("[data-root-preview-meta]");
      const series = resolvePreviewSeries(snapshot, timeframe);
      if (!popover || !labelNode || !updatedNode || !chartNode || !metaNode || !series) {{
        return;
      }}
      for (const button of card.querySelectorAll("[data-root-preview-button]")) {{
        button.classList.toggle("is-active", button.dataset.timeframe === timeframe);
      }}
      labelNode.textContent = `${{rootPreviewTimeframes[timeframe] || timeframe}} · ${{timeframe}}`;
      updatedNode.textContent = `${{rootPreviewMessages.updated}} ${{
        formatPreviewTime(snapshot.as_of)
      }} | ${{
        snapshot.status || "n/a"
      }}`;
      chartNode.innerHTML = renderRootPreviewChart(series);
      metaNode.innerHTML = `<span>${{rootPreviewMessages.last}} ${{
        formatPreviewPrice(snapshot.current_price)
      }}${{
        snapshot.unit ? ` ${{snapshot.unit}}` : ""
      }}</span><span>${{rootPreviewMessages.open}} ${{
        formatPreviewPrice(series.open_price)
      }} | ${{rootPreviewMessages.change}} ${{
        formatPreviewPct(series.change_pct)
      }}</span><span>${{rootPreviewMessages.range}} ${{
        formatPreviewPrice(series.low_price)
      }} - ${{
        formatPreviewPrice(series.high_price)
      }}</span>`;
      for (const pinButton of card.querySelectorAll("[data-pin-root-preview]")) {{
        pinButton.dataset.timeframe = timeframe;
      }}
      syncRootPinButtons();
      popover.hidden = false;
    }};
    const setRootPreviewMessage = (rootCode, timeframe, message) => {{
      const card = document.querySelector(`[data-root-preview-card][data-root-code="${{rootCode}}"]`);
      if (!card) {{
        return;
      }}
      const popover = card.querySelector("[data-root-preview-popover]");
      const labelNode = card.querySelector("[data-root-preview-label]");
      const updatedNode = card.querySelector("[data-root-preview-updated]");
      const chartNode = card.querySelector("[data-root-preview-chart]");
      const metaNode = card.querySelector("[data-root-preview-meta]");
      if (!popover || !labelNode || !updatedNode || !chartNode || !metaNode) {{
        return;
      }}
      for (const button of card.querySelectorAll("[data-root-preview-button]")) {{
        button.classList.toggle("is-active", button.dataset.timeframe === timeframe);
      }}
      labelNode.textContent = `${{rootPreviewTimeframes[timeframe] || timeframe}} · ${{timeframe}}`;
      updatedNode.textContent = message;
      chartNode.innerHTML = `<div class="empty">${{message}}</div>`;
      metaNode.textContent = rootPreviewMessages.pick;
      for (const pinButton of card.querySelectorAll("[data-pin-root-preview]")) {{
        pinButton.dataset.timeframe = timeframe;
      }}
      syncRootPinButtons();
      popover.hidden = false;
    }};
    const hideRootPreviews = (keepRootCode = null) => {{
      for (const popover of document.querySelectorAll("[data-root-preview-popover]")) {{
        if (keepRootCode && popover.dataset.rootCode === keepRootCode) {{
          continue;
        }}
        popover.hidden = true;
      }}
    }};
    const fetchRootPreviewSnapshot = async (rootCode) => {{
      if (rootPreviewCache.has(rootCode)) {{
        return rootPreviewCache.get(rootCode);
      }}
      const response = await fetch(`/api/v1/workspace/market-preview?root=${{encodeURIComponent(rootCode)}}`);
      if (!response.ok) {{
        throw new Error("preview request failed");
      }}
      const payload = await response.json();
      if (!payload) {{
        throw new Error("preview payload missing");
      }}
      rootPreviewCache.set(rootCode, payload);
      return payload;
    }};
    const openRootPreview = async (rootCode, timeframe) => {{
      hideRootPreviews(rootCode);
      if (rootPreviewCache.has(rootCode)) {{
        setRootPreviewContent(rootCode, timeframe, rootPreviewCache.get(rootCode));
        return;
      }}
      setRootPreviewMessage(rootCode, timeframe, rootPreviewMessages.loading);
      try {{
        const payload = await fetchRootPreviewSnapshot(rootCode);
        setRootPreviewContent(rootCode, timeframe, payload);
      }} catch (_error) {{
        setRootPreviewMessage(rootCode, timeframe, rootPreviewMessages.unavailable);
      }}
    }};
    for (const button of rootPreviewButtons) {{
      button.addEventListener("click", async (event) => {{
        event.preventDefault();
        event.stopPropagation();
        const rootCode = button.dataset.rootCode;
        const timeframe = button.dataset.timeframe || "1D";
        if (!rootCode) {{
          return;
        }}
        const card = document.querySelector(`[data-root-preview-card][data-root-code="${{rootCode}}"]`);
        const popover = card ? card.querySelector("[data-root-preview-popover]") : null;
        const alreadyOpen = popover && !popover.hidden && button.classList.contains("is-active");
        if (alreadyOpen) {{
          popover.hidden = true;
          return;
        }}
        await openRootPreview(rootCode, timeframe);
      }});
    }}
    const signalPreviewMessages = {signal_preview_messages};
    const signalPreviewCache = new Map();
    const signalPreviewButtons = document.querySelectorAll("[data-signal-preview-button]");
    const compareMessages = {compare_messages};
    const compareStorageKey = "imoex-workspace-compare-state";
    const compareSlots = ["a", "b"];
    const compareBoard = document.querySelector("[data-compare-board]");
    const compareRootNodes = {{
      a: document.querySelector('[data-compare-root-slot="a"]'),
      b: document.querySelector('[data-compare-root-slot="b"]'),
    }};
    const compareSignalNodes = {{
      a: document.querySelector('[data-compare-signal-slot="a"]'),
      b: document.querySelector('[data-compare-signal-slot="b"]'),
    }};
    const compareStatusNode = document.querySelector("[data-compare-status]");
    const compareClearAllButton = document.querySelector("[data-compare-clear-all]");
    const compareState = {{
      roots: {{ a: null, b: null }},
      signals: {{ a: null, b: null }},
    }};
    const setSignalPreviewMessage = (signalId, timeframe, message) => {{
      const card = document.querySelector(`[data-signal-preview-card][data-signal-id="${{signalId}}"]`);
      if (!card) {{
        return;
      }}
      const popover = card.querySelector("[data-signal-preview-popover]");
      const labelNode = card.querySelector("[data-signal-preview-label]");
      const updatedNode = card.querySelector("[data-signal-preview-updated]");
      const chartNode = card.querySelector("[data-signal-preview-chart]");
      const gridNode = card.querySelector("[data-signal-preview-grid]");
      const summaryNode = card.querySelector("[data-signal-preview-summary]");
      if (!popover || !labelNode || !updatedNode || !chartNode || !gridNode || !summaryNode) {{
        return;
      }}
      for (const button of card.querySelectorAll("[data-signal-preview-button]")) {{
        button.classList.toggle("is-active", button.dataset.timeframe === timeframe);
      }}
      labelNode.textContent = `${{rootPreviewTimeframes[timeframe] || timeframe}} · ${{timeframe}}`;
      updatedNode.textContent = message;
      chartNode.innerHTML = `<div class="empty">${{escapePreviewText(message)}}</div>`;
      gridNode.innerHTML = "";
      summaryNode.textContent = signalPreviewMessages.unavailable;
      for (const pinButton of card.querySelectorAll("[data-pin-signal-preview]")) {{
        pinButton.dataset.timeframe = timeframe;
      }}
      syncSignalPinButtons();
      popover.hidden = false;
    }};
    const setSignalPreviewContent = (signalId, timeframe, snapshot) => {{
      const card = document.querySelector(`[data-signal-preview-card][data-signal-id="${{signalId}}"]`);
      if (!card) {{
        return;
      }}
      const popover = card.querySelector("[data-signal-preview-popover]");
      const labelNode = card.querySelector("[data-signal-preview-label]");
      const updatedNode = card.querySelector("[data-signal-preview-updated]");
      const chartNode = card.querySelector("[data-signal-preview-chart]");
      const gridNode = card.querySelector("[data-signal-preview-grid]");
      const summaryNode = card.querySelector("[data-signal-preview-summary]");
      if (!popover || !labelNode || !updatedNode || !chartNode || !gridNode || !summaryNode) {{
        return;
      }}
      const signal = snapshot && snapshot.signal ? snapshot.signal : null;
      const marketSnapshot = snapshot && snapshot.market_snapshot ? snapshot.market_snapshot : null;
      const series = resolvePreviewSeries(marketSnapshot, timeframe);
      const diffSummary = snapshot && snapshot.signal_diff && snapshot.signal_diff.summary
        ? snapshot.signal_diff.summary
        : signalPreviewMessages.none;
      const latestEvent = snapshot && Array.isArray(snapshot.decision_log) && snapshot.decision_log.length > 0
        ? `${{snapshot.decision_log[0].title}} | ${{previewExcerpt(snapshot.decision_log[0].detail, 120)}}`
        : signalPreviewMessages.none;
      for (const button of card.querySelectorAll("[data-signal-preview-button]")) {{
        button.classList.toggle("is-active", button.dataset.timeframe === timeframe);
      }}
      labelNode.textContent = `${{rootPreviewTimeframes[timeframe] || timeframe}} · ${{timeframe}}`;
      updatedNode.textContent = marketSnapshot
        ? `${{signalPreviewMessages.updated}} ${{formatPreviewTime(marketSnapshot.as_of)}}`
        : signalPreviewMessages.unavailable;
      chartNode.innerHTML = series
        ? renderRootPreviewChart(series)
        : `<div class="empty">${{escapePreviewText(signalPreviewMessages.unavailable)}}</div>`;
      gridNode.innerHTML = [
        `<article><span>${{escapePreviewText(signalPreviewMessages.confidence)}}</span><strong>${{signal && typeof signal.confidence_final === "number" ? signal.confidence_final.toFixed(2) : "n/a"}}</strong></article>`,
        `<article><span>${{escapePreviewText(signalPreviewMessages.skeptic)}}</span><strong>${{signal && typeof signal.skeptic_score === "number" ? signal.skeptic_score.toFixed(2) : "n/a"}}</strong></article>`,
        `<article><span>${{escapePreviewText(signalPreviewMessages.priority)}}</span><strong>${{signal && signal.priority_score !== undefined ? escapePreviewText(signal.priority_score) : "n/a"}}</strong></article>`,
        `<article><span>${{escapePreviewText(signalPreviewMessages.price)}}</span><strong>${{marketSnapshot ? `${{formatPreviewPrice(marketSnapshot.current_price)}}${{marketSnapshot.unit ? ` ${{escapePreviewText(marketSnapshot.unit)}}` : ""}}` : "n/a"}}</strong></article>`,
      ].join("");
      summaryNode.innerHTML = `<strong>${{
        escapePreviewText(signal ? `${{signal.direction_final}} | ${{signal.horizon}} | ${{signal.workflow_state}}` : signalPreviewMessages.none)
      }}</strong><p>${{
        escapePreviewText(previewExcerpt(signal && signal.summary ? signal.summary : signalPreviewMessages.none, 180))
      }}</p><p><strong>${{escapePreviewText(signalPreviewMessages.diff)}}:</strong> ${{
        escapePreviewText(previewExcerpt(diffSummary, 180))
      }}</p><p><strong>${{escapePreviewText(signalPreviewMessages.timeline)}}:</strong> ${{
        escapePreviewText(latestEvent)
      }}</p>`;
      for (const pinButton of card.querySelectorAll("[data-pin-signal-preview]")) {{
        pinButton.dataset.timeframe = timeframe;
      }}
      syncSignalPinButtons();
      popover.hidden = false;
    }};
    const hideSignalPreviews = (keepSignalId = null) => {{
      for (const popover of document.querySelectorAll("[data-signal-preview-popover]")) {{
        if (keepSignalId && popover.dataset.signalId === keepSignalId) {{
          continue;
        }}
        popover.hidden = true;
      }}
    }};
    const fetchSignalPreviewSnapshot = async (signalId) => {{
      if (signalPreviewCache.has(signalId)) {{
        return signalPreviewCache.get(signalId);
      }}
      const response = await fetch(`/api/v1/workspace/signals/${{encodeURIComponent(signalId)}}`);
      if (!response.ok) {{
        throw new Error("signal preview request failed");
      }}
      const payload = await response.json();
      if (!payload) {{
        throw new Error("signal preview payload missing");
      }}
      signalPreviewCache.set(signalId, payload);
      return payload;
    }};
    const openSignalPreview = async (signalId, timeframe) => {{
      hideSignalPreviews(signalId);
      if (signalPreviewCache.has(signalId)) {{
        setSignalPreviewContent(signalId, timeframe, signalPreviewCache.get(signalId));
        return;
      }}
      setSignalPreviewMessage(signalId, timeframe, signalPreviewMessages.loading);
      try {{
        const payload = await fetchSignalPreviewSnapshot(signalId);
        setSignalPreviewContent(signalId, timeframe, payload);
      }} catch (_error) {{
        setSignalPreviewMessage(signalId, timeframe, signalPreviewMessages.unavailable);
      }}
    }};
    for (const button of signalPreviewButtons) {{
      button.addEventListener("click", async (event) => {{
        event.preventDefault();
        event.stopPropagation();
        const signalId = button.dataset.signalId;
        const timeframe = button.dataset.timeframe || "1D";
        if (!signalId) {{
          return;
        }}
        const card = document.querySelector(`[data-signal-preview-card][data-signal-id="${{signalId}}"]`);
        const popover = card ? card.querySelector("[data-signal-preview-popover]") : null;
        const alreadyOpen = popover && !popover.hidden && button.classList.contains("is-active");
        if (alreadyOpen) {{
          popover.hidden = true;
          return;
        }}
        await openSignalPreview(signalId, timeframe);
      }});
    }}
    const normalizeCompareTimeframe = (value) => rootPreviewTimeframes[value] ? value : "1D";
    const normalizeCompareSlot = (value) => compareSlots.includes(String(value || "").toLowerCase())
      ? String(value).toLowerCase()
      : "a";
    const slotTitle = (kind, slot) => `${{kind === "root" ? compareMessages.root_slot : compareMessages.signal_slot}} ${{slot.toUpperCase()}}`;
    const serializeCompareCollection = (collection, idKey) => {{
      const payload = {{}};
      for (const slot of compareSlots) {{
        const entry = collection[slot];
        payload[slot] = entry
          ? {{
              [idKey]: entry[idKey],
              timeframe: normalizeCompareTimeframe(entry.timeframe),
            }}
          : null;
      }}
      return payload;
    }};
    const readCompareCollection = (parsedCollection, legacyEntry, idKey) => {{
      const collection = {{ a: null, b: null }};
      if (parsedCollection && typeof parsedCollection === "object") {{
        for (const slot of compareSlots) {{
          const entry = parsedCollection[slot];
          if (entry && entry[idKey]) {{
            collection[slot] = {{
              [idKey]: String(entry[idKey]),
              timeframe: normalizeCompareTimeframe(entry.timeframe),
              unavailable: false,
            }};
          }}
        }}
      }} else if (legacyEntry && legacyEntry[idKey]) {{
        collection.a = {{
          [idKey]: String(legacyEntry[idKey]),
          timeframe: normalizeCompareTimeframe(legacyEntry.timeframe),
          unavailable: false,
        }};
      }}
      return collection;
    }};
    const persistCompareState = () => {{
      try {{
        const payload = {{
          roots: serializeCompareCollection(compareState.roots, "rootCode"),
          signals: serializeCompareCollection(compareState.signals, "signalId"),
        }};
        window.localStorage.setItem(compareStorageKey, JSON.stringify(payload));
      }} catch (_error) {{
      }}
    }};
    const restoreCompareState = () => {{
      try {{
        const raw = window.localStorage.getItem(compareStorageKey);
        if (!raw) {{
          return;
        }}
        const parsed = JSON.parse(raw);
        const restoredRoots = readCompareCollection(parsed && parsed.roots, parsed && parsed.root, "rootCode");
        const restoredSignals = readCompareCollection(parsed && parsed.signals, parsed && parsed.signal, "signalId");
        for (const slot of compareSlots) {{
          compareState.roots[slot] = restoredRoots[slot];
          compareState.signals[slot] = restoredSignals[slot];
        }}
      }} catch (_error) {{
      }}
    }};
    const syncRootPinButtons = () => {{
      for (const button of document.querySelectorAll("[data-pin-root-preview]")) {{
        const slot = normalizeCompareSlot(button.dataset.compareSlot);
        const timeframe = normalizeCompareTimeframe(button.dataset.timeframe);
        const entry = compareState.roots[slot];
        const isActive = Boolean(
          entry
          && entry.rootCode === button.dataset.rootCode
          && entry.timeframe === timeframe
        );
        button.classList.toggle("is-active", isActive);
        button.setAttribute("aria-pressed", isActive ? "true" : "false");
      }}
    }};
    const syncSignalPinButtons = () => {{
      for (const button of document.querySelectorAll("[data-pin-signal-preview]")) {{
        const slot = normalizeCompareSlot(button.dataset.compareSlot);
        const timeframe = normalizeCompareTimeframe(button.dataset.timeframe);
        const entry = compareState.signals[slot];
        const isActive = Boolean(
          entry
          && entry.signalId === button.dataset.signalId
          && entry.timeframe === timeframe
        );
        button.classList.toggle("is-active", isActive);
        button.setAttribute("aria-pressed", isActive ? "true" : "false");
      }}
    }};
    const buildCompareTabs = (kind, slot, activeTimeframe) => {{
      const buttonClass = kind === "root" ? "rail-preview-button" : "signal-preview-button";
      return ["1D", "1W", "1M"].map((timeframe) => {{
        const activeClass = timeframe === activeTimeframe ? " is-active" : "";
        return `<button class="${{buttonClass}}${{activeClass}}" type="button" data-compare-timeframe data-compare-kind="${{kind}}" data-compare-slot="${{slot}}" data-timeframe="${{timeframe}}">${{timeframe}}</button>`;
      }}).join("");
    }};
    const renderCompareStatus = () => {{
      if (!compareStatusNode) {{
        return;
      }}
      const rootCount = compareSlots.filter((slot) => Boolean(compareState.roots[slot])).length;
      const signalCount = compareSlots.filter((slot) => Boolean(compareState.signals[slot])).length;
      compareStatusNode.textContent = rootCount === 0 && signalCount === 0
        ? compareMessages.status_empty
        : `${{compareMessages.root_slot}}: ${{rootCount}}/2 | ${{compareMessages.signal_slot}}: ${{signalCount}}/2`;
      return;
      const parts = [];
      if (compareState.root) {{
        parts.push(`${{compareMessages.root_slot}}: ${{compareState.root.rootCode}} · ${{compareState.root.timeframe}}`);
      }}
      if (compareState.signal) {{
        const cachedSignal = signalPreviewCache.get(compareState.signal.signalId);
        const signalLabel = cachedSignal && cachedSignal.signal
          ? `${{cachedSignal.signal.root}} · ${{cachedSignal.signal.horizon}}`
          : compareState.signal.signalId;
        parts.push(`${{compareMessages.signal_slot}}: ${{signalLabel}} · ${{compareState.signal.timeframe}}`);
      }}
      compareStatusNode.textContent = parts.length ? parts.join(" | ") : compareMessages.status_empty;
    }};
    const renderCompareRootCard = (slot) => {{
      const node = compareRootNodes[slot];
      if (!node) {{
        return;
      }}
      {{
      const entry = compareState.roots[slot];
      const label = slotTitle("root", slot);
      if (!entry) {{
        node.innerHTML = `<div class="compare-card-head"><div><strong>${{escapePreviewText(label)}}</strong><p>${{escapePreviewText(compareMessages.empty_root)}}</p></div></div><div class="compare-empty">${{escapePreviewText(compareMessages.empty_root)}}</div>`;
        return;
      }}
      const snapshot = rootPreviewCache.get(entry.rootCode);
      const actions = `<div class="compare-card-actions"><button class="preview-pin-button" type="button" data-compare-clear-kind="root" data-compare-slot="${{slot}}">${{escapePreviewText(compareMessages.clear)}}</button><a class="rail-open-link" href="/workspace?root=${{encodeURIComponent(entry.rootCode)}}">${{escapePreviewText(compareMessages.open)}}</a></div>`;
      if (!snapshot) {{
        const statusText = entry.unavailable ? rootPreviewMessages.unavailable : compareMessages.loading;
        node.innerHTML = `<div class="compare-card-head"><div><strong>${{escapePreviewText(label)}}</strong><p>${{escapePreviewText(entry.rootCode)}}</p></div>${{actions}}</div><div class="compare-tabs">${{buildCompareTabs("root", slot, entry.timeframe)}}</div><div class="compare-empty">${{escapePreviewText(statusText)}}</div>`;
        return;
      }}
      const series = resolvePreviewSeries(snapshot, entry.timeframe);
      const subtitle = `${{compareMessages.updated}} ${{formatPreviewTime(snapshot.as_of)}} | ${{snapshot.status || "n/a"}}`;
      node.innerHTML = `<div class="compare-card-head"><div><strong>${{escapePreviewText(label)}} · ${{escapePreviewText(snapshot.root_code || entry.rootCode)}}</strong><p>${{escapePreviewText(subtitle)}}</p></div>${{actions}}</div><div class="compare-tabs">${{buildCompareTabs("root", slot, entry.timeframe)}}</div><div class="compare-chart">${{series ? renderRootPreviewChart(series) : `<div class="empty">${{escapePreviewText(rootPreviewMessages.unavailable)}}</div>`}}</div><div class="compare-meta"><article><span>${{escapePreviewText(compareMessages.last)}}</span><strong>${{formatPreviewPrice(snapshot.current_price)}}${{snapshot.unit ? ` ${{escapePreviewText(snapshot.unit)}}` : ""}}</strong></article><article><span>${{escapePreviewText(compareMessages.open_label)}}</span><strong>${{series ? formatPreviewPrice(series.open_price) : "n/a"}}</strong></article><article><span>${{escapePreviewText(compareMessages.change)}}</span><strong>${{series ? formatPreviewPct(series.change_pct) : "n/a"}}</strong></article><article><span>${{escapePreviewText(compareMessages.range)}}</span><strong>${{series ? `${{formatPreviewPrice(series.low_price)}} - ${{formatPreviewPrice(series.high_price)}}` : "n/a"}}</strong></article></div><div class="compare-summary"><strong>${{escapePreviewText(snapshot.contract || entry.rootCode)}}</strong><p>${{escapePreviewText(snapshot.source_note || snapshot.status_detail || compareMessages.root_slot)}}</p></div>`;
      return;
      }}
      if (!compareState.root) {{
        compareRootNode.innerHTML = `<div class="compare-card-head"><div><strong>${{escapePreviewText(compareMessages.root_slot)}}</strong><p>${{escapePreviewText(compareMessages.empty_root)}}</p></div></div><div class="compare-empty">${{escapePreviewText(compareMessages.empty_root)}}</div>`;
        return;
      }}
      const entry = compareState.root;
      const snapshot = rootPreviewCache.get(entry.rootCode);
      const actions = `<div class="compare-card-actions"><button class="preview-pin-button" type="button" data-compare-clear="root">${{escapePreviewText(compareMessages.clear)}}</button><a class="rail-open-link" href="/workspace?root=${{encodeURIComponent(entry.rootCode)}}">${{escapePreviewText(compareMessages.open)}}</a></div>`;
      if (!snapshot) {{
        const statusText = entry.unavailable ? rootPreviewMessages.unavailable : compareMessages.loading;
        compareRootNode.innerHTML = `<div class="compare-card-head"><div><strong>${{escapePreviewText(entry.rootCode)}}</strong><p>${{escapePreviewText(compareMessages.root_slot)}}</p></div>${{actions}}</div><div class="compare-tabs">${{buildCompareTabs("root", "root-code", entry.rootCode, entry.timeframe)}}</div><div class="compare-empty">${{escapePreviewText(statusText)}}</div>`;
        return;
      }}
      const series = resolvePreviewSeries(snapshot, entry.timeframe);
      const subtitle = `${{compareMessages.updated}} ${{formatPreviewTime(snapshot.as_of)}} | ${{snapshot.status || "n/a"}}`;
      compareRootNode.innerHTML = `<div class="compare-card-head"><div><strong>${{escapePreviewText(snapshot.root_code || entry.rootCode)}} · ${{escapePreviewText(rootPreviewTimeframes[entry.timeframe] || entry.timeframe)}}</strong><p>${{escapePreviewText(subtitle)}}</p></div>${{actions}}</div><div class="compare-tabs">${{buildCompareTabs("root", "root-code", entry.rootCode, entry.timeframe)}}</div><div class="compare-chart">${{series ? renderRootPreviewChart(series) : `<div class="empty">${{escapePreviewText(rootPreviewMessages.unavailable)}}</div>`}}</div><div class="compare-meta"><article><span>${{escapePreviewText(compareMessages.last)}}</span><strong>${{formatPreviewPrice(snapshot.current_price)}}${{snapshot.unit ? ` ${{escapePreviewText(snapshot.unit)}}` : ""}}</strong></article><article><span>${{escapePreviewText(compareMessages.open_label)}}</span><strong>${{series ? formatPreviewPrice(series.open_price) : "n/a"}}</strong></article><article><span>${{escapePreviewText(compareMessages.change)}}</span><strong>${{series ? formatPreviewPct(series.change_pct) : "n/a"}}</strong></article><article><span>${{escapePreviewText(compareMessages.range)}}</span><strong>${{series ? `${{formatPreviewPrice(series.low_price)}} - ${{formatPreviewPrice(series.high_price)}}` : "n/a"}}</strong></article></div><div class="compare-summary"><strong>${{escapePreviewText(snapshot.contract || entry.rootCode)}}</strong><p>${{escapePreviewText(snapshot.source_note || snapshot.status_detail || compareMessages.root_slot)}}</p></div>`;
    }};
    const renderCompareSignalCard = (slot) => {{
      const node = compareSignalNodes[slot];
      if (!node) {{
        return;
      }}
      {{
      const entry = compareState.signals[slot];
      const label = slotTitle("signal", slot);
      if (!entry) {{
        node.innerHTML = `<div class="compare-card-head"><div><strong>${{escapePreviewText(label)}}</strong><p>${{escapePreviewText(compareMessages.empty_signal)}}</p></div></div><div class="compare-empty">${{escapePreviewText(compareMessages.empty_signal)}}</div>`;
        return;
      }}
      const snapshot = signalPreviewCache.get(entry.signalId);
      const actions = `<div class="compare-card-actions"><button class="preview-pin-button" type="button" data-compare-clear-kind="signal" data-compare-slot="${{slot}}">${{escapePreviewText(compareMessages.clear)}}</button><a class="rail-open-link" href="/workspace/signals/${{encodeURIComponent(entry.signalId)}}">${{escapePreviewText(compareMessages.open)}}</a></div>`;
      if (!snapshot) {{
        const statusText = entry.unavailable ? signalPreviewMessages.unavailable : compareMessages.loading;
        node.innerHTML = `<div class="compare-card-head"><div><strong>${{escapePreviewText(label)}}</strong><p>${{escapePreviewText(entry.signalId)}}</p></div>${{actions}}</div><div class="compare-tabs">${{buildCompareTabs("signal", slot, entry.timeframe)}}</div><div class="compare-empty">${{escapePreviewText(statusText)}}</div>`;
        return;
      }}
      const signal = snapshot.signal || null;
      const marketSnapshot = snapshot.market_snapshot || null;
      const series = resolvePreviewSeries(marketSnapshot, entry.timeframe);
      const diffSummary = snapshot.signal_diff && snapshot.signal_diff.summary ? snapshot.signal_diff.summary : signalPreviewMessages.none;
      const latestEvent = Array.isArray(snapshot.decision_log) && snapshot.decision_log.length > 0
        ? `${{snapshot.decision_log[0].title}} | ${{previewExcerpt(snapshot.decision_log[0].detail, 120)}}`
        : signalPreviewMessages.none;
      const subtitle = signal
        ? `${{signal.direction_final}} | ${{signal.horizon}} | ${{signal.workflow_state}}`
        : compareMessages.signal_slot;
      node.innerHTML = `<div class="compare-card-head"><div><strong>${{escapePreviewText(label)}} · ${{escapePreviewText(signal ? `${{signal.root}} | ${{signal.contract}}` : entry.signalId)}}</strong><p>${{escapePreviewText(subtitle)}}</p></div>${{actions}}</div><div class="compare-tabs">${{buildCompareTabs("signal", slot, entry.timeframe)}}</div><div class="compare-chart">${{series ? renderRootPreviewChart(series) : `<div class="empty">${{escapePreviewText(signalPreviewMessages.unavailable)}}</div>`}}</div><div class="compare-meta"><article><span>${{escapePreviewText(compareMessages.confidence)}}</span><strong>${{signal && typeof signal.confidence_final === "number" ? signal.confidence_final.toFixed(2) : "n/a"}}</strong></article><article><span>${{escapePreviewText(compareMessages.skeptic)}}</span><strong>${{signal && typeof signal.skeptic_score === "number" ? signal.skeptic_score.toFixed(2) : "n/a"}}</strong></article><article><span>${{escapePreviewText(compareMessages.priority)}}</span><strong>${{signal && signal.priority_score !== undefined ? escapePreviewText(signal.priority_score) : "n/a"}}</strong></article><article><span>${{escapePreviewText(compareMessages.price)}}</span><strong>${{marketSnapshot ? `${{formatPreviewPrice(marketSnapshot.current_price)}}${{marketSnapshot.unit ? ` ${{escapePreviewText(marketSnapshot.unit)}}` : ""}}` : "n/a"}}</strong></article></div><div class="compare-summary"><strong>${{escapePreviewText(previewExcerpt(signal && signal.summary ? signal.summary : signalPreviewMessages.none, 180))}}</strong><p><strong>${{escapePreviewText(compareMessages.diff)}}:</strong> ${{escapePreviewText(previewExcerpt(diffSummary, 180))}}</p><p><strong>${{escapePreviewText(compareMessages.timeline)}}:</strong> ${{escapePreviewText(latestEvent)}}</p></div>`;
      return;
      }}
      if (!compareState.signal) {{
        compareSignalNode.innerHTML = `<div class="compare-card-head"><div><strong>${{escapePreviewText(compareMessages.signal_slot)}}</strong><p>${{escapePreviewText(compareMessages.empty_signal)}}</p></div></div><div class="compare-empty">${{escapePreviewText(compareMessages.empty_signal)}}</div>`;
        return;
      }}
      const entry = compareState.signal;
      const snapshot = signalPreviewCache.get(entry.signalId);
      const actions = `<div class="compare-card-actions"><button class="preview-pin-button" type="button" data-compare-clear="signal">${{escapePreviewText(compareMessages.clear)}}</button><a class="rail-open-link" href="/workspace/signals/${{encodeURIComponent(entry.signalId)}}">${{escapePreviewText(compareMessages.open)}}</a></div>`;
      if (!snapshot) {{
        const statusText = entry.unavailable ? signalPreviewMessages.unavailable : compareMessages.loading;
        compareSignalNode.innerHTML = `<div class="compare-card-head"><div><strong>${{escapePreviewText(entry.signalId)}}</strong><p>${{escapePreviewText(compareMessages.signal_slot)}}</p></div>${{actions}}</div><div class="compare-tabs">${{buildCompareTabs("signal", "signal-id", entry.signalId, entry.timeframe)}}</div><div class="compare-empty">${{escapePreviewText(statusText)}}</div>`;
        return;
      }}
      const signal = snapshot.signal || null;
      const marketSnapshot = snapshot.market_snapshot || null;
      const series = resolvePreviewSeries(marketSnapshot, entry.timeframe);
      const diffSummary = snapshot.signal_diff && snapshot.signal_diff.summary ? snapshot.signal_diff.summary : signalPreviewMessages.none;
      const latestEvent = Array.isArray(snapshot.decision_log) && snapshot.decision_log.length > 0
        ? `${{snapshot.decision_log[0].title}} | ${{previewExcerpt(snapshot.decision_log[0].detail, 120)}}`
        : signalPreviewMessages.none;
      const subtitle = signal
        ? `${{signal.direction_final}} | ${{signal.horizon}} | ${{signal.workflow_state}}`
        : compareMessages.signal_slot;
      compareSignalNode.innerHTML = `<div class="compare-card-head"><div><strong>${{escapePreviewText(signal ? `${{signal.root}} | ${{signal.contract}}` : entry.signalId)}}</strong><p>${{escapePreviewText(subtitle)}}</p></div>${{actions}}</div><div class="compare-tabs">${{buildCompareTabs("signal", "signal-id", entry.signalId, entry.timeframe)}}</div><div class="compare-chart">${{series ? renderRootPreviewChart(series) : `<div class="empty">${{escapePreviewText(signalPreviewMessages.unavailable)}}</div>`}}</div><div class="compare-meta"><article><span>${{escapePreviewText(compareMessages.confidence)}}</span><strong>${{signal && typeof signal.confidence_final === "number" ? signal.confidence_final.toFixed(2) : "n/a"}}</strong></article><article><span>${{escapePreviewText(compareMessages.skeptic)}}</span><strong>${{signal && typeof signal.skeptic_score === "number" ? signal.skeptic_score.toFixed(2) : "n/a"}}</strong></article><article><span>${{escapePreviewText(compareMessages.priority)}}</span><strong>${{signal && signal.priority_score !== undefined ? escapePreviewText(signal.priority_score) : "n/a"}}</strong></article><article><span>${{escapePreviewText(compareMessages.price)}}</span><strong>${{marketSnapshot ? `${{formatPreviewPrice(marketSnapshot.current_price)}}${{marketSnapshot.unit ? ` ${{escapePreviewText(marketSnapshot.unit)}}` : ""}}` : "n/a"}}</strong></article></div><div class="compare-summary"><strong>${{escapePreviewText(previewExcerpt(signal && signal.summary ? signal.summary : signalPreviewMessages.none, 180))}}</strong><p><strong>${{escapePreviewText(compareMessages.diff)}}:</strong> ${{escapePreviewText(previewExcerpt(diffSummary, 180))}}</p><p><strong>${{escapePreviewText(compareMessages.timeline)}}:</strong> ${{escapePreviewText(latestEvent)}}</p></div>`;
    }};
    const renderCompareBoard = () => {{
      renderCompareStatus();
      for (const slot of compareSlots) {{
        renderCompareRootCard(slot);
        renderCompareSignalCard(slot);
      }}
      syncRootPinButtons();
      syncSignalPinButtons();
      return;
    }};
    const pinRootPreview = async (rootCode, timeframe, slot) => {{
      const resolvedSlot = normalizeCompareSlot(slot);
      const resolvedTimeframe = normalizeCompareTimeframe(timeframe);
      const current = compareState.roots[resolvedSlot];
      if (current && current.rootCode === rootCode && current.timeframe === resolvedTimeframe) {{
        compareState.roots[resolvedSlot] = null;
        persistCompareState();
        renderCompareBoard();
        return;
      }}
      compareState.roots[resolvedSlot] = {{
        rootCode,
        timeframe: resolvedTimeframe,
        unavailable: false,
      }};
      persistCompareState();
      renderCompareBoard();
      try {{
        await fetchRootPreviewSnapshot(rootCode);
        if (
          compareState.roots[resolvedSlot]
          && compareState.roots[resolvedSlot].rootCode === rootCode
          && compareState.roots[resolvedSlot].timeframe === resolvedTimeframe
        ) {{
          compareState.roots[resolvedSlot].unavailable = false;
        }}
      }} catch (_error) {{
        if (
          compareState.roots[resolvedSlot]
          && compareState.roots[resolvedSlot].rootCode === rootCode
          && compareState.roots[resolvedSlot].timeframe === resolvedTimeframe
        ) {{
          compareState.roots[resolvedSlot].unavailable = true;
        }}
      }}
      renderCompareBoard();
      return;
    }};
    const pinSignalPreview = async (signalId, timeframe, slot) => {{
      const resolvedSlot = normalizeCompareSlot(slot);
      const resolvedTimeframe = normalizeCompareTimeframe(timeframe);
      const current = compareState.signals[resolvedSlot];
      if (current && current.signalId === signalId && current.timeframe === resolvedTimeframe) {{
        compareState.signals[resolvedSlot] = null;
        persistCompareState();
        renderCompareBoard();
        return;
      }}
      compareState.signals[resolvedSlot] = {{
        signalId,
        timeframe: resolvedTimeframe,
        unavailable: false,
      }};
      persistCompareState();
      renderCompareBoard();
      try {{
        await fetchSignalPreviewSnapshot(signalId);
        if (
          compareState.signals[resolvedSlot]
          && compareState.signals[resolvedSlot].signalId === signalId
          && compareState.signals[resolvedSlot].timeframe === resolvedTimeframe
        ) {{
          compareState.signals[resolvedSlot].unavailable = false;
        }}
      }} catch (_error) {{
        if (
          compareState.signals[resolvedSlot]
          && compareState.signals[resolvedSlot].signalId === signalId
          && compareState.signals[resolvedSlot].timeframe === resolvedTimeframe
        ) {{
          compareState.signals[resolvedSlot].unavailable = true;
        }}
      }}
      renderCompareBoard();
      return;
    }};
    for (const button of document.querySelectorAll("[data-pin-root-preview]")) {{
      button.addEventListener("click", async (event) => {{
        event.preventDefault();
        event.stopPropagation();
        const rootCode = button.dataset.rootCode;
        const timeframe = button.dataset.timeframe || "1D";
        const slot = button.dataset.compareSlot || "a";
        if (!rootCode) {{
          return;
        }}
        await pinRootPreview(rootCode, timeframe, slot);
      }});
    }}
    for (const button of document.querySelectorAll("[data-pin-signal-preview]")) {{
      button.addEventListener("click", async (event) => {{
        event.preventDefault();
        event.stopPropagation();
        const signalId = button.dataset.signalId;
        const timeframe = button.dataset.timeframe || "1D";
        const slot = button.dataset.compareSlot || "a";
        if (!signalId) {{
          return;
        }}
        await pinSignalPreview(signalId, timeframe, slot);
      }});
    }}
    if (compareBoard) {{
      compareBoard.addEventListener("click", async (event) => {{
        const clearButtonNext = event.target.closest("[data-compare-clear-kind]");
        if (clearButtonNext) {{
          event.preventDefault();
          const kind = clearButtonNext.dataset.compareClearKind;
          const slot = normalizeCompareSlot(clearButtonNext.dataset.compareSlot);
          if (kind === "root") {{
            compareState.roots[slot] = null;
          }}
          if (kind === "signal") {{
            compareState.signals[slot] = null;
          }}
          persistCompareState();
          renderCompareBoard();
          return;
        }}
        const timeframeButtonNext = event.target.closest("[data-compare-timeframe]");
        if (timeframeButtonNext) {{
          event.preventDefault();
          const kind = timeframeButtonNext.dataset.compareKind;
          const slot = normalizeCompareSlot(timeframeButtonNext.dataset.compareSlot);
          const timeframe = normalizeCompareTimeframe(timeframeButtonNext.dataset.timeframe);
          if (kind === "root" && compareState.roots[slot]) {{
            compareState.roots[slot].timeframe = timeframe;
            compareState.roots[slot].unavailable = false;
            persistCompareState();
            renderCompareBoard();
            try {{
              await fetchRootPreviewSnapshot(compareState.roots[slot].rootCode);
            }} catch (_error) {{
              if (compareState.roots[slot]) {{
                compareState.roots[slot].unavailable = true;
              }}
            }}
            renderCompareBoard();
            return;
          }}
          if (kind === "signal" && compareState.signals[slot]) {{
            compareState.signals[slot].timeframe = timeframe;
            compareState.signals[slot].unavailable = false;
            persistCompareState();
            renderCompareBoard();
            try {{
              await fetchSignalPreviewSnapshot(compareState.signals[slot].signalId);
            }} catch (_error) {{
              if (compareState.signals[slot]) {{
                compareState.signals[slot].unavailable = true;
              }}
            }}
            renderCompareBoard();
            return;
          }}
        }}
        const clearButton = event.target.closest("[data-compare-clear]");
        if (clearButton) {{
          event.preventDefault();
          const slot = clearButton.dataset.compareClear;
          if (slot === "root") {{
            compareState.root = null;
          }}
          if (slot === "signal") {{
            compareState.signal = null;
          }}
          persistCompareState();
          renderCompareBoard();
          return;
        }}
        const rootTimeframeButton = event.target.closest("[data-compare-root-timeframe]");
        if (rootTimeframeButton && compareState.root) {{
          event.preventDefault();
          compareState.root.timeframe = normalizeCompareTimeframe(rootTimeframeButton.dataset.timeframe);
          compareState.root.unavailable = false;
          persistCompareState();
          renderCompareBoard();
          try {{
            await fetchRootPreviewSnapshot(compareState.root.rootCode);
          }} catch (_error) {{
            compareState.root.unavailable = true;
          }}
          renderCompareBoard();
          return;
        }}
        const signalTimeframeButton = event.target.closest("[data-compare-signal-timeframe]");
        if (signalTimeframeButton && compareState.signal) {{
          event.preventDefault();
          compareState.signal.timeframe = normalizeCompareTimeframe(signalTimeframeButton.dataset.timeframe);
          compareState.signal.unavailable = false;
          persistCompareState();
          renderCompareBoard();
          try {{
            await fetchSignalPreviewSnapshot(compareState.signal.signalId);
          }} catch (_error) {{
            compareState.signal.unavailable = true;
          }}
          renderCompareBoard();
        }}
      }});
    }}
    if (compareClearAllButton) {{
      compareClearAllButton.addEventListener("click", (event) => {{
        event.preventDefault();
        for (const slot of compareSlots) {{
          compareState.roots[slot] = null;
          compareState.signals[slot] = null;
        }}
        persistCompareState();
        renderCompareBoard();
        return;
        compareState.root = null;
        compareState.signal = null;
        persistCompareState();
        renderCompareBoard();
      }});
    }}
    restoreCompareState();
    renderCompareBoard();
    for (const slot of compareSlots) {{
      if (compareState.roots[slot]) {{
        void fetchRootPreviewSnapshot(compareState.roots[slot].rootCode)
          .then(() => {{
            if (compareState.roots[slot]) {{
              compareState.roots[slot].unavailable = false;
            }}
            renderCompareBoard();
          }})
          .catch(() => {{
            if (compareState.roots[slot]) {{
              compareState.roots[slot].unavailable = true;
            }}
            renderCompareBoard();
          }});
      }}
      if (compareState.signals[slot]) {{
        void fetchSignalPreviewSnapshot(compareState.signals[slot].signalId)
          .then(() => {{
            if (compareState.signals[slot]) {{
              compareState.signals[slot].unavailable = false;
            }}
            renderCompareBoard();
          }})
          .catch(() => {{
            if (compareState.signals[slot]) {{
              compareState.signals[slot].unavailable = true;
            }}
            renderCompareBoard();
          }});
      }}
    }}
    if (compareState.root) {{
      void fetchRootPreviewSnapshot(compareState.root.rootCode)
        .then(() => {{
          if (compareState.root) {{
            compareState.root.unavailable = false;
          }}
          renderCompareBoard();
        }})
        .catch(() => {{
          if (compareState.root) {{
            compareState.root.unavailable = true;
          }}
          renderCompareBoard();
        }});
    }}
    if (compareState.signal) {{
      void fetchSignalPreviewSnapshot(compareState.signal.signalId)
        .then(() => {{
          if (compareState.signal) {{
            compareState.signal.unavailable = false;
          }}
          renderCompareBoard();
        }})
        .catch(() => {{
          if (compareState.signal) {{
            compareState.signal.unavailable = true;
          }}
          renderCompareBoard();
        }});
    }}
    document.addEventListener("click", (event) => {{
      if (!event.target.closest("[data-root-preview-card]")) {{
        hideRootPreviews();
      }}
      if (!event.target.closest("[data-signal-preview-card]")) {{
        hideSignalPreviews();
      }}
    }});
    const workflowStatus = document.getElementById("workspace-workflow-status");
    const workflowButtons = document.querySelectorAll(".workflow-button[data-signal-id]");
    for (const button of workflowButtons) {{
      button.addEventListener("click", async () => {{
        const signalId = button.dataset.signalId;
        const workflowState = button.dataset.workflowState;
        if (!signalId || !workflowState) {{
          return;
        }}
        if (workflowStatus) {{
          workflowStatus.textContent = "Updating workflow...";
        }}
        const response = await fetch(`/api/v1/signals/${{signalId}}/workflow-state`, {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ workflow_state: workflowState }}),
        }});
        if (!response.ok) {{
          if (workflowStatus) {{
            workflowStatus.textContent = "Workflow update failed.";
          }}
          return;
        }}
        if (workflowStatus) {{
          workflowStatus.textContent = "Workflow updated. Refreshing...";
        }}
        const url = new URL(window.location.href);
        url.searchParams.set("signal_id", signalId);
        await window.__imoexRefreshPage(url.toString());
      }});
    }}
    const deliverySendButtons = document.querySelectorAll(".delivery-send-now");
    const deliverySendForceButtons = document.querySelectorAll(".delivery-send-now-force");
    const deliverySkipButtons = document.querySelectorAll(".delivery-skip-next");
    const deliveryUndoButtons = document.querySelectorAll(".delivery-undo-skip");
    const runDeliveryAction = async (eventKind, ignoreQuietHours) => {{
      if (deliveryStatus) {{
        deliveryStatus.textContent = ignoreQuietHours ? "Sending with quiet-hours override..." : "Sending...";
      }}
      const response = await fetch("/api/v1/workspace/delivery/send-now", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{
          root: "{escape(snapshot.selected_root)}",
          event_kind: eventKind,
          limit: 3,
          ignore_quiet_hours: ignoreQuietHours,
        }}),
      }});
      const payload = await response.json();
      if (!response.ok) {{
        if (deliveryStatus) {{
          deliveryStatus.textContent = "Delivery action failed.";
        }}
        return;
      }}
      if (deliveryStatus) {{
        deliveryStatus.textContent = payload.detail || payload.delivery_status || "Delivery action completed.";
      }}
      window.setTimeout(() => {{
        void window.__imoexRefreshPage();
      }}, 800);
    }};
    for (const button of deliverySendButtons) {{
      button.addEventListener("click", async () => {{
        await runDeliveryAction(button.dataset.eventKind, false);
      }});
    }}
    for (const button of deliverySendForceButtons) {{
      button.addEventListener("click", async () => {{
        await runDeliveryAction(button.dataset.eventKind, true);
      }});
    }}
    for (const button of deliverySkipButtons) {{
      button.addEventListener("click", async () => {{
        const eventKind = button.dataset.eventKind;
        if (deliveryStatus) {{
          deliveryStatus.textContent = "Updating next run...";
        }}
        const response = await fetch("/api/v1/workspace/delivery/skip-next", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ event_kind: eventKind }}),
        }});
        if (!response.ok) {{
          if (deliveryStatus) {{
            deliveryStatus.textContent = "Skip-next action failed.";
          }}
          return;
        }}
        if (deliveryStatus) {{
          deliveryStatus.textContent = "Next run updated. Reloading...";
        }}
        window.setTimeout(() => {{
          void window.__imoexRefreshPage();
        }}, 600);
      }});
    }}
    for (const button of deliveryUndoButtons) {{
      button.addEventListener("click", async () => {{
        const eventKind = button.dataset.eventKind;
        if (deliveryStatus) {{
          deliveryStatus.textContent = "Undoing skip...";
        }}
        const response = await fetch("/api/v1/workspace/delivery/undo-skip", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ event_kind: eventKind }}),
        }});
        if (!response.ok) {{
          if (deliveryStatus) {{
            deliveryStatus.textContent = "Undo-skip action failed.";
          }}
          return;
        }}
        if (deliveryStatus) {{
          deliveryStatus.textContent = "Skip removed. Reloading...";
        }}
        window.setTimeout(() => {{
          void window.__imoexRefreshPage();
        }}, 600);
      }});
    }}
  </script>
  </main>
  </div>
</body>
</html>"""


def _council_role_blueprint(role_key: str, language: str) -> dict[str, str]:
    blueprints = {
        "trend_vol": {
            "ru": {
                "title": "Аналитик тренда и волатильности",
                "inputs": "Смотрит на наклон тренда, режим волатильности, пробойные признаки и устойчивость движения по горизонту.",
                "output": "Даёт первичное направление сценария и решает, есть ли здесь преимущество или рынок пока в режиме no-edge.",
                "purpose": "Помогает понять, стоит ли идея на структуре движения цены или рынок пока слишком шумный.",
            },
            "en": {
                "title": "Trend / volatility analyst",
                "inputs": "Looks at trend slope, volatility regime, breakout features, and horizon-level stability.",
                "output": "Produces the first directional read and decides whether the setup has edge or is still near no-edge.",
                "purpose": "Shows whether the idea is supported by price structure or the market is still too noisy.",
            },
        },
        "flow_liquidity": {
            "ru": {
                "title": "Аналитик потока и ликвидности",
                "inputs": "Смотрит на ликвидность, качество потока, прокси стакана и риск проскальзывания.",
                "output": "Оценивает, можно ли доверять движению и не искажается ли оно тонким рынком.",
                "purpose": "Отделяет живое движение от ситуации, где цена идёт без достаточного подтверждения ликвидностью.",
            },
            "en": {
                "title": "Flow / liquidity analyst",
                "inputs": "Looks at liquidity, flow quality, order-book proxies, and slippage risk.",
                "output": "Judges whether the move is trustworthy or distorted by thin participation.",
                "purpose": "Separates real movement from fragile moves that can disappear on poor liquidity.",
            },
        },
        "oi_roll": {
            "ru": {
                "title": "Аналитик OI и ролла",
                "inputs": "Смотрит на долю следующего контракта, состояние ролла, близость экспирации и прокси открытого интереса.",
                "output": "Оценивает, насколько переход между контрактами может испортить текущий сигнал.",
                "purpose": "Не даёт воспринимать технический сигнал как чистый, когда цену уже заметно двигает ролл или экспирация.",
            },
            "en": {
                "title": "OI / roll analyst",
                "inputs": "Looks at next-contract share, roll state, time to expiry, and open-interest proxies.",
                "output": "Measures how much contract transition can distort the current signal.",
                "purpose": "Prevents a clean-looking technical setup from ignoring roll and expiry pressure.",
            },
        },
        "macro_event": {
            "ru": {
                "title": "Аналитик макро-событий",
                "inputs": "Смотрит на календарь событий, макро-режим и близость новостей, которые могут резко сменить контекст.",
                "output": "Даёт поправку на событийный риск и предупреждает, когда хороший сетап слишком зависим от календаря.",
                "purpose": "Нужен, чтобы было видно: рынок может быть прав по технике, но не пережить ближайшее событие.",
            },
            "en": {
                "title": "Macro-event analyst",
                "inputs": "Looks at the event calendar, macro regime, and proximity of news that can flip the context fast.",
                "output": "Adds the event-risk overlay and warns when a good setup is too dependent on timing.",
                "purpose": "Makes it clear that technical structure can still fail when the event calendar is too close.",
            },
        },
        "skeptic": {
            "ru": {
                "title": "Скептик",
                "inputs": "Собирает выводы аналитиков, ищет противоречия, проверяет риск ролла, экспирации и слабые места тезиса.",
                "output": "Даёт verdict и score доверия: насколько совет вообще готов пропустить идею дальше.",
                "purpose": "Это предохранитель. Скептик нужен не чтобы подтвердить идею, а чтобы найти причину её не брать.",
            },
            "en": {
                "title": "Skeptic",
                "inputs": "Collects analyst outputs, looks for contradictions, and checks roll, expiry, and thesis weaknesses.",
                "output": "Produces the approval verdict and score that decides whether the setup can move forward.",
                "purpose": "This is the safety brake: the skeptic is there to find reasons not to take the idea.",
            },
        },
        "arbiter": {
            "ru": {
                "title": "Арбитр",
                "inputs": "Берёт все голоса совета, результат скептика и текущие риски исполнения.",
                "output": "Формирует итоговое направление, уверенность, приоритет и короткое человеческое summary.",
                "purpose": "Это финальный перевод сложной внутренней логики в один понятный вывод для пользователя.",
            },
            "en": {
                "title": "Arbiter",
                "inputs": "Takes every council output, the skeptic result, and the current execution risks.",
                "output": "Produces the final direction, confidence, priority, and short human-readable summary.",
                "purpose": "Turns the internal debate into one clear decision the user can act on.",
            },
        },
    }
    fallback = {
        "ru": {
            "title": "Участник совета",
            "inputs": "Использует свою часть рыночного контекста и текущее состояние сигнала.",
            "output": "Возвращает промежуточное заключение по сценарию.",
            "purpose": "Нужен, чтобы итоговое решение не строилось на одном признаке.",
        },
        "en": {
            "title": "Council participant",
            "inputs": "Uses its slice of market context and the current signal state.",
            "output": "Returns an intermediate opinion on the setup.",
            "purpose": "Keeps the final decision from depending on one feature only.",
        },
    }
    return blueprints.get(role_key, fallback)["ru" if language == "ru" else "en"]


def _render_council_page(snapshot: WorkspaceSnapshot, *, language: str) -> str:
    focus = snapshot.focus_signal
    root_details = snapshot.root_details
    panel = snapshot.control_panel
    primary_feed = _primary_market_feed(panel)
    control_panel = _render_control_panel(panel)
    sidebar = _render_page_sidebar(
        "council",
        root=snapshot.selected_root,
        roots=snapshot.roots,
        signal_id=focus.signal_id if focus is not None else snapshot.selected_signal_id,
    )
    sidebar_styles = _render_page_sidebar_styles("1380px")
    is_ru = language == "ru"

    copy = {
        "title": "Как принимается решение" if is_ru else "How the decision is made",
        "eyebrow": "Совет сигналов | Прозрачность" if is_ru else "Signal council | Explainability",
        "hero_title": (
            f"Как совет принимает решение по {snapshot.selected_root}"
            if is_ru
            else f"How the council decides for {snapshot.selected_root}"
        ),
        "hero_intro": (
            "Здесь по шагам показано, какие вводные получает каждый участник совета, почему итоговое решение выглядит именно так и как читать score простым человеческим языком."
            if is_ru
            else "This page shows what each council participant receives as input, why the final call looks this way, and how to read the scores in plain language."
        ),
        "open_json": "Открыть JSON рабочего пространства" if is_ru else "Open workspace JSON",
        "open_workspace": "Открыть рабочее пространство" if is_ru else "Open workspace",
        "open_dashboard": "Открыть дашборд" if is_ru else "Open dashboard",
        "runtime": "Текущий runtime" if is_ru else "Current runtime",
        "data_mode": "Режим данных" if is_ru else "Data mode",
        "price_source": "Источник цены" if is_ru else "Price source",
        "reference": "Справочник контрактов" if is_ru else "Contract reference",
        "latest_market": "Последние рыночные данные" if is_ru else "Latest market data",
        "latest_reference": "Последняя синхронизация справочника" if is_ru else "Latest reference sync",
        "inputs_title": "Какие вводные получает совет" if is_ru else "What enters the council",
        "inputs_note": (
            "До спора моделей в совет попадает единый пакет данных о рынке, контракте и текущем сигнале."
            if is_ru
            else "Before models disagree with each other, the council gets one shared packet of market, contract, and signal context."
        ),
        "flow_title": "Блок-схема решения" if is_ru else "Decision flow",
        "flow_note": (
            "Упрощённый путь от исходных данных до финального решения, которое видит пользователь."
            if is_ru
            else "A simplified path from raw inputs to the final decision the user sees."
        ),
        "roles_title": "Кто участвует в совете" if is_ru else "Who sits on the council",
        "roles_note": (
            "У каждой роли свой срез рынка. Ниже видно, что каждая роль берёт на вход и что возвращает на выход."
            if is_ru
            else "Every role sees a different slice of the market. Below you can see what each role takes in and what it returns."
        ),
        "looks_at": "Смотрит на" if is_ru else "Looks at",
        "produces": "Возвращает" if is_ru else "Produces",
        "purpose": "Зачем нужен" if is_ru else "Why it matters",
        "fixed": "Сейчас роль жёстко закреплена за этой моделью." if is_ru else "This role is currently fixed to this model.",
        "dynamic": "Роль выбирается динамически." if is_ru else "This role is routed dynamically.",
        "decision_title": "Почему итог сейчас такой" if is_ru else "Why the current output looks like this",
        "decision_note": (
            "Это краткая человеческая расшифровка того, почему арбитр оставил именно такой вывод на поверхности продукта."
            if is_ru
            else "This is the short human explanation for why the arbiter left this exact output on the product surface."
        ),
        "why_now": "Почему сейчас" if is_ru else "Why now",
        "pushback": "Что сдерживает" if is_ru else "What is holding it back",
        "invalidation": "Что отменяет сценарий" if is_ru else "What would break it",
        "score_title": "Как читать итоговые score" if is_ru else "How to read the final scores",
        "score_note": (
            "Ключевые score вынесены отдельно, чтобы решение было прозрачным даже для нетехнического пользователя."
            if is_ru
            else "Key scores are separated out so the decision stays transparent even for a non-technical user."
        ),
        "runtime_title": "Текущий стек моделей и источников" if is_ru else "Current model and data stack",
        "runtime_note": (
            "Здесь уже полный runtime: какие модели закреплены за ролями и чьи данные реально используются."
            if is_ru
            else "This is the full runtime: which models own the roles and whose data is actually being used."
        ),
    }

    direction_labels = {
        "bullish": "Бычий" if is_ru else "Bullish",
        "bearish": "Медвежий" if is_ru else "Bearish",
        "no_edge": "Без преимущества" if is_ru else "No edge",
        "neutral": "Нейтральный" if is_ru else "Neutral",
    }
    status_labels = {
        "active": "Активен" if is_ru else "Active",
        "resolved": "Разрешён" if is_ru else "Resolved",
        "invalidated": "Инвалидирован" if is_ru else "Invalidated",
    }
    workflow_labels = {
        SignalWorkflowState.WATCHING: "Наблюдаю" if is_ru else "Watching",
        SignalWorkflowState.VALIDATING: "Проверяю" if is_ru else "Validating",
        SignalWorkflowState.READY: "Готов" if is_ru else "Ready",
        SignalWorkflowState.IGNORED: "Игнорирую" if is_ru else "Ignored",
        SignalWorkflowState.ESCALATE: "Эскалирую" if is_ru else "Escalated",
        SignalWorkflowState.RESOLVED: "Завершено" if is_ru else "Resolved",
    }

    focus_header = (
        f"{focus.root} | {focus.contract} | {focus.horizon.value}"
        if focus is not None
        else ("Сигнала в фокусе пока нет" if is_ru else "No focus signal yet")
    )
    focus_summary = (
        focus.summary
        if focus is not None
        else (
            "Выберите серию или дождитесь следующего пересчёта, чтобы увидеть живую анатомию решения."
            if is_ru
            else "Pick a root or wait for the next recalculation cycle to see the live decision anatomy."
        )
    )
    final_call = (
        f"{direction_labels.get(focus.direction_final.value, focus.direction_final.value)} · {status_labels.get(focus.status.value, focus.status.value)}"
        if focus is not None
        else "n/a"
    )
    workflow_state = workflow_labels.get(focus.workflow_state, _workflow_state_label(focus.workflow_state)) if focus is not None else "n/a"

    session_name = root_details.session.session_type.value if root_details is not None else "n/a"
    trading_day = root_details.session.trading_day.isoformat() if root_details is not None else "n/a"
    active_contract = root_details.continuous_series.active_contract if root_details is not None else "n/a"
    next_contract = root_details.continuous_series.next_contract if root_details is not None else "n/a"
    days_to_expiry = str(root_details.continuous_series.days_to_expiry) if root_details is not None else "n/a"
    expiry_date = (
        _format_calendar_date(root_details.continuous_series.expiry_date, language=language)
        if root_details is not None
        else "n/a"
    )
    roll_share = f"{root_details.continuous_series.next_contract_share:.0%}" if root_details is not None else "n/a"
    price_source = primary_feed.owner if primary_feed is not None else "n/a"
    data_mode = _control_panel_data_mode_label(panel.data_mode)
    reference_state = f"{_control_panel_reference_sync_label(panel.reference_sync.status)} · {_control_panel_reference_sync_source(panel.reference_sync.source)}"
    contract_context = (
        f"{next_contract} · экспирация {days_to_expiry} дн. до {expiry_date} · ролл {roll_share}"
        if is_ru
        else f"{next_contract} · expiry in {days_to_expiry}d ({expiry_date}) · roll {roll_share}"
    )

    role_cards = []
    for item in panel.model_roles:
        blueprint = _council_role_blueprint(item.role_key, language)
        role_cards.append(
            '<article class="role-card">'
            f'<strong>{escape(blueprint["title"])}</strong>'
            f'<p class="role-runtime">{escape(item.product)} · {escape(item.model)} · {escape(item.owner)}</p>'
            '<div class="role-facts">'
            f'<div><span>{escape(copy["looks_at"])}</span><p>{escape(blueprint["inputs"])}</p></div>'
            f'<div><span>{escape(copy["produces"])}</span><p>{escape(blueprint["output"])}</p></div>'
            f'<div><span>{escape(copy["purpose"])}</span><p>{escape(blueprint["purpose"])}</p></div>'
            "</div>"
            f'<small>{escape(copy["fixed"] if item.control_mode == "fixed" else copy["dynamic"])}</small>'
            "</article>"
        )

    why_now_items = "".join(f"<li>{escape(item)}</li>" for item in (focus.drivers if focus is not None else [])) or f"<li>{escape('Драйверы пока не зафиксированы.' if is_ru else 'No drivers are recorded yet.')}</li>"
    pushback_items = "".join(f"<li>{escape(item)}</li>" for item in (focus.objections if focus is not None else [])) or f"<li>{escape('Сдерживающие факторы пока не зафиксированы.' if is_ru else 'No pushback is recorded yet.')}</li>"
    invalidation_items = "".join(f"<li>{escape(item)}</li>" for item in (focus.invalidation_conditions if focus is not None else [])) or f"<li>{escape('?????????????? ???????????? ???????? ???? ??????????????????????????.' if is_ru else 'No invalidation conditions are recorded yet.')}</li>"
    disagreement_map = _render_confidence_decomposition(snapshot.focus_confidence)
    counterfactual_prompt = (
        "?????? ?????????????????? ???????????????? ?? no-trade, ?? ?????????? ???????? ???????????????????? ?????????????? ???????????????????????"
        if is_ru
        else "What would make this a no-trade, and what single observation would upgrade conviction?"
    )
    counterfactual_note = (
        ("???????????????????? ????????????????: " if is_ru else "No-trade trigger: ")
        + escape(
            focus.invalidation_conditions[0]
            if focus is not None and focus.invalidation_conditions
            else (
                "?????? ?????????????? ?????????????????? ???????????????? ?????? ???????????????????? ?????????? ????????????."
                if is_ru
                else "If the key driver breaks or data freshness degrades materially."
            )
        )
        + "<br>"
        + (("?????????????? conviction: ") if is_ru else "Conviction upgrade: ")
        + escape(
            focus.drivers[0]
            if focus is not None and focus.drivers
            else "A fresh confirming move from the same direction across higher horizons."
        )
    )
    session_guidance = _render_review_bundle(snapshot.review_bundle)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(copy["title"])}</title>
  <style>
    :root {{ --bg:#f6f1e7; --paper:rgba(255,250,241,.9); --ink:#17222c; --muted:#5e6b73; --line:rgba(23,34,44,.1); --navy:#193a52; --teal:#0f6c67; --amber:#b66d1f; --coral:#b64b3d; --mint:#2f7d5b; --shadow:0 18px 46px rgba(23,34,44,.11); }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; min-height:100vh; color:var(--ink); font-family:"Segoe UI","Trebuchet MS",sans-serif; background:radial-gradient(circle at top left,rgba(182,109,31,.17),transparent 26%),radial-gradient(circle at top right,rgba(15,108,103,.18),transparent 24%),linear-gradient(180deg,#fbf7f0,var(--bg)); }}
    a {{ color:inherit; text-decoration:none; }}
    .shell {{ width:min(1380px,calc(100% - 28px)); margin:18px auto 36px; }}
    .hero,.panel {{ background:var(--paper); border:1px solid var(--line); border-radius:30px; box-shadow:var(--shadow); backdrop-filter:blur(14px); }}
    .hero {{ display:grid; grid-template-columns:minmax(0,1.45fr) minmax(320px,.95fr); gap:18px; padding:24px; }}
    .eyebrow {{ display:inline-flex; gap:8px; align-items:center; padding:8px 12px; border-radius:999px; background:rgba(25,58,82,.08); color:var(--navy); text-transform:uppercase; letter-spacing:.08em; font-size:12px; }}
    h1 {{ margin:14px 0 10px; font-family:Georgia,"Palatino Linotype",serif; font-size:clamp(34px,5vw,58px); line-height:.98; max-width:11ch; }}
    h2 {{ margin:0; font-family:Georgia,"Palatino Linotype",serif; font-size:24px; }}
    h3 {{ margin:0 0 10px; font-size:16px; }}
    .muted,.panel-note,.input-card p,.score-card p,.role-facts p,.why-card ul,.control-summary-card small,.role-card small {{ color:var(--muted); line-height:1.6; }}
    .hero-actions {{ display:flex; flex-wrap:wrap; gap:10px; margin-top:18px; }}
    .button {{ display:inline-flex; align-items:center; justify-content:center; padding:12px 16px; border-radius:14px; border:1px solid var(--line); background:rgba(255,255,255,.62); font-weight:600; }}
    .button.primary {{ background:var(--navy); border-color:transparent; color:#fdf8f0; }}
    .hero-side {{ padding:18px; border-radius:24px; background:linear-gradient(160deg,rgba(25,58,82,.96),rgba(15,108,103,.88)); color:#f5efe6; display:grid; gap:12px; }}
    .hero-side p,.hero-side small {{ color:rgba(245,239,230,.84); line-height:1.55; }}
    .hero-stats,.input-grid,.score-grid,.control-summary-grid,.why-grid,.role-grid,.metric-list {{ display:grid; gap:14px; }}
    .hero-stats {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
    .hero-stats article,.input-card,.score-card,.role-card,.why-card,.control-summary-card,.flow-node,.metric-list article {{ padding:16px 18px; border-radius:20px; border:1px solid var(--line); background:rgba(255,255,255,.7); display:grid; gap:8px; align-content:start; }}
    .hero-stats article {{ background:rgba(255,255,255,.1); }}
    .hero-stats span,.input-card span,.score-card span,.flow-node span,.role-facts span,.control-summary-card label {{ display:block; margin-bottom:8px; font-size:11px; text-transform:uppercase; letter-spacing:.08em; color:var(--muted); }}
    .hero-side .hero-stats span {{ color:rgba(245,239,230,.74); }}
    .input-grid,.score-grid,.control-summary-grid,.metric-list {{ grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); }}
    .role-grid {{ grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); }}
    .why-grid {{ grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); }}
    .input-card,.score-card,.control-summary-card {{
      min-height: 168px;
      padding: 18px 20px;
      grid-template-rows:auto auto 1fr;
    }}
    .input-card strong,.score-card strong,.control-summary-card strong,.flow-node strong,.role-card strong {{
      font-size:clamp(1.3rem, 1.65vw, 1.72rem);
      line-height:1.18;
      word-break:normal;
      overflow-wrap:break-word;
      hyphens:auto;
      text-wrap:pretty;
    }}
    .metric-list article {{
      min-height: 0;
    }}
    .metric-list article strong,.metric-list article p {{
      word-break:normal;
      overflow-wrap:break-word;
      hyphens:auto;
      text-wrap:pretty;
    }}
    .input-card p,.score-card p,.role-facts p,.why-card li,.flow-node p,.role-card small,.control-summary-card small {{
      word-break:normal;
      overflow-wrap:break-word;
      hyphens:auto;
      text-wrap:pretty;
    }}
    .panel {{ padding:22px; margin-top:16px; }}
    .panel-head {{ display:flex; flex-wrap:wrap; justify-content:space-between; gap:12px; align-items:baseline; margin-bottom:16px; }}
    .flow-strip {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:16px; align-items:stretch; }}
    .flow-node {{ min-height:0; grid-template-rows:auto auto 1fr; }}
    .flow-arrow {{ display:none; }}
    .role-runtime {{ margin:0; color:var(--navy); font-weight:600; }}
    .role-facts {{ display:grid; gap:10px; }}
    .why-card ul {{ margin:0; padding-left:18px; }}
    .control-summary-card.is-wide {{
      grid-column:span 2;
      min-height: 0;
    }}
    .tone-positive strong {{ color:var(--mint); }} .tone-warning strong {{ color:var(--amber); }} .tone-negative strong {{ color:var(--coral); }}
    @media (max-width:1180px) {{
      .hero {{ grid-template-columns:1fr; }}
      .hero-stats {{ grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); }}
    }}
    @media (max-width:760px) {{
      .control-summary-card.is-wide {{ grid-column:span 1; }}
      .shell {{ width:min(100% - 18px,1380px); }}
      .hero {{ padding:22px; }}
      .hero-stats,
      .input-grid,
      .score-grid,
      .control-summary-grid,
      .why-grid,
      .role-grid,
      .metric-list,
      .flow-strip {{ grid-template-columns:1fr; }}
      .flow-node {{ min-height:0; }}
    }}
    {sidebar_styles}
  </style>
</head>
<body>
  <div class="page-shell">
  {sidebar}
  <main class="shell">
    <section class="hero">
      <div>
        <span class="eyebrow">{escape(copy["eyebrow"])}</span>
        <h1>{escape(copy["hero_title"])}</h1>
        <p class="muted">{escape(copy["hero_intro"])}</p>
        <div class="hero-actions">
          <a class="button primary" href="/api/v1/workspace?root={escape(snapshot.selected_root)}">{escape(copy["open_json"])}</a>
          <a class="button" href="/workspace?root={escape(snapshot.selected_root)}">{escape(copy["open_workspace"])}</a>
          <a class="button" href="/dashboard?root={escape(snapshot.selected_root)}">{escape(copy["open_dashboard"])}</a>
        </div>
      </div>
      <aside class="hero-side">
        <div><strong>{escape(focus_header)}</strong><p>{escape(focus_summary)}</p></div>
        <div class="hero-stats">
          <article><span>{escape(copy["runtime"])}</span><strong>{escape(panel.llm_product)} · {escape(panel.llm_model)}</strong></article>
          <article><span>{escape(copy["data_mode"])}</span><strong>{escape(data_mode)}</strong></article>
          <article><span>{escape(copy["price_source"])}</span><strong>{escape(price_source)}</strong></article>
          <article><span>{escape(copy["reference"])}</span><strong>{escape(reference_state)}</strong></article>
          <article><span>{escape(copy["latest_market"])}</span><strong>{escape(_format_timestamp(panel.latest_market_data_at))}</strong></article>
          <article><span>{escape(copy["latest_reference"])}</span><strong>{escape(_format_timestamp(panel.reference_sync.last_sync_at))}</strong></article>
        </div>
      </aside>
    </section>
    <section class="panel"><div class="panel-head"><h2>{escape(copy["inputs_title"])}</h2></div><p class="panel-note">{escape(copy["inputs_note"])}</p><div class="input-grid"><article class="input-card"><span>{"Рыночный контекст" if is_ru else "Market context"}</span><strong>{escape(session_name)}</strong><p>{escape(snapshot.selected_root)} · {escape(trading_day)}</p></article><article class="input-card"><span>{"Контракт и экспирация" if is_ru else "Contract and expiry"}</span><strong>{escape(active_contract)}</strong><p>{escape(contract_context)}</p></article><article class="input-card"><span>{"Сигнал в фокусе" if is_ru else "Signal in focus"}</span><strong>{escape(final_call)}</strong><p>{escape(focus_header)} · {escape(workflow_state)}</p></article><article class="input-card"><span>{"Источники и синхронизация" if is_ru else "Sources and sync"}</span><strong>{escape(price_source)}</strong><p>{escape(data_mode)} · {escape(reference_state)}</p></article></div></section>
    <section class="panel">
      <div class="panel-head">
        <h2>{escape(copy["flow_title"])}</h2>
      </div>
      <p class="panel-note">{escape(copy["flow_note"])}</p>
      <div class="flow-strip">
        <article class="flow-node">
          <span>{"1. Вводные данные" if is_ru else "1. Inputs"}</span>
          <strong>{escape(snapshot.selected_root)}</strong>
          <p>{"Цена, сессия, контракт, экспирация и состояние источников." if is_ru else "Price, session, contract ladder, expiry, and source state."}</p>
        </article>
        <article class="flow-node">
          <span>{"2. Аналитики" if is_ru else "2. Analysts"}</span>
          <strong>{sum(1 for item in panel.model_roles if item.role_key not in {'skeptic', 'arbiter'})}</strong>
          <p>{"Каждый аналитик смотрит на свой кусок рынка и даёт промежуточный вывод." if is_ru else "Each analyst looks at one slice of the market and returns an intermediate read."}</p>
        </article>
        <article class="flow-node">
          <span>{"3. Скептик" if is_ru else "3. Skeptic"}</span>
          <strong>{escape(f"{focus.skeptic_score:.2f}" if focus is not None else "n/a")}</strong>
          <p>{"Ищет противоречия и снижает доверие, если тезис слабый." if is_ru else "Looks for contradictions and reduces trust when the thesis is weak."}</p>
        </article>
        <article class="flow-node">
          <span>{"4. Арбитр" if is_ru else "4. Arbiter"}</span>
          <strong>{escape(final_call)}</strong>
          <p>{"Собирает голоса совета и превращает их в один итоговый сценарий." if is_ru else "Collects the council outputs and turns them into one final scenario."}</p>
        </article>
        <article class="flow-node">
          <span>{"5. Выход для пользователя" if is_ru else "5. User output"}</span>
          <strong>{escape(workflow_state)}</strong>
          <p>{"На экран попадают summary, направление, confidence, priority и статус." if is_ru else "The product shows the summary, direction, confidence, priority, and workflow state."}</p>
        </article>
      </div>
    </section>
    <section class="panel"><div class="panel-head"><h2>{escape(copy["roles_title"])}</h2></div><p class="panel-note">{escape(copy["roles_note"])}</p><div class="role-grid">{"".join(role_cards)}</div></section>
    <section class="panel"><div class="panel-head"><h2>{escape(copy["decision_title"])}</h2></div><p class="panel-note">{escape(copy["decision_note"])}</p><div class="input-grid"><article class="input-card"><span>{"Итоговый вывод" if is_ru else "Final call"}</span><strong>{escape(final_call)}</strong><p>{escape(focus_header)}</p></article><article class="input-card"><span>{"Короткое объяснение" if is_ru else "Short explanation"}</span><strong>{escape(f"{focus.confidence_final:.2f}" if focus is not None else "n/a")}</strong><p>{escape(focus_summary)}</p></article><article class="input-card"><span>{"Статус работы" if is_ru else "Workflow"}</span><strong>{escape(workflow_state)}</strong><p>{escape(snapshot.selected_root)} · {escape(price_source)}</p></article></div><div class="why-grid"><article class="why-card"><h3>{'Почему сейчас' if is_ru else 'Why now'}</h3><ul>{why_now_items}</ul></article><article class="why-card"><h3>{'Что сдерживает' if is_ru else 'What is holding it back'}</h3><ul>{pushback_items}</ul></article><article class="why-card"><h3>{'Что отменяет сценарий' if is_ru else 'What would break it'}</h3><ul>{invalidation_items}</ul></article></div></section>
    <section class="panel"><div class="panel-head"><h2>{"Карта разногласий" if is_ru else "Disagreement map"}</h2></div><p class="panel-note">{"Показывает, где аналитики усиливают тезис, а где скептик снижает доверие." if is_ru else "Shows where analysts strengthen the thesis and where the skeptic takes trust away."}</p>{disagreement_map}</section>
    <section class="panel"><div class="panel-head"><h2>{"Контрфактические подсказки" if is_ru else "Counterfactual prompts"}</h2></div><p class="panel-note">{escape(counterfactual_prompt)}</p><div class="metric-list"><article><strong>{"Порог отмены" if is_ru else "No-trade trigger"}</strong><p class="muted">{counterfactual_note}</p></article></div></section>
    <section class="panel"><div class="panel-head"><h2>{"Позиционирование по сессии" if is_ru else "Session-aware posture guidance"}</h2></div><p class="panel-note">{"Короткий обзор для opening auction, post-clearing, rollover window и моментов с пониженной ликвидностью." if is_ru else "A compact review for the opening auction, post-clearing, rollover window, and low-liquidity caution zones."}</p>{session_guidance}</section>
    <section class="panel"><div class="panel-head"><h2>{escape(copy["score_title"])}</h2></div><p class="panel-note">{escape(copy["score_note"])}</p><div class="score-grid"><article class="score-card"><span>{"Приоритет" if is_ru else "Priority"}</span><strong>{escape(str(focus.priority_score) if focus is not None else "n/a")}</strong><p>{"Показывает, насколько высоко сигнал должен стоять в пользовательской ленте." if is_ru else "Shows how high the signal should sit in the user-facing queue."}</p></article><article class="score-card"><span>{"Уверенность" if is_ru else "Confidence"}</span><strong>{escape(f"{focus.confidence_final:.2f}" if focus is not None else "n/a")}</strong><p>{"Показывает, насколько устойчив итоговый сценарий после калибровки." if is_ru else "Shows how stable the final scenario looks after calibration."}</p></article><article class="score-card"><span>{"Скептик" if is_ru else "Skeptic"}</span><strong>{escape(f"{focus.skeptic_score:.2f}" if focus is not None else "n/a")}</strong><p>{"Чем выше значение, тем меньше у скептика возражений к текущей идее." if is_ru else "Higher means the skeptic has fewer objections to the current idea."}</p></article><article class="score-card"><span>{"Риск ролла" if is_ru else "Roll risk"}</span><strong>{escape(f"{focus.roll_risk:.2f}" if focus is not None else "n/a")}</strong><p>{"Чем выше значение, тем сильнее переход между контрактами может исказить сигнал." if is_ru else "Higher means the contract transition can distort the setup more strongly."}</p></article><article class="score-card"><span>{"Риск экспирации" if is_ru else "Expiry risk"}</span><strong>{escape(f"{focus.expiry_risk:.2f}" if focus is not None else "n/a")}</strong><p>{"Чем выше значение, тем больше близость экспирации влияет на решение." if is_ru else "Higher means time-to-expiry matters more for this decision."}</p></article></div></section>
    <section class="panel"><div class="panel-head"><h2>{escape(copy["runtime_title"])}</h2></div><p class="panel-note">{escape(copy["runtime_note"])}</p>{control_panel}</section>
  </main>
  </div>
</body>
</html>"""


def _render_journal_workspace(snapshot: JournalWorkspaceSnapshot) -> str:
    sidebar = _render_page_sidebar("journal", root=snapshot.selected_root, roots=snapshot.roots)
    sidebar_styles = _render_page_sidebar_styles("1280px")
    root_filters = ['<a class="chip{}" href="/workspace/journal">All roots</a>'.format(" is-active" if snapshot.selected_root is None else "")]
    for root in snapshot.roots:
        query = urlencode({"root": root.root_code, **({"status": snapshot.selected_status.value} if snapshot.selected_status is not None else {}), **({"kind": snapshot.selected_kind.value} if snapshot.selected_kind is not None else {})})
        root_filters.append(
            f'<a class="chip{" is-active" if snapshot.selected_root == root.root_code else ""}" href="/workspace/journal?{escape(query)}">{escape(root.root_code)}</a>'
        )

    status_filters = ['<a class="chip{}" href="{}">All statuses</a>'.format(" is-active" if snapshot.selected_status is None else "", escape(_journal_filter_href(root=snapshot.selected_root, kind=snapshot.selected_kind)))]
    for status in SignalStatus:
        status_filters.append(
            f'<a class="chip{" is-active" if snapshot.selected_status == status else ""}" href="{escape(_journal_filter_href(root=snapshot.selected_root, status=status, kind=snapshot.selected_kind))}">{escape(status.value)}</a>'
        )

    kind_filters = ['<a class="chip{}" href="{}">All kinds</a>'.format(" is-active" if snapshot.selected_kind is None else "", escape(_journal_filter_href(root=snapshot.selected_root, status=snapshot.selected_status)))]
    for kind in JournalEntryKind:
        kind_filters.append(
            f'<a class="chip{" is-active" if snapshot.selected_kind == kind else ""}" href="{escape(_journal_filter_href(root=snapshot.selected_root, status=snapshot.selected_status, kind=kind))}">{escape(kind.value)}</a>'
        )

    entry_cards = "".join(_render_journal_workspace_entry(item) for item in snapshot.entries) or '<p class="empty">No journal entries match the current filters yet.</p>'
    decision_cards = "".join(_render_journal_decision_log_item(item) for item in snapshot.decision_log) or '<p class="empty">No decision cards available for the current filter window.</p>'
    related = "".join(_render_related_signal(item) for item in snapshot.related_signals) or '<p class="empty">No related signals in the current filter window.</p>'
    payload = escape(json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Journal Workspace</title>
  <style>
    :root {{
      --bg: #f6f0e7;
      --paper: rgba(255, 250, 241, 0.9);
      --ink: #18222b;
      --muted: #5d6b72;
      --line: rgba(24, 34, 43, 0.1);
      --navy: #17384f;
      --teal: #116866;
      --amber: #ba7021;
      --shadow: 0 18px 46px rgba(24, 34, 43, 0.11);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      font-family: "Segoe UI", "Trebuchet MS", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(186, 112, 33, 0.16), transparent 24%),
        radial-gradient(circle at right, rgba(17, 104, 102, 0.18), transparent 22%),
        linear-gradient(180deg, #fbf7f0, var(--bg));
    }}
    a {{ color: inherit; text-decoration: none; }}
    .shell {{ width: min(1280px, calc(100% - 28px)); margin: 20px auto 36px; display: grid; gap: 16px; }}
    .hero, .panel {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 30px;
      box-shadow: var(--shadow);
      padding: 24px;
    }}
    .hero {{
      display: grid;
      grid-template-columns: minmax(0, 1.5fr) minmax(260px, 0.9fr);
      gap: 18px;
    }}
    .eyebrow {{
      display: inline-flex;
      gap: 8px;
      align-items: center;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(23, 56, 79, 0.08);
      color: var(--navy);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 12px;
    }}
    h1 {{
      margin: 14px 0 10px;
      font-family: Georgia, "Palatino Linotype", serif;
      font-size: clamp(34px, 5vw, 56px);
      line-height: 0.98;
      max-width: 11ch;
    }}
    h2 {{
      margin: 0;
      font-family: Georgia, "Palatino Linotype", serif;
      font-size: 22px;
    }}
    .muted, .empty {{ color: var(--muted); line-height: 1.55; }}
    .actions, .chips {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 14px;
    }}
    .button, .chip {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 11px 14px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.64);
      font-weight: 600;
    }}
    .button.primary, .chip.is-active {{
      background: var(--navy);
      color: #fff8ef;
      border-color: transparent;
    }}
    .hero-side {{
      display: grid;
      gap: 10px;
      padding: 18px;
      border-radius: 24px;
      background: linear-gradient(160deg, rgba(23, 56, 79, 0.96), rgba(17, 104, 102, 0.88));
      color: #f6efe5;
    }}
    .hero-side p {{ color: rgba(246, 239, 229, 0.84); margin: 0; }}
    .hero-side strong {{ font-size: 24px; }}
    .layout {{
      display: grid;
      grid-template-columns: minmax(0, 1.45fr) minmax(300px, 0.95fr);
      gap: 16px;
    }}
    .stack, .entry-list, .related-list, .metric-grid, .decision-list {{ display: grid; gap: 12px; }}
    .metric-grid {{
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    }}
    .metric-grid article, .entry-card, .related-card, .raw-box, .decision-card {{
      padding: 14px 16px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.68);
    }}
    .metric-grid span {{
      display: block;
      margin-bottom: 8px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 11px;
    }}
    .metric-grid strong {{ font-size: 20px; }}
    .entry-meta {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      gap: 10px;
      margin-bottom: 10px;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 7px 10px;
      border-radius: 999px;
      background: rgba(17, 104, 102, 0.08);
      color: var(--teal);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 12px;
    }}
    .decision-head {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      gap: 10px;
      align-items: flex-start;
      margin-bottom: 12px;
    }}
    .decision-head-actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }}
    .decision-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 10px;
    }}
    .decision-grid article {{
      padding: 12px 14px;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.74);
    }}
    .decision-grid span {{
      display: block;
      margin-bottom: 8px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 11px;
    }}
    .decision-grid ul {{
      margin: 0;
      padding-left: 18px;
      color: var(--ink);
      line-height: 1.55;
    }}
    .decision-grid p {{
      margin: 0;
      line-height: 1.6;
    }}
    pre {{
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: Consolas, "Courier New", monospace;
      font-size: 12px;
      color: var(--muted);
    }}
    @media (max-width: 980px) {{
      .hero, .layout {{
        grid-template-columns: 1fr;
      }}
      .shell {{ width: min(100% - 16px, 1280px); }}
    }}
    {sidebar_styles}
  </style>
</head>
<body>
  <div class="page-shell">
  {sidebar}
  <main class="shell">
    <section class="hero">
      <div>
        <span class="eyebrow">Journal Workspace | User Workflow</span>
        <h1>Trading memory for the signal system</h1>
        <p class="muted">
          This is the user-facing journal hub: thesis notes, risk notes, execution notes and post-mortems
          across the current signal inventory.
        </p>
        <div class="actions">
          <a class="button primary" href="/api/v1/workspace/journal">Open journal JSON</a>
          <a class="button" href="/workspace">Open workspace</a>
          <a class="button" href="/workspace/preferences">Preferences</a>
        </div>
      </div>
      <aside class="hero-side">
        <p>Total entries</p>
        <strong>{snapshot.total_entries}</strong>
        <p>Thesis {snapshot.thesis_entries} | Risk {snapshot.risk_entries} | Post-mortems {snapshot.post_mortems}</p>
      </aside>
    </section>
    <section class="panel">
      <h2>Filters</h2>
      <div class="chips">{''.join(root_filters)}</div>
      <div class="chips">{''.join(status_filters)}</div>
      <div class="chips">{''.join(kind_filters)}</div>
    </section>
    <section class="panel">
      <h2>Decision log</h2>
      <p class="muted">What the user decided, why the current call exists, and what needs to change next.</p>
      <div class="decision-list">{decision_cards}</div>
    </section>
    <section class="layout">
      <div class="stack">
        <section class="panel">
          <h2>Journal tape</h2>
          <div class="metric-grid">
            <article><span>Total</span><strong>{snapshot.total_entries}</strong></article>
            <article><span>Thesis</span><strong>{snapshot.thesis_entries}</strong></article>
            <article><span>Risk</span><strong>{snapshot.risk_entries}</strong></article>
            <article><span>Post-mortems</span><strong>{snapshot.post_mortems}</strong></article>
          </div>
          <div class="entry-list" style="margin-top:16px;">{entry_cards}</div>
        </section>
      </div>
      <div class="stack">
        <section class="panel">
          <h2>Current signal lane</h2>
          <div class="related-list">{related}</div>
        </section>
        <section class="panel">
          <h2>Raw snapshot</h2>
          <div class="raw-box">
            <pre id="journal-workspace-data">{payload}</pre>
          </div>
        </section>
      </div>
    </section>
  </main>
  </div>
</body>
</html>"""


def _render_delivery_history_workspace(snapshot: DeliveryHistoryWorkspaceSnapshot) -> str:
    sidebar = _render_page_sidebar("delivery-history", root=snapshot.selected_root, roots=snapshot.roots)
    sidebar_styles = _render_page_sidebar_styles("1320px")
    selected_root = snapshot.selected_root
    root_links = ['<a class="chip{}" href="/workspace/delivery-history">All roots</a>'.format(" is-active" if selected_root is None and snapshot.delivery_activity_filters.root_scope is None else "")]
    for root in snapshot.roots:
        href = _delivery_activity_filter_href(
            "/workspace/delivery-history",
            root=root.root_code,
            activity_root_scope=root.root_code,
            activity_event_kind=snapshot.delivery_activity_filters.event_kind,
            activity_status=snapshot.delivery_activity_filters.status,
        )
        root_links.append(
            f'<a class="chip{" is-active" if snapshot.delivery_activity_filters.root_scope == root.root_code else ""}" href="{escape(href)}">{escape(root.root_code)}</a>'
        )

    delivery_activity = _render_delivery_activity(snapshot.delivery_activity)
    delivery_activity_controls = _render_delivery_activity_controls(
        base_path="/workspace/delivery-history",
        root=selected_root,
        filters=snapshot.delivery_activity_filters,
        by_event_kind=snapshot.delivery_activity_by_event_kind,
        by_root_scope=snapshot.delivery_activity_by_root_scope,
        by_status=snapshot.delivery_activity_by_status,
    )
    delivery_activity_footer = _render_delivery_activity_footer(
        base_path="/workspace/delivery-history",
        export_path="/api/v1/workspace/delivery/activity/export",
        root=selected_root,
        filters=snapshot.delivery_activity_filters,
        pagination=snapshot.delivery_activity_pagination,
    )
    payload = escape(json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Delivery History</title>
  <style>
    :root {{
      --bg: #f6f0e6;
      --paper: rgba(255, 250, 242, 0.9);
      --ink: #18232c;
      --muted: #5e6b73;
      --line: rgba(24, 35, 44, 0.1);
      --navy: #17384f;
      --teal: #116866;
      --shadow: 0 18px 46px rgba(24, 35, 44, 0.11);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      font-family: "Segoe UI", "Trebuchet MS", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(187, 113, 34, 0.15), transparent 24%),
        radial-gradient(circle at right, rgba(17, 104, 102, 0.16), transparent 22%),
        linear-gradient(180deg, #fbf7f1, var(--bg));
    }}
    a {{ color: inherit; text-decoration: none; }}
    .shell {{ width: min(1320px, calc(100% - 28px)); margin: 20px auto 36px; display: grid; gap: 16px; }}
    .hero, .panel {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 28px;
      box-shadow: var(--shadow);
      padding: 24px;
    }}
    .hero {{
      display: grid;
      grid-template-columns: minmax(0, 1.45fr) minmax(280px, 0.85fr);
      gap: 18px;
    }}
    .eyebrow {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(23, 56, 79, 0.08);
      color: var(--navy);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 12px;
    }}
    h1 {{
      margin: 14px 0 10px;
      font-family: Georgia, "Palatino Linotype", serif;
      font-size: clamp(34px, 5vw, 52px);
      line-height: 0.98;
      max-width: 12ch;
    }}
    h2 {{
      margin: 0;
      font-family: Georgia, "Palatino Linotype", serif;
      font-size: 22px;
    }}
    .muted, .empty {{ color: var(--muted); line-height: 1.55; }}
    .actions, .chip-row, .layout, .stack {{ display: flex; flex-wrap: wrap; gap: 10px; }}
    .layout {{ display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(300px, 0.9fr); gap: 16px; align-items: start; }}
    .stack {{ display: grid; gap: 16px; }}
    .button, .chip, .filter-chip {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 10px 14px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.7);
      font-weight: 600;
    }}
    .button.primary {{ background: var(--navy); color: #fff8ef; border-color: transparent; }}
    .chip, .filter-chip {{
      border-radius: 999px;
      font-size: 12px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.06em;
      padding: 8px 12px;
    }}
    .chip.is-active, .filter-chip.is-active {{
      background: rgba(17, 104, 102, 0.12);
      color: var(--teal);
      border-color: rgba(17, 104, 102, 0.28);
    }}
    .hero-side, .summary-card, .raw-box, .delivery-card {{
      padding: 14px 16px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.68);
    }}
    .hero-side {{ display: grid; gap: 12px; }}
    .filter-stack {{ display: grid; gap: 12px; margin-bottom: 14px; }}
    .filter-row {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }}
    .summary-card {{ display: flex; flex-direction: column; gap: 6px; }}
    pre {{
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: Consolas, "Courier New", monospace;
      font-size: 12px;
      color: var(--muted);
    }}
    @media (max-width: 980px) {{
      .hero, .layout {{ grid-template-columns: 1fr; }}
      .shell {{ width: min(100% - 16px, 1320px); }}
    }}
    {sidebar_styles}
  </style>
</head>
<body>
  <div class="page-shell">
  {sidebar}
  <main class="shell">
    <section class="hero">
      <div>
        <span class="eyebrow">Delivery History | User Workflow</span>
        <h1>Audit trail for Telegram delivery</h1>
        <p class="muted">
          This page keeps the full user-facing history of Telegram sends, suppressions, skip controls and scheduled delivery outcomes.
        </p>
        <div class="actions">
          <a class="button primary" href="/api/v1/workspace/delivery-history">Open history JSON</a>
          <a class="button" href="/workspace">Open workspace</a>
          <a class="button" href="/workspace/preferences">Preferences</a>
          <a class="button" href="/workspace/journal">Journal</a>
        </div>
      </div>
      <aside class="hero-side">
        <p>Selected root: <strong>{escape(selected_root or "all")}</strong></p>
        <p>Telegram enabled: <strong>{str(snapshot.telegram_enabled).lower()}</strong></p>
        <p>Telegram configured: <strong>{str(snapshot.telegram_configured).lower()}</strong></p>
        <p>Total events: <strong>{snapshot.delivery_activity_pagination.total_items}</strong></p>
        <p>Current page: <strong>{snapshot.delivery_activity_pagination.page} / {snapshot.delivery_activity_pagination.total_pages}</strong></p>
      </aside>
    </section>
    <section class="panel">
      <h2>Root scope</h2>
      <div class="chip-row">{''.join(root_links)}</div>
    </section>
    <section class="layout">
      <section class="panel">
        <h2>Delivery activity</h2>
        <p class="muted">The same audit trail as the workspace block, but with a longer page size and dedicated navigation.</p>
        {delivery_activity_controls}
        <div class="stack">{delivery_activity}</div>
        {delivery_activity_footer}
      </section>
      <div class="stack">
        <section class="panel">
          <h2>Grouped summary</h2>
          <div class="stack">
            <article class="summary-card"><strong>By event</strong><span>{escape(', '.join(f"{item.label} {item.count}" for item in snapshot.delivery_activity_by_event_kind[:6]) or 'none')}</span></article>
            <article class="summary-card"><strong>By root</strong><span>{escape(', '.join(f"{item.label} {item.count}" for item in snapshot.delivery_activity_by_root_scope[:6]) or 'none')}</span></article>
            <article class="summary-card"><strong>By status</strong><span>{escape(', '.join(f"{item.label} {item.count}" for item in snapshot.delivery_activity_by_status[:6]) or 'none')}</span></article>
          </div>
        </section>
        <section class="panel">
          <h2>Raw snapshot</h2>
          <div class="raw-box">
            <pre id="delivery-history-data">{payload}</pre>
          </div>
        </section>
      </div>
    </section>
  </main>
  </div>
</body>
</html>"""


def _render_workspace_preferences(
    snapshot: NotificationPreferenceWorkspaceSnapshot,
    *,
    root_context: str | None = None,
) -> str:
    sidebar = _render_page_sidebar(
        "preferences",
        root=root_context or snapshot.preferences.default_root,
        roots=snapshot.roots,
    )
    sidebar_styles = _render_page_sidebar_styles("1240px")
    preferences = snapshot.preferences
    root_options = ['<option value="">Auto root</option>']
    for root in snapshot.roots:
        selected = " selected" if preferences.default_root == root.root_code else ""
        root_options.append(f'<option value="{escape(root.root_code)}"{selected}>{escape(root.root_code)} · {escape(root.base_asset)}</option>')

    root_checks = "".join(
        (
            '<label class="check-card">'
            f'<input type="checkbox" name="subscribed_roots" value="{escape(root.root_code)}"{" checked" if root.root_code in preferences.subscribed_roots else ""}>'
            f'<span><strong>{escape(root.root_code)}</strong><small>{escape(root.base_asset)}</small></span>'
            "</label>"
        )
        for root in snapshot.roots
    )
    horizon_checks = "".join(
        (
            '<label class="check-card">'
            f'<input type="checkbox" name="subscribed_horizons" value="{escape(horizon.value)}"{" checked" if horizon in preferences.subscribed_horizons else ""}>'
            f"<span><strong>{escape(horizon.value)}</strong><small>Signal horizon</small></span>"
            "</label>"
        )
        for horizon in snapshot.available_horizons
    )
    event_checks = "".join(
        (
            '<label class="check-card">'
            f'<input type="checkbox" name="subscribed_event_kinds" value="{escape(event_kind.value)}"{" checked" if event_kind in preferences.subscribed_event_kinds else ""}>'
            f"<span><strong>{escape(event_kind.value)}</strong><small>Telegram event type</small></span>"
            "</label>"
        )
        for event_kind in NotificationEventKind
    )
    delivery_windows = _render_delivery_windows(snapshot.delivery_windows)
    delivery_activity = _render_delivery_activity(snapshot.delivery_activity)
    delivery_activity_controls = _render_delivery_activity_controls(
        base_path="/workspace/preferences",
        filters=snapshot.delivery_activity_filters,
        by_event_kind=snapshot.delivery_activity_by_event_kind,
        by_root_scope=snapshot.delivery_activity_by_root_scope,
        by_status=snapshot.delivery_activity_by_status,
    )
    delivery_activity_footer = _render_delivery_activity_footer(
        base_path="/workspace/preferences",
        export_path="/api/v1/workspace/delivery/activity/export",
        filters=snapshot.delivery_activity_filters,
        pagination=snapshot.delivery_activity_pagination,
    )
    payload = escape(json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Notification Preferences</title>
  <style>
    :root {{
      --bg: #f6f0e7;
      --paper: rgba(255, 250, 241, 0.9);
      --ink: #18222b;
      --muted: #5d6b72;
      --line: rgba(24, 34, 43, 0.1);
      --navy: #17384f;
      --teal: #116866;
      --shadow: 0 18px 46px rgba(24, 34, 43, 0.11);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      font-family: "Segoe UI", "Trebuchet MS", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(186, 112, 33, 0.16), transparent 24%),
        radial-gradient(circle at right, rgba(17, 104, 102, 0.18), transparent 22%),
        linear-gradient(180deg, #fbf7f0, var(--bg));
    }}
    a {{ color: inherit; text-decoration: none; }}
    .shell {{ width: min(1240px, calc(100% - 28px)); margin: 20px auto 36px; display: grid; gap: 16px; }}
    .hero, .panel {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 30px;
      box-shadow: var(--shadow);
      padding: 24px;
    }}
    .hero {{
      display: grid;
      grid-template-columns: minmax(0, 1.45fr) minmax(260px, 0.95fr);
      gap: 18px;
    }}
    .eyebrow {{
      display: inline-flex;
      gap: 8px;
      align-items: center;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(23, 56, 79, 0.08);
      color: var(--navy);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 12px;
    }}
    h1 {{
      margin: 14px 0 10px;
      font-family: Georgia, "Palatino Linotype", serif;
      font-size: clamp(34px, 5vw, 56px);
      line-height: 0.98;
      max-width: 11ch;
    }}
    h2 {{
      margin: 0;
      font-family: Georgia, "Palatino Linotype", serif;
      font-size: 22px;
    }}
    .muted {{ color: var(--muted); line-height: 1.55; }}
    .actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 16px;
    }}
    .button {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 12px 16px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.64);
      font-weight: 600;
      cursor: pointer;
    }}
    .button.primary {{
      background: var(--navy);
      border-color: transparent;
      color: #fff8ef;
    }}
    .hero-side {{
      display: grid;
      gap: 12px;
      padding: 18px;
      border-radius: 24px;
      background: linear-gradient(160deg, rgba(23, 56, 79, 0.96), rgba(17, 104, 102, 0.88));
      color: #f6efe5;
    }}
    .hero-side p {{ margin: 0; color: rgba(246, 239, 229, 0.84); }}
    .layout {{
      display: grid;
      grid-template-columns: minmax(0, 1.45fr) minmax(300px, 0.95fr);
      gap: 16px;
    }}
    .stack, form, .checks {{ display: grid; gap: 12px; }}
    label span {{
      display: flex;
      flex-direction: column;
      gap: 2px;
    }}
    select, input {{
      width: 100%;
      padding: 12px 14px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.85);
      color: var(--ink);
      font: inherit;
    }}
    .field {{
      display: grid;
      gap: 8px;
    }}
    .grid2 {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }}
    .check-card, .summary-card, .raw-box, .delivery-card {{
      display: flex;
      gap: 12px;
      align-items: flex-start;
      padding: 14px 16px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.68);
    }}
    .check-card input {{
      width: auto;
      margin-top: 2px;
    }}
    .status {{
      min-height: 20px;
      color: var(--teal);
      font-size: 14px;
    }}
    .filter-stack {{ display: grid; gap: 12px; margin-bottom: 14px; }}
    .filter-row {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }}
    .filter-chip {{
      display: inline-flex;
      padding: 8px 12px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.72);
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }}
    .filter-chip.is-active {{
      background: rgba(17, 104, 102, 0.12);
      color: var(--teal);
      border-color: rgba(17, 104, 102, 0.28);
    }}
    pre {{
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: Consolas, "Courier New", monospace;
      font-size: 12px;
      color: var(--muted);
    }}
    @media (max-width: 960px) {{
      .hero, .layout, .grid2 {{
        grid-template-columns: 1fr;
      }}
      .shell {{ width: min(100% - 16px, 1240px); }}
    }}
    {sidebar_styles}
  </style>
</head>
<body>
  <div class="page-shell">
  {sidebar}
  <main class="shell">
    <section class="hero">
      <div>
        <span class="eyebrow">Preferences Center | User Workflow</span>
        <h1>Control what reaches you and when</h1>
        <p class="muted">
          This page controls the single local user profile: default root, subscribed roots and horizons,
          event subscriptions, minimum priority and quiet hours for Telegram delivery.
        </p>
        <div class="actions">
          <a class="button primary" href="/api/v1/workspace/preferences">Open preferences JSON</a>
          <a class="button" href="/workspace">Back to workspace</a>
          <a class="button" href="/workspace/journal">Open journal</a>
          <a class="button" href="/workspace/delivery-history">Delivery history</a>
        </div>
      </div>
      <aside class="hero-side">
        <p>Telegram enabled: <strong>{str(snapshot.telegram_enabled).lower()}</strong></p>
        <p>Telegram configured: <strong>{str(snapshot.telegram_configured).lower()}</strong></p>
        <p>Default root: <strong>{escape(preferences.default_root or "auto")}</strong></p>
        <p>Quiet hours: <strong>{escape(preferences.quiet_hours_start or "--:--")} - {escape(preferences.quiet_hours_end or "--:--")}</strong></p>
        <p>Quiet-hours delivery: <strong>{'suppressed' if preferences.suppress_during_quiet_hours else 'allowed'}</strong></p>
      </aside>
    </section>
    <section class="layout">
      <section class="panel">
        <h2>Subscription settings</h2>
        <form id="preferences-form">
          <div class="field">
            <label for="default_root">Default root</label>
            <select id="default_root" name="default_root">
              {''.join(root_options)}
            </select>
          </div>
          <div class="field">
            <label>Subscribed roots</label>
            <div class="checks">{root_checks}</div>
          </div>
          <div class="field">
            <label>Subscribed horizons</label>
            <div class="checks">{horizon_checks}</div>
          </div>
          <div class="field">
            <label>Telegram events</label>
            <div class="checks">{event_checks}</div>
          </div>
          <div class="grid2">
            <div class="field">
              <label for="min_priority_score">Minimum priority score</label>
              <input id="min_priority_score" name="min_priority_score" type="number" min="0" max="10" value="{preferences.min_priority_score}">
            </div>
            <div class="field">
              <label for="digest_limit">Digest limit</label>
              <input id="digest_limit" name="digest_limit" type="number" min="1" max="10" value="{preferences.digest_limit}">
            </div>
            <div class="field">
              <label for="quiet_hours_start">Quiet hours start</label>
              <input id="quiet_hours_start" name="quiet_hours_start" type="time" value="{escape(preferences.quiet_hours_start or '')}">
            </div>
            <div class="field">
              <label for="quiet_hours_end">Quiet hours end</label>
              <input id="quiet_hours_end" name="quiet_hours_end" type="time" value="{escape(preferences.quiet_hours_end or '')}">
            </div>
          </div>
          <label class="check-card">
            <input type="checkbox" name="suppress_during_quiet_hours" value="true"{" checked" if preferences.suppress_during_quiet_hours else ""}>
            <span><strong>Suppress delivery during quiet hours</strong><small>Preview still works, sends are paused unless overridden.</small></span>
          </label>
          <button class="button primary" type="submit">Save preferences</button>
          <div class="status" id="preferences-status"></div>
        </form>
      </section>
      <section class="panel">
        <h2>Current summary</h2>
        <div class="stack">
          <article class="summary-card"><strong>Subscribed roots</strong><span>{escape(', '.join(preferences.subscribed_roots) or 'none')}</span></article>
          <article class="summary-card"><strong>Subscribed horizons</strong><span>{escape(', '.join(item.value for item in preferences.subscribed_horizons) or 'none')}</span></article>
          <article class="summary-card"><strong>Telegram events</strong><span>{escape(', '.join(item.value for item in preferences.subscribed_event_kinds) or 'none')}</span></article>
          <article class="summary-card"><strong>Min priority</strong><span>{preferences.min_priority_score}</span></article>
          <article class="summary-card"><strong>Digest limit</strong><span>{preferences.digest_limit}</span></article>
          <article class="summary-card"><strong>Quiet-hours policy</strong><span>{'suppress sends' if preferences.suppress_during_quiet_hours else 'allow sends'}</span></article>
        </div>
      </section>
    </section>
    <section class="panel">
      <h2>Delivery calendar</h2>
      <p class="muted">These are the next scheduler-driven Telegram windows using your saved preferences.</p>
      <div class="stack">{delivery_windows}</div>
      <div class="status" id="preferences-delivery-status"></div>
    </section>
    <section class="panel">
      <h2>Delivery activity</h2>
      <p class="muted">Recent sends, quiet-hours suppressions and manual calendar actions.</p>
      {delivery_activity_controls}
      <div class="stack">{delivery_activity}</div>
      {delivery_activity_footer}
    </section>
    <section class="panel">
      <h2>Raw snapshot</h2>
      <div class="raw-box">
        <pre id="preferences-data">{payload}</pre>
      </div>
    </section>
  </main>
  <script>
    const form = document.getElementById("preferences-form");
    const status = document.getElementById("preferences-status");
    const deliveryStatus = document.getElementById("preferences-delivery-status");
    if (form) {{
      form.addEventListener("submit", async (event) => {{
        event.preventDefault();
        const formData = new FormData(form);
        const payload = {{
          default_root: formData.get("default_root") || null,
          subscribed_roots: formData.getAll("subscribed_roots"),
          subscribed_horizons: formData.getAll("subscribed_horizons"),
          subscribed_event_kinds: formData.getAll("subscribed_event_kinds"),
          min_priority_score: Number(formData.get("min_priority_score") || 0),
          quiet_hours_start: formData.get("quiet_hours_start") || null,
          quiet_hours_end: formData.get("quiet_hours_end") || null,
          suppress_during_quiet_hours: formData.get("suppress_during_quiet_hours") === "true",
          digest_limit: Number(formData.get("digest_limit") || 3),
        }};
        if (status) {{
          status.textContent = "Saving...";
        }}
        const response = await fetch("/api/v1/workspace/preferences", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify(payload),
        }});
        if (!response.ok) {{
          if (status) {{
            status.textContent = "Preferences save failed.";
          }}
          return;
        }}
        if (status) {{
          status.textContent = "Saved. Reloading...";
        }}
        await window.__imoexRefreshPage();
      }});
    }}
    const deliverySendButtons = document.querySelectorAll(".delivery-send-now");
    const deliverySendForceButtons = document.querySelectorAll(".delivery-send-now-force");
    const deliverySkipButtons = document.querySelectorAll(".delivery-skip-next");
    const deliveryUndoButtons = document.querySelectorAll(".delivery-undo-skip");
    const runDeliveryAction = async (eventKind, ignoreQuietHours) => {{
      if (deliveryStatus) {{
        deliveryStatus.textContent = ignoreQuietHours ? "Sending with quiet-hours override..." : "Sending...";
      }}
      const response = await fetch("/api/v1/workspace/delivery/send-now", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{
          root: null,
          event_kind: eventKind,
          limit: 3,
          ignore_quiet_hours: ignoreQuietHours,
        }}),
      }});
      const payload = await response.json();
      if (!response.ok) {{
        if (deliveryStatus) {{
          deliveryStatus.textContent = "Delivery action failed.";
        }}
        return;
      }}
      if (deliveryStatus) {{
        deliveryStatus.textContent = payload.detail || payload.delivery_status || "Delivery action completed.";
      }}
      window.setTimeout(() => {{
        void window.__imoexRefreshPage();
      }}, 800);
    }};
    for (const button of deliverySendButtons) {{
      button.addEventListener("click", async () => {{
        await runDeliveryAction(button.dataset.eventKind, false);
      }});
    }}
    for (const button of deliverySendForceButtons) {{
      button.addEventListener("click", async () => {{
        await runDeliveryAction(button.dataset.eventKind, true);
      }});
    }}
    for (const button of deliverySkipButtons) {{
      button.addEventListener("click", async () => {{
        const eventKind = button.dataset.eventKind;
        if (deliveryStatus) {{
          deliveryStatus.textContent = "Updating next run...";
        }}
        const response = await fetch("/api/v1/workspace/delivery/skip-next", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ event_kind: eventKind }}),
        }});
        if (!response.ok) {{
          if (deliveryStatus) {{
            deliveryStatus.textContent = "Skip-next action failed.";
          }}
          return;
        }}
        if (deliveryStatus) {{
          deliveryStatus.textContent = "Next run updated. Reloading...";
        }}
        window.setTimeout(() => {{
          void window.__imoexRefreshPage();
        }}, 600);
      }});
    }}
    for (const button of deliveryUndoButtons) {{
      button.addEventListener("click", async () => {{
        const eventKind = button.dataset.eventKind;
        if (deliveryStatus) {{
          deliveryStatus.textContent = "Undoing skip...";
        }}
        const response = await fetch("/api/v1/workspace/delivery/undo-skip", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ event_kind: eventKind }}),
        }});
        if (!response.ok) {{
          if (deliveryStatus) {{
            deliveryStatus.textContent = "Undo-skip action failed.";
          }}
          return;
        }}
        if (deliveryStatus) {{
          deliveryStatus.textContent = "Skip removed. Reloading...";
        }}
        window.setTimeout(() => {{
          void window.__imoexRefreshPage();
        }}, 600);
      }});
    }}
  </script>
  </main>
  </div>
</body>
</html>"""


def _render_signal_workspace(snapshot: WorkspaceSignalSnapshot, *, language: str) -> str:
    signal = snapshot.signal
    sidebar = _render_page_sidebar("signal", root=signal.root, roots=snapshot.roots, signal_id=signal.signal_id)
    sidebar_styles = _render_page_sidebar_styles("1280px")
    root_details = snapshot.root_details
    visual = snapshot.visual
    journal_rows = "".join(_render_journal_entry(item) for item in signal.journal_entries) or '<p class="empty">No journal entries yet.</p>'
    related = "".join(_render_related_signal(item) for item in snapshot.related_signals) or '<p class="empty">No related signals available right now.</p>'
    metric_bars = _render_metric_bars(visual.metric_bars, compact=False)
    timeline = _render_timeline(visual.timeline, compact=False)
    horizon_pulse = _render_horizon_pulse(visual.horizon_pulse)
    drivers = "".join(f"<li>{escape(item)}</li>" for item in signal.drivers) or "<li>No drivers recorded yet.</li>"
    objections = "".join(f"<li>{escape(item)}</li>" for item in signal.objections) or "<li>No objections recorded yet.</li>"
    invalidations = "".join(f"<li>{escape(item)}</li>" for item in signal.invalidation_conditions) or "<li>No invalidation conditions recorded yet.</li>"
    data_sources = "".join(f"<li>{escape(item)}</li>" for item in signal.data_sources) or "<li>No explicit data sources recorded yet.</li>"
    resolution_block = '<p class="empty">Signal is still active; no resolution record yet.</p>'
    if signal.resolution is not None:
        resolution_block = (
            '<article class="resolution-card">'
            f'<strong>{escape(signal.resolution.outcome.value)} | {escape(signal.resolution.status.value)}</strong>'
            f'<p class="muted">Resolved at {escape(_format_timestamp(signal.resolution.resolved_at))} | return {signal.resolution.realized_return_bps:.1f} bps</p>'
            f'<p class="muted">{escape(signal.resolution.resolution_note)}</p>'
            f'<p class="muted">{escape(signal.resolution.post_mortem_summary)}</p>'
            "</article>"
        )

    context_band = ""
    if root_details is not None:
        market_data_context = _render_market_data_context(snapshot.control_panel)
        expiry_summary = _format_expiry_countdown(
            root_details.continuous_series.days_to_expiry,
            root_details.continuous_series.expiry_date,
            language=language,
        )
        context_band = (
            '<section class="band-grid">'
            f'<article><span>Session</span><strong>{escape(root_details.session.session_type.value)}</strong><p class="muted">Trading day {escape(root_details.session.trading_day.isoformat())}</p></article>'
            f'<article><span>Contract state</span><strong>{escape(root_details.continuous_series.active_contract)}</strong><p class="muted">Next {escape(root_details.continuous_series.next_contract)} | roll {root_details.continuous_series.next_contract_share:.0%}</p></article>'
            f'<article><span>Days To Expiry</span><strong>{escape(expiry_summary)}</strong><p class="muted">Until contract expiry</p></article>'
            f'<article><span>Universe</span><strong>{escape(root_details.root.universe_status.value)}</strong><p class="muted">Liquidity rank {root_details.root.liquidity_rank}</p></article>'
            f'<article><span>Evaluation</span><strong>{snapshot.evaluation.resolved_signals}</strong><p class="muted">Resolved signals | Brier {_format_optional(snapshot.evaluation.brier_score)}</p></article>'
            f"{market_data_context}"
            "</section>"
        )

    payload = escape(json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False))
    telegram_preview = escape(snapshot.telegram_preview_message or "Telegram preview is not available.")
    workflow_panel = _render_workflow_panel(signal, status_id="signal-workflow-status")
    trust_ribbon = _render_trust_ribbon(snapshot.trust_ribbon)
    diff_block = _render_signal_diff(snapshot.signal_diff)
    confidence_block = _render_confidence_decomposition(snapshot.confidence_decomposition)
    decision_log = _render_decision_timeline(snapshot.decision_log, title="Decision log")
    similar_setups = _render_similar_setups(snapshot.similar_setups)
    market_panel = _render_market_snapshot(snapshot.market_snapshot, language=language)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Signal {escape(signal.signal_id)}</title>
  <style>
    :root {{
      --bg: #f5efe6;
      --paper: rgba(255, 250, 242, 0.9);
      --ink: #15202a;
      --muted: #5c6970;
      --line: rgba(21, 32, 42, 0.1);
      --navy: #17364d;
      --teal: #116966;
      --amber: #bb7122;
      --red: #b44a3d;
      --green: #2f7e57;
      --shadow: 0 18px 46px rgba(21, 32, 42, 0.11);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      font-family: "Segoe UI", "Trebuchet MS", sans-serif;
      background:
        radial-gradient(circle at left top, rgba(187, 113, 34, 0.16), transparent 24%),
        radial-gradient(circle at right, rgba(17, 105, 102, 0.18), transparent 22%),
        linear-gradient(180deg, #fbf7f1, var(--bg));
    }}
    a {{ color: inherit; text-decoration: none; }}
    .shell {{ width: min(1280px, calc(100% - 28px)); margin: 20px auto 36px; display: grid; gap: 16px; }}
    .hero, .panel {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 30px;
      box-shadow: var(--shadow);
      padding: 24px;
    }}
    .hero {{
      display: grid;
      grid-template-columns: minmax(0, 1.45fr) minmax(280px, 0.9fr);
      gap: 18px;
    }}
    .eyebrow {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(23, 54, 77, 0.08);
      color: var(--navy);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 12px;
    }}
    h1 {{
      margin: 14px 0 10px;
      font-family: Georgia, "Palatino Linotype", serif;
      font-size: clamp(34px, 5vw, 54px);
      line-height: 0.98;
      max-width: 11ch;
    }}
    h2 {{
      margin: 0;
      font-family: Georgia, "Palatino Linotype", serif;
      font-size: 22px;
    }}
    h3 {{ margin: 0 0 10px; font-size: 16px; }}
    .muted, .empty {{ color: var(--muted); line-height: 1.55; }}
    .hero-actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 18px;
    }}
    .button {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 12px 16px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.64);
      font-weight: 600;
      cursor: pointer;
    }}
    .button.primary {{
      background: var(--navy);
      border-color: transparent;
      color: #fff8ef;
    }}
    .hero-side {{
      display: grid;
      gap: 12px;
      padding: 18px;
      border-radius: 24px;
      background: linear-gradient(160deg, rgba(23, 54, 77, 0.96), rgba(17, 105, 102, 0.88));
      color: #f6efe5;
    }}
    .hero-side p, .hero-side small {{ color: rgba(246, 239, 229, 0.84); line-height: 1.5; }}
    .metric-grid, .band-grid, .split, .layout, .stack, .list, .timeline-list, .visual-grid, .horizon-grid {{
      display: grid;
      gap: 12px;
    }}
    .layout {{
      grid-template-columns: minmax(0, 1.45fr) minmax(320px, 0.95fr);
      gap: 16px;
    }}
    .metric-grid {{
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    }}
    .metric-grid article, .band-grid article, .resolution-card, .journal-entry, .related-card, .telegram-box, .raw-box, .thesis-card {{
      padding: 14px 16px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.68);
    }}
    .metric-grid span, .band-grid span {{
      display: block;
      margin-bottom: 8px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 11px;
    }}
    .metric-grid strong, .band-grid strong {{ font-size: 20px; }}
    .band-grid {{
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    }}
    .split {{
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }}
    .thesis-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
    }}
    .thesis-card ul {{
      margin: 0;
      padding-left: 18px;
      color: var(--muted);
      line-height: 1.55;
    }}
    .journal-entry strong, .related-card strong {{ display: block; margin-bottom: 6px; }}
    .journal-entry small {{ color: var(--muted); display: block; margin-bottom: 8px; }}
    form {{ display: grid; gap: 10px; }}
    select, input, textarea {{
      width: 100%;
      padding: 12px 14px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.85);
      color: var(--ink);
      font: inherit;
    }}
    textarea {{ min-height: 120px; resize: vertical; }}
    .status {{ min-height: 20px; color: var(--teal); font-size: 14px; }}
    .metric-bar {{
      padding: 12px 14px;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.68);
    }}
    .metric-bar-head {{
      display: flex;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 8px;
      font-size: 13px;
    }}
    .metric-bar-track {{
      width: 100%;
      height: 10px;
      border-radius: 999px;
      background: rgba(21, 32, 42, 0.08);
      overflow: hidden;
    }}
    .metric-bar-fill {{
      height: 100%;
      border-radius: 999px;
      background: linear-gradient(90deg, var(--navy), var(--teal));
    }}
    .metric-bar-fill.tone-positive {{ background: linear-gradient(90deg, #2f7e57, #59a570); }}
    .metric-bar-fill.tone-warning {{ background: linear-gradient(90deg, #bb7122, #db9a45); }}
    .metric-bar-fill.tone-negative {{ background: linear-gradient(90deg, #b44a3d, #df6f5f); }}
    .timeline-item {{
      position: relative;
      padding: 12px 14px 12px 30px;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.68);
    }}
    .timeline-item::before {{
      content: "";
      position: absolute;
      left: 13px;
      top: 18px;
      width: 8px;
      height: 8px;
      border-radius: 999px;
      background: var(--navy);
    }}
    .timeline-item.tone-positive::before {{ background: #2f7e57; }}
    .timeline-item.tone-warning::before {{ background: #bb7122; }}
    .timeline-item.tone-negative::before {{ background: #b44a3d; }}
    .horizon-grid {{
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    }}
    .horizon-card {{
      padding: 14px 16px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.68);
    }}
    .horizon-card strong {{
      display: block;
      margin-bottom: 6px;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 7px 10px;
      border-radius: 999px;
      background: rgba(17, 105, 102, 0.08);
      color: var(--teal);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 12px;
    }}
    .workflow-chip {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 7px 10px;
      border-radius: 999px;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      background: rgba(23, 54, 77, 0.1);
      color: var(--navy);
    }}
    .workflow-chip.tone-review {{
      background: rgba(187, 113, 34, 0.16);
      color: var(--amber);
    }}
    .workflow-chip.tone-ignore {{
      background: rgba(92, 105, 112, 0.16);
      color: var(--muted);
    }}
    .workflow-chip.tone-escalate {{
      background: rgba(180, 74, 61, 0.16);
      color: var(--red);
    }}
    .workflow-panel {{
      display: grid;
      gap: 12px;
      padding: 14px 16px;
      border-radius: 18px;
      border: 1px solid rgba(246, 239, 229, 0.18);
      background: rgba(255, 255, 255, 0.1);
    }}
    .workflow-meta {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: flex-start;
    }}
    .workflow-meta span {{
      display: block;
      margin-bottom: 6px;
      color: rgba(246, 239, 229, 0.72);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 11px;
    }}
    .workflow-summary {{
      margin: 0;
      color: rgba(246, 239, 229, 0.82);
      line-height: 1.5;
    }}
    .workflow-actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .workflow-button {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 10px 12px;
      border-radius: 12px;
      border: 1px solid rgba(246, 239, 229, 0.18);
      background: rgba(255, 255, 255, 0.12);
      color: #f6efe5;
      font: inherit;
      font-weight: 600;
      cursor: pointer;
    }}
    .workflow-button:disabled {{
      opacity: 0.55;
      cursor: not-allowed;
    }}
    .workflow-button.is-active {{
      border-color: transparent;
      color: #fff8ef;
    }}
    .workflow-button.tone-watch.is-active {{
      background: rgba(246, 239, 229, 0.18);
    }}
    .workflow-button.tone-review.is-active {{
      background: var(--amber);
    }}
    .workflow-button.tone-ignore.is-active {{
      background: rgba(92, 105, 112, 0.92);
    }}
    .workflow-button.tone-escalate.is-active {{
      background: var(--red);
    }}
    .workflow-button.tone-ready.is-active {{
      background: rgba(17, 104, 102, 0.92);
    }}
    .workflow-button.tone-resolved.is-active {{
      background: rgba(23, 56, 79, 0.92);
    }}
    pre {{
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: Consolas, "Courier New", monospace;
      font-size: 12px;
      color: var(--muted);
    }}
    @media (max-width: 1040px) {{
      .hero, .layout, .split, .thesis-grid {{
        grid-template-columns: 1fr;
      }}
      .shell {{ width: min(100% - 16px, 1280px); }}
    }}
    {sidebar_styles}
  </style>
</head>
<body>
  <div class="page-shell">
  {sidebar}
  <main class="shell">
    <section class="hero">
      <div>
        <span class="eyebrow">Signal Detail | User Workflow</span>
        <h1>{escape(signal.root)} {escape(signal.contract)}</h1>
        <p class="muted">{escape(signal.summary)}</p>
        <div class="hero-actions">
          <a class="button primary" href="/workspace?root={escape(signal.root)}&signal_id={escape(signal.signal_id)}">Back to workspace</a>
          <a class="button" href="/workspace/preferences">Preferences</a>
          <a class="button" href="/api/v1/workspace/signals/{escape(signal.signal_id)}">Open page JSON</a>
          <a class="button" href="/api/v1/signals/{escape(signal.signal_id)}">Open signal API</a>
          <a class="button" href="/api/v1/roots/{escape(signal.root)}/deep-dive">Open deep-dive</a>
        </div>
      </div>
      <aside class="hero-side">
        <div>
          <h2>{escape(signal.direction_final.value)} | {escape(signal.horizon.value)}</h2>
          <p><strong>{escape(signal.skeptic_verdict.value)}</strong></p>
          <small>Signal id: {escape(signal.signal_id)}</small>
        </div>
        <div class="metric-grid">
          <article><span>Confidence</span><strong>{signal.confidence_final:.2f}</strong></article>
          <article><span>Skeptic</span><strong>{signal.skeptic_score:.2f}</strong></article>
          <article><span>Priority</span><strong>{signal.priority_score}</strong></article>
          <article><span>Status</span><strong>{escape(signal.status.value)}</strong></article>
          <article><span>Workflow</span><strong>{escape(_workflow_state_label(signal.workflow_state))}</strong></article>
        </div>
        {workflow_panel}
      </aside>
    </section>
    {trust_ribbon}
    <section class="layout">
      <div class="stack">
        {diff_block}
        {confidence_block}
      </div>
      <div class="stack">
        {similar_setups}
      </div>
    </section>
    {context_band}
    {market_panel}
    <section class="layout">
      <div class="stack">
        <section class="panel">
          <h2>Probability map</h2>
          <div class="metric-grid">
            <article><span>Up</span><strong>{signal.probability_up:.2f}</strong></article>
            <article><span>Down</span><strong>{signal.probability_down:.2f}</strong></article>
            <article><span>No edge</span><strong>{signal.probability_no_edge:.2f}</strong></article>
            <article><span>Freshness</span><strong>{signal.freshness_score:.2f}</strong></article>
            <article><span>Roll risk</span><strong>{signal.roll_risk:.2f}</strong></article>
            <article><span>Expiry risk</span><strong>{signal.expiry_risk:.2f}</strong></article>
          </div>
        </section>
        <section class="panel">
          <h2>Signal chart</h2>
          <div class="visual-grid">{metric_bars}</div>
        </section>
        <section class="panel">
          <h2>Horizon pulse</h2>
          <p class="muted">Same root across horizons, using point-in-time features and active signal probabilities.</p>
          <div class="horizon-grid">{horizon_pulse}</div>
        </section>
        <section class="panel">
          <h2>Decision anatomy</h2>
          <div class="thesis-grid">
            <article class="thesis-card">
              <h3>Drivers</h3>
              <ul>{drivers}</ul>
            </article>
            <article class="thesis-card">
              <h3>Objections</h3>
              <ul>{objections}</ul>
            </article>
            <article class="thesis-card">
              <h3>Invalidation</h3>
              <ul>{invalidations}</ul>
            </article>
            <article class="thesis-card">
              <h3>Data sources</h3>
              <ul>{data_sources}</ul>
            </article>
          </div>
        </section>
        <section class="panel">
          <h2>Resolution</h2>
          {resolution_block}
        </section>
        <section class="panel">
          <h2>Lifecycle timeline</h2>
          <div class="timeline-list">{timeline}</div>
        </section>
        {decision_log}
        <section class="panel">
          <div style="display:flex;justify-content:space-between;gap:12px;align-items:baseline;margin-bottom:16px;">
            <h2>Journal</h2>
            <p class="muted">Capture what changed around this exact signal.</p>
          </div>
          <div class="list">{journal_rows}</div>
          <div style="display:flex;justify-content:space-between;gap:12px;align-items:baseline;margin:18px 0 12px;">
            <h2>Quick capture</h2>
            <p class="muted">Writes directly to the signal journal.</p>
          </div>
          <form id="signal-journal-form" data-signal-id="{escape(signal.signal_id)}">
            <select name="kind">
              <option value="thesis">Thesis</option>
              <option value="risk_note">Risk note</option>
              <option value="execution_note">Execution note</option>
              <option value="post_mortem">Post-mortem</option>
              <option value="invalidation_breach">Invalidation breach</option>
              <option value="data_anomaly">Data anomaly</option>
            </select>
            <input type="text" name="title" placeholder="Short title">
            <textarea name="note" placeholder="What changed, what risk you see, and what should be watched next."></textarea>
            <button class="button primary" type="submit">Save journal note</button>
            <div class="status" id="signal-journal-status"></div>
          </form>
        </section>
      </div>
      <div class="stack">
        <section class="panel">
          <h2>Telegram brief</h2>
          <p class="muted">{'Ready to send.' if snapshot.telegram_delivery_ready else 'Preview available even if delivery is not configured yet.'}</p>
          <div class="telegram-box">
            <pre>{telegram_preview}</pre>
          </div>
        </section>
        <section class="panel">
          <h2>Related signals</h2>
          <div class="list">{related}</div>
        </section>
        <section class="panel">
          <h2>Raw snapshot</h2>
          <div class="raw-box">
            <pre id="signal-page-data">{payload}</pre>
          </div>
        </section>
      </div>
    </section>
  </main>
  </div>
  <script>
    const journalForm = document.getElementById("signal-journal-form");
    const journalStatus = document.getElementById("signal-journal-status");
    if (journalForm) {{
      journalForm.addEventListener("submit", async (event) => {{
        event.preventDefault();
        const signalId = journalForm.dataset.signalId;
        const formData = new FormData(journalForm);
        const payload = {{
          kind: formData.get("kind"),
          title: formData.get("title"),
          note: formData.get("note"),
          author: "signal-page",
        }};
        if (!payload.title || !payload.note) {{
          if (journalStatus) {{
            journalStatus.textContent = "Title and note are required.";
          }}
          return;
        }}
        if (journalStatus) {{
          journalStatus.textContent = "Saving...";
        }}
        const response = await fetch(`/api/v1/journal/${{signalId}}`, {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify(payload),
        }});
        if (!response.ok) {{
          if (journalStatus) {{
            journalStatus.textContent = "Journal save failed.";
          }}
          return;
        }}
        if (journalStatus) {{
          journalStatus.textContent = "Saved. Reloading...";
        }}
        await window.__imoexRefreshPage();
      }});
    }}
    const workflowStatus = document.getElementById("signal-workflow-status");
    const workflowButtons = document.querySelectorAll(".workflow-button[data-signal-id]");
    for (const button of workflowButtons) {{
      button.addEventListener("click", async () => {{
        const signalId = button.dataset.signalId;
        const workflowState = button.dataset.workflowState;
        if (!signalId || !workflowState) {{
          return;
        }}
        if (workflowStatus) {{
          workflowStatus.textContent = "Updating workflow...";
        }}
        const response = await fetch(`/api/v1/signals/${{signalId}}/workflow-state`, {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ workflow_state: workflowState }}),
        }});
        if (!response.ok) {{
          if (workflowStatus) {{
            workflowStatus.textContent = "Workflow update failed.";
          }}
          return;
        }}
        if (workflowStatus) {{
          workflowStatus.textContent = "Workflow updated. Refreshing...";
        }}
        await window.__imoexRefreshPage();
      }});
    }}
  </script>
</body>
</html>"""


def _workflow_state_label(state: SignalWorkflowState) -> str:
    labels = {
        SignalWorkflowState.WATCHING: "watching",
        SignalWorkflowState.VALIDATING: "validating",
        SignalWorkflowState.READY: "ready",
        SignalWorkflowState.IGNORED: "ignored",
        SignalWorkflowState.ESCALATE: "escalated",
        SignalWorkflowState.RESOLVED: "resolved",
    }
    return labels.get(state, state.value)


def _workflow_state_tone(state: SignalWorkflowState) -> str:
    tones = {
        SignalWorkflowState.WATCHING: "watch",
        SignalWorkflowState.VALIDATING: "review",
        SignalWorkflowState.READY: "ready",
        SignalWorkflowState.IGNORED: "ignore",
        SignalWorkflowState.ESCALATE: "escalate",
        SignalWorkflowState.RESOLVED: "resolved",
    }
    return tones.get(state, "watch")


def _workflow_state_hint(state: SignalWorkflowState) -> str:
    hints = {
        SignalWorkflowState.WATCHING: "Keep this setup in view and wait for stronger confirmation.",
        SignalWorkflowState.VALIDATING: "Manually verify the setup before taking action.",
        SignalWorkflowState.READY: "The setup is actionable; manage it closely.",
        SignalWorkflowState.IGNORED: "This signal is deprioritized until the context changes.",
        SignalWorkflowState.ESCALATE: "This signal needs a higher-attention review right now.",
        SignalWorkflowState.RESOLVED: "The setup is closed and should now feed the review loop.",
    }
    return hints.get(state, "Manual workflow state for the current signal.")


def _render_workflow_chip(signal) -> str:
    state = getattr(signal, "workflow_state", SignalWorkflowState.WATCHING)
    tone = _workflow_state_tone(state)
    label = _workflow_state_label(state)
    return f'<span class="workflow-chip tone-{escape(tone)}">{escape(label)}</span>'


def _render_workflow_panel(signal, *, status_id: str) -> str:
    if signal is None:
        buttons = "".join(
            f'<button class="workflow-button tone-{escape(_workflow_state_tone(state))}" type="button" disabled>{escape(_workflow_state_label(state))}</button>'
            for state in SignalWorkflowState
        )
        return (
            '<div class="workflow-panel">'
            '<div class="workflow-meta">'
            '<div><span>Workflow</span><strong>Pick a signal first</strong></div>'
            "</div>"
            '<p class="workflow-summary">Select a signal to set how you want to handle it.</p>'
            f'<div class="workflow-actions">{buttons}</div>'
            f'<div class="status" id="{escape(status_id)}"></div>'
            "</div>"
        )

    state = signal.workflow_state
    buttons = []
    for candidate in SignalWorkflowState:
        tone = _workflow_state_tone(candidate)
        active = " is-active" if candidate == state else ""
        buttons.append(
            f'<button class="workflow-button tone-{escape(tone)}{active}" '
            f'type="button" data-workflow-state="{escape(candidate.value)}" data-signal-id="{escape(signal.signal_id)}">'
            f"{escape(_workflow_state_label(candidate))}"
            "</button>"
        )
    return (
        '<div class="workflow-panel">'
        '<div class="workflow-meta">'
        f'<div><span>Workflow</span><strong>{escape(_workflow_state_label(state))}</strong></div>'
        f"{_render_workflow_chip(signal)}"
        "</div>"
        f'<p class="workflow-summary">{escape(_workflow_state_hint(state))}</p>'
        f'<div class="workflow-actions">{"".join(buttons)}</div>'
        f'<div class="status" id="{escape(status_id)}"></div>'
        "</div>"
    )


def _render_root_pulse_card(item, *, selected_root: str, language: str) -> str:
    price_line = f"{item.active_signals} active | roll {item.next_contract_share:.0%}"
    if item.current_price is not None:
        unit = f" {escape(item.price_unit)}" if item.price_unit else ""
        price_line = (
            f"L {_format_price_value(item.current_price)}{unit} | "
            f"D {_format_signed_pct(item.price_change_pct)} | "
            f"{item.active_signals} active | roll {item.next_contract_share:.0%}"
        )
    copy = {
        "open": "Открыть" if language == "ru" else "Open",
        "preview_ready": "Выберите таймфрейм" if language == "ru" else "Pick a timeframe",
        "preview_note": "Быстрый просмотр свечей без перехода" if language == "ru" else "Quick candle preview without navigation",
        "pin_a": "Серия A" if language == "ru" else "Root A",
        "pin_b": "Серия B" if language == "ru" else "Root B",
    }
    preview_buttons = "".join(
        (
            f'<button class="rail-preview-button{" is-active" if timeframe == "1D" else ""}" '
            f'type="button" data-root-preview-button data-root-code="{escape(item.root_code)}" '
            f'data-timeframe="{timeframe}">{timeframe}</button>'
        )
        for timeframe in ("1D", "1W", "1M")
    )
    return (
        f'<article class="rail-card tone-{escape(item.tone)}{" is-active" if item.root_code == selected_root else ""}" '
        f'data-root-preview-card data-root-code="{escape(item.root_code)}">'
        f'<a class="rail-card-link" href="/workspace?root={escape(item.root_code)}">'
        f"<strong>{escape(item.root_code)}</strong>"
        f"<span>{escape(item.base_asset)}</span>"
        f"<small>{escape(item.headline)}</small>"
        f"<em>{price_line}</em>"
        "</a>"
        '<div class="rail-card-footer">'
        f'<div class="rail-card-tabs">{preview_buttons}</div>'
        f'<a class="rail-open-link" href="/workspace?root={escape(item.root_code)}">{escape(copy["open"])}</a>'
        "</div>"
        f'<div class="rail-preview-popover" hidden data-root-preview-popover data-root-code="{escape(item.root_code)}">'
        '<div class="rail-preview-head">'
        f'<strong>{escape(item.root_code)} · <span data-root-preview-label>1D</span></strong>'
        f'<small data-root-preview-updated>{escape(copy["preview_ready"])}</small>'
        "</div>"
        f'<div class="rail-preview-chart" data-root-preview-chart><div class="empty">{escape(copy["preview_note"])}</div></div>'
        f'<div class="rail-preview-meta" data-root-preview-meta>{escape(price_line)}</div>'
        '<div class="signal-preview-actions">'
        f'<button class="preview-pin-button" type="button" data-pin-root-preview data-root-code="{escape(item.root_code)}" data-compare-slot="a" data-timeframe="1D">{escape(copy["pin_a"])}</button>'
        f'<button class="preview-pin-button" type="button" data-pin-root-preview data-root-code="{escape(item.root_code)}" data-compare-slot="b" data-timeframe="1D">{escape(copy["pin_b"])}</button>'
        f'<a class="rail-open-link" href="/workspace?root={escape(item.root_code)}">{escape(copy["open"])}</a>'
        "</div>"
        "</div>"
        "</article>"
    )


def _render_market_snapshot(snapshot, *, language: str) -> str:
    if snapshot is None:
        return ""

    copy = {
        "title": "Текущая цена и графики" if language == "ru" else "Current price and charts",
        "subtitle": (
            "По выбранному инструменту: текущая цена и три масштаба просмотра без переключения страниц."
            if language == "ru"
            else "Current price plus day, week, and month views for the selected instrument."
        ),
        "current_price": "Последняя цена" if language == "ru" else "Last",
        "daily_change": "Дневное изменение" if language == "ru" else "Daily change",
        "day_high": "Дневной максимум" if language == "ru" else "Day high",
        "day_low": "Дневной минимум" if language == "ru" else "Day low",
        "updated": "Обновлено" if language == "ru" else "Updated",
        "source": "Источник" if language == "ru" else "Source",
        "warning_title": "Поток цены требует внимания" if language == "ru" else "Price feed needs attention",
        "warning_body": (
            "Данные выглядят несвежими или деградировавшими, поэтому цену стоит читать с осторожностью."
            if language == "ru"
            else "The feed looks stale or degraded, so treat the displayed price with caution."
        ),
        "status": "Статус" if language == "ru" else "Status",
    }
    unit = f" {escape(snapshot.unit)}" if snapshot.unit else ""
    tone = _market_status_tone(snapshot.status)
    warning = ""
    if tone != "positive":
        warning_detail = snapshot.status_detail or copy["warning_body"]
        warning = (
            '<div class="metric-list" style="margin-bottom:12px;">'
            f'<article class="action-card tone-{tone}">'
            f'<strong>{escape(copy["warning_title"])}</strong>'
            f'<p class="muted">{escape(_market_status_label(snapshot.status, language=language))} | {escape(warning_detail)}</p>'
            "</article>"
            "</div>"
        )
    charts = "".join(
        _render_market_chart_card(series, unit=snapshot.unit, language=language)
        for series in (snapshot.daily, snapshot.weekly, snapshot.monthly)
    )
    return (
        '<section class="panel">'
        '<div class="panel-head">'
        f'<h2>{escape(copy["title"])}</h2>'
        f'<p>{escape(copy["subtitle"])}</p>'
        "</div>"
        f"{warning}"
        '<div class="metric-list" style="grid-template-columns:repeat(auto-fit,minmax(180px,1fr));">'
        f'<article><span>{escape(copy["current_price"])}</span><strong>{_format_price_value(snapshot.current_price)}{unit}</strong><p class="muted">{escape(snapshot.root_code)} · {escape(snapshot.contract)}</p></article>'
        f'<article><span>{escape(copy["daily_change"])}</span><strong>{_format_signed_value(snapshot.price_change_abs)}{unit}</strong><p class="muted">{_format_signed_pct(snapshot.price_change_pct)}</p></article>'
        f'<article><span>{escape(copy["day_high"])}</span><strong>{_format_price_value(snapshot.daily.high_price)}{unit}</strong><p class="muted">{escape(snapshot.daily.points[-1].label if snapshot.daily.points else snapshot.contract)}</p></article>'
        f'<article><span>{escape(copy["day_low"])}</span><strong>{_format_price_value(snapshot.daily.low_price)}{unit}</strong><p class="muted">{escape(snapshot.daily.points[0].label if snapshot.daily.points else snapshot.contract)}</p></article>'
        f'<article><span>{escape(copy["updated"])}</span><strong>{escape(_format_timestamp(snapshot.as_of))}</strong><p class="muted">{escape(copy["status"])}: {escape(_market_status_label(snapshot.status, language=language))}</p></article>'
        f'<article><span>{escape(copy["source"])}</span><strong>{escape(snapshot.price_source)}</strong><p class="muted">{escape(snapshot.base_asset)}</p></article>'
        "</div>"
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin-top:16px;">'
        f"{charts}"
        "</div>"
        "</section>"
    )


def _render_market_chart_card(series, *, unit: str, language: str) -> str:
    if not series.points:
        return ""
    chart_labels = {
        "1D": "День" if language == "ru" else "Day",
        "1W": "Неделя" if language == "ru" else "Week",
        "1M": "Месяц" if language == "ru" else "Month",
    }
    label = chart_labels.get(series.label, series.label)
    low = min(point.low for point in series.points)
    high = max(point.high for point in series.points)
    span = max(high - low, 0.0001)
    width = 220.0
    height = 92.0
    tone = "#2f7e57" if series.change_abs >= 0 else "#b44a3d"
    unit_suffix = f" {escape(unit)}" if unit else ""
    first_label = escape(series.points[0].label)
    last_label = escape(series.points[-1].label)
    range_label = "Диапазон" if language == "ru" else "Range"
    open_label = "Открытие" if language == "ru" else "Open"
    close_label = "Закрытие" if language == "ru" else "Close"
    change_label = "Изменение" if language == "ru" else "Change"
    candles: list[str] = []
    body_width = max(6.0, min(16.0, width / max(len(series.points) * 1.9, 1)))

    def _map_price_y(value: float) -> float:
        return height - (((value - low) / span) * (height - 14.0)) - 7.0

    for index, point in enumerate(series.points):
        x = width / 2 if len(series.points) == 1 else (index / float(len(series.points) - 1)) * width
        open_y = _map_price_y(point.open)
        close_y = _map_price_y(point.close)
        high_y = _map_price_y(point.high)
        low_y = _map_price_y(point.low)
        body_top = min(open_y, close_y)
        body_height = max(abs(close_y - open_y), 3.0)
        candle_tone = "#2f7e57" if point.close >= point.open else "#b44a3d"
        candles.append(
            f'<line x1="{x:.1f}" y1="{high_y:.1f}" x2="{x:.1f}" y2="{low_y:.1f}" '
            f'stroke="{candle_tone}" stroke-width="1.8" stroke-linecap="round"></line>'
            f'<rect x="{(x - (body_width / 2)):.1f}" y="{body_top:.1f}" width="{body_width:.1f}" '
            f'height="{body_height:.1f}" rx="2" fill="{candle_tone}" fill-opacity="0.92"></rect>'
        )
    return (
        '<article style="padding:14px 16px;border-radius:18px;border:1px solid rgba(21, 32, 42, 0.1);background:rgba(255,255,255,0.72);display:grid;gap:10px;">'
        '<div style="display:flex;justify-content:space-between;gap:12px;align-items:baseline;">'
        f'<strong>{escape(label)} · {escape(series.label)}</strong>'
        f'<span style="font-weight:700;color:{tone};">{_format_price_value(series.current_price)}{unit_suffix}</span>'
        "</div>"
        f'<svg viewBox="0 0 220 92" preserveAspectRatio="none" style="width:100%;height:92px;border-radius:14px;background:linear-gradient(180deg, rgba(15,108,103,0.06), rgba(255,255,255,0.6));">'
        f'<line x1="0" y1="{_map_price_y(series.open_price):.1f}" x2="220" y2="{_map_price_y(series.open_price):.1f}" stroke="rgba(21,32,42,0.08)" stroke-width="1" stroke-dasharray="4 4"></line>'
        f'{"".join(candles)}'
        "</svg>"
        '<div style="display:flex;justify-content:space-between;gap:8px;font-size:12px;color:#5c6970;">'
        f"<span>{first_label}</span><span>{last_label}</span>"
        "</div>"
        f'<p class="muted">{escape(open_label)} {_format_price_value(series.open_price)}{unit_suffix} | {escape(close_label)} {_format_price_value(series.current_price)}{unit_suffix} | {escape(change_label)} {_format_signed_value(series.change_abs)}{unit_suffix} ({_format_signed_pct(series.change_pct)})</p>'
        f'<p class="muted">{escape(range_label)} {_format_price_value(series.low_price)}{unit_suffix} - {_format_price_value(series.high_price)}{unit_suffix}</p>'
        "</article>"
    )


def _render_trust_ribbon(ribbon) -> str:
    items = "".join(
        f'<article class="action-card tone-{escape(item.tone)}"><strong>{escape(item.label)}</strong><p class="muted">{escape(item.value)} | {escape(item.detail or "")}</p></article>'
        for item in ribbon.items
    )
    return (
        '<section class="panel">'
        '<div class="panel-head">'
        '<h2>Trust ribbon</h2>'
        f'<p>{escape(ribbon.headline)}</p>'
        "</div>"
        f'<div class="action-list">{items}</div>'
        "</section>"
    )


def _render_watchlist(items) -> str:
    body = "".join(
        f'<article><strong>{escape(item.root_code)}</strong><p class="muted">{escape(item.note or (item.signal.summary if item.signal is not None else "Root-level watch item"))}</p></article>'
        for item in items
    ) or '<p class="empty">No watchlist entries yet.</p>'
    return (
        '<section class="panel">'
        '<div class="panel-head">'
        '<h2>Watchlist</h2>'
        '<p>Promoted roots and signals stay visible between cycles.</p>'
        "</div>"
        f'<div class="metric-list">{body}</div>'
        "</section>"
    )


def _render_horizon_comparison(snapshot) -> str:
    if snapshot is None:
        return (
            '<section class="panel">'
            '<div class="panel-head"><h2>Horizon compare</h2><p>No horizon comparison is available yet.</p></div>'
            "</section>"
        )
    rows = "".join(
        (
            "<article>"
            f"<strong>{escape(item.horizon)} | {escape(item.direction)}</strong>"
            f'<p class="muted">confidence {item.confidence:.2f} | skeptic {item.skeptic_score:.2f} | attention {item.attention_score:.2f}</p>'
            f'<p class="muted">{escape(item.summary)}</p>'
            "</article>"
        )
        for item in snapshot.items
    )
    return (
        '<section class="panel">'
        '<div class="panel-head"><h2>Horizon compare</h2><p>Read the root across multiple horizons in one place.</p></div>'
        f'<div class="metric-list">{rows}</div>'
        "</section>"
    )


def _render_signal_diff(diff) -> str:
    if diff is None:
        return ""
    return (
        '<section class="panel">'
        '<div class="panel-head"><h2>What changed since last cycle?</h2><p>Diff vs the previous recalculation.</p></div>'
        '<div class="metric-list">'
        f'<article><strong>{escape(diff.summary)}</strong><p class="muted">Prob up {diff.probability_up_delta:+.2f} | confidence {diff.confidence_delta:+.2f} | skeptic {diff.skeptic_delta:+.2f} | freshness {diff.freshness_delta:+.2f}</p></article>'
        f'<article><strong>Drivers</strong><p class="muted">Added: {escape(", ".join(diff.drivers_added) or "none")} | Removed: {escape(", ".join(diff.drivers_removed) or "none")}</p></article>'
        f'<article><strong>Invalidation</strong><p class="muted">Added: {escape(", ".join(diff.invalidations_added) or "none")} | Removed: {escape(", ".join(diff.invalidations_removed) or "none")}</p></article>'
        "</div>"
        "</section>"
    )


def _render_confidence_decomposition(decomposition) -> str:
    if decomposition is None:
        return ""
    items = "".join(
        f'<article><strong>{escape(item.label)}</strong><p class="muted">{item.value:.2f} | {escape(item.detail or "")}</p></article>'
        for item in decomposition.factors
    )
    return (
        '<section class="panel">'
        '<div class="panel-head"><h2>Confidence decomposition</h2><p>'
        f"{escape(decomposition.headline)}"
        "</p></div>"
        f'<div class="metric-list">{items}</div>'
        "</section>"
    )


def _render_decision_timeline(items, *, title: str) -> str:
    rows = "".join(
        f'<article class="timeline-item tone-{escape(item.tone)}"><strong>{escape(item.title)}</strong><p class="muted">{escape(_format_timestamp(item.at))} | {escape(item.detail)}</p></article>'
        for item in items
    ) or '<p class="empty">No decision events yet.</p>'
    return (
        '<section class="panel">'
        f'<div class="panel-head"><h2>{escape(title)}</h2><p>Narrative timeline across workflow, journal, and resolution.</p></div>'
        f'<div class="timeline-list">{rows}</div>'
        "</section>"
    )


def _render_review_bundle(bundle) -> str:
    highlights = "".join(f"<li>{escape(item)}</li>" for item in bundle.highlights) or "<li>No review highlights yet.</li>"
    return (
        '<section class="panel">'
        '<div class="panel-head"><h2>Review bundle</h2><p>End-of-day and post-resolution recall in one block.</p></div>'
        '<div class="metric-list">'
        f'<article><strong>Watched roots</strong><p class="muted">{bundle.watched_roots}</p></article>'
        f'<article><strong>Decisions logged</strong><p class="muted">{bundle.decisions_logged}</p></article>'
        f'<article><strong>Ignored / resolved</strong><p class="muted">{bundle.ignored_signals} / {bundle.resolved_signals}</p></article>'
        f'<article><strong>Highlights</strong><ul>{highlights}</ul></article>'
        "</div>"
        "</section>"
    )


def _render_similar_setups(items) -> str:
    body = "".join(
        f'<article><strong>{escape(item.outcome)}</strong><p class="muted">{escape(_format_timestamp(item.resolved_at))} | {item.realized_return_bps:.1f} bps | similarity {item.similarity_score:.2f}</p><p class="muted">{escape(item.note)}</p></article>'
        for item in items
    ) or '<p class="empty">No similar historical setups are available yet.</p>'
    return (
        '<section class="panel">'
        '<div class="panel-head"><h2>Similar historical setups</h2><p>Resolved analogs for quick precedent checks.</p></div>'
        f'<div class="metric-list">{body}</div>'
        "</section>"
    )


def _render_workspace_signal_tile(signal, selected_signal_id: str | None, *, language: str) -> str:
    is_focus = signal.signal_id == selected_signal_id or (selected_signal_id is None and signal.status.value == "active")
    copy = {
        "open": "Открыть" if language == "ru" else "Open",
        "focus": "В фокус" if language == "ru" else "Focus",
        "pin_a": "Сигнал A" if language == "ru" else "Signal A",
        "pin_b": "Сигнал B" if language == "ru" else "Signal B",
        "preview_ready": "Выберите таймфрейм" if language == "ru" else "Pick a timeframe",
        "preview_note": (
            "Быстрый просмотр сигнала без перехода на полную страницу."
            if language == "ru"
            else "Quick signal preview without leaving the lane."
        ),
    }
    preview_buttons = "".join(
        (
            f'<button class="signal-preview-button{" is-active" if timeframe == "1D" else ""}" '
            f'type="button" data-signal-preview-button data-signal-id="{escape(signal.signal_id)}" '
            f'data-timeframe="{timeframe}">{timeframe}</button>'
        )
        for timeframe in ("1D", "1W", "1M")
    )
    return (
        f'<article class="signal-tile{" is-focus" if is_focus else ""}" '
        f'data-signal-preview-card data-signal-id="{escape(signal.signal_id)}">'
        f'<a class="signal-tile-link" href="/workspace?root={escape(signal.root)}&signal_id={escape(signal.signal_id)}">'
        '<div class="signal-top">'
        f'<div><strong>{escape(signal.root)} | {escape(signal.contract)}</strong><p class="muted">{escape(signal.summary)}</p></div>'
        f'<span class="badge">{escape(signal.direction_final.value)} | {escape(signal.horizon.value)}</span>'
        "</div>"
        '<div class="metric-row">'
        f"<small>confidence {signal.confidence_final:.2f}</small>"
        f"<small>skeptic {signal.skeptic_score:.2f}</small>"
        f"<small>priority {signal.priority_score}</small>"
        f"<small>workflow {_workflow_state_label(signal.workflow_state)}</small>"
        "</div>"
        "</a>"
        '<div class="signal-tile-footer">'
        f'<div class="signal-preview-tabs">{preview_buttons}</div>'
        f'<a class="rail-open-link" href="/workspace/signals/{escape(signal.signal_id)}">{escape(copy["open"])}</a>'
        "</div>"
        f'<div class="signal-preview-popover" hidden data-signal-preview-popover data-signal-id="{escape(signal.signal_id)}">'
        '<div class="signal-preview-head">'
        f'<strong>{escape(signal.root)} | {escape(signal.horizon.value)} | <span data-signal-preview-label>1D</span></strong>'
        f'<small data-signal-preview-updated>{escape(copy["preview_ready"])}</small>'
        "</div>"
        f'<div class="signal-preview-chart" data-signal-preview-chart><div class="empty">{escape(copy["preview_note"])}</div></div>'
        '<div class="signal-preview-grid" data-signal-preview-grid></div>'
        f'<div class="signal-preview-summary" data-signal-preview-summary>{escape(signal.summary)}</div>'
        '<div class="signal-preview-actions">'
        f'<button class="preview-pin-button" type="button" data-pin-signal-preview data-signal-id="{escape(signal.signal_id)}" data-compare-slot="a" data-timeframe="1D">{escape(copy["pin_a"])}</button>'
        f'<button class="preview-pin-button" type="button" data-pin-signal-preview data-signal-id="{escape(signal.signal_id)}" data-compare-slot="b" data-timeframe="1D">{escape(copy["pin_b"])}</button>'
        f'<a class="rail-open-link" href="/workspace?root={escape(signal.root)}&signal_id={escape(signal.signal_id)}">{escape(copy["focus"])}</a>'
        f'<a class="rail-open-link" href="/workspace/signals/{escape(signal.signal_id)}">{escape(copy["open"])}</a>'
        "</div>"
        "</div>"
        "</article>"
    )


def _render_action_item(item: WorkspaceActionItem) -> str:
    return (
        f'<article class="action-card tone-{escape(item.tone)}">'
        f"<strong>{escape(item.title)}</strong>"
        f'<p class="muted">{escape(item.detail)}</p>'
        "</article>"
    )


def _render_journal_entry(entry) -> str:
    return (
        '<article class="journal-entry">'
        f"<strong>{escape(entry.title)}</strong>"
        f"<small>{escape(entry.kind.value)} | {escape(entry.author)} | {escape(_format_timestamp(entry.created_at))}</small>"
        f'<p class="muted">{escape(entry.note)}</p>'
        "</article>"
    )


def _render_related_signal(signal) -> str:
    return (
        f'<a class="related-card" href="/workspace/signals/{escape(signal.signal_id)}">'
        f"<strong>{escape(signal.root)} | {escape(signal.contract)} | {escape(signal.horizon.value)}</strong>"
        f'<p class="muted">{escape(signal.summary)}</p>'
        f'<p class="muted">confidence {signal.confidence_final:.2f} | skeptic {signal.skeptic_score:.2f} | {escape(signal.direction_final.value)} | workflow {_workflow_state_label(signal.workflow_state)}</p>'
        "</a>"
    )


def _render_journal_decision_log_item(item) -> str:
    signal = item.signal
    latest_entry = item.latest_entry
    why_now = "".join(f"<li>{escape(point)}</li>" for point in item.why_now)
    next_watch = "".join(f"<li>{escape(point)}</li>" for point in item.next_watch)
    latest_note = (
        f'Latest note: {escape(latest_entry.title)} | {escape(latest_entry.author)} | {escape(_format_timestamp(latest_entry.created_at))}'
        if latest_entry is not None
        else f'Latest note: none yet | updated {escape(_format_timestamp(item.updated_at))}'
    )
    return (
        '<article class="decision-card">'
        '<div class="decision-head">'
        f'<div><strong>{escape(signal.root)} | {escape(signal.contract)} | {escape(signal.horizon.value)}</strong><p class="muted">{escape(signal.summary)}</p></div>'
        '<div class="decision-head-actions">'
        f'<span class="badge">{escape(signal.direction_final.value)} | {escape(signal.status.value)}</span>'
        f"{_render_workflow_chip(signal)}"
        "</div>"
        "</div>"
        '<div class="decision-grid">'
        f'<article><span>Decision</span><p>{escape(item.decision_summary)}</p></article>'
        f'<article><span>Why this is the current call</span><ul>{why_now}</ul></article>'
        f'<article><span>What should change next</span><ul>{next_watch}</ul></article>'
        "</div>"
        f'<p class="muted" style="margin-top:12px;">{latest_note}</p>'
        '<div style="display:flex;flex-wrap:wrap;gap:10px;margin-top:12px;">'
        f'<a class="button" href="/workspace/signals/{escape(signal.signal_id)}">Open signal page</a>'
        f'<a class="button" href="/workspace?root={escape(signal.root)}&signal_id={escape(signal.signal_id)}">Open in workspace</a>'
        "</div>"
        "</article>"
    )


def _render_journal_workspace_entry(item) -> str:
    signal = item.signal
    entry = item.entry
    return (
        '<article class="entry-card">'
        '<div class="entry-meta">'
        f'<div><strong>{escape(entry.title)}</strong><p class="muted">{escape(signal.root)} | {escape(signal.contract)} | {escape(signal.horizon.value)}</p></div>'
        f'<span class="badge">{escape(entry.kind.value)} | {escape(signal.status.value)}</span>'
        "</div>"
        f'<p class="muted">{escape(entry.note)}</p>'
        f'<p class="muted">author {escape(entry.author)} | created {escape(_format_timestamp(entry.created_at))}</p>'
        '<div style="display:flex;flex-wrap:wrap;gap:10px;margin-top:12px;">'
        f'<a class="button" href="/workspace/signals/{escape(signal.signal_id)}">Open signal page</a>'
        f'<a class="button" href="/workspace?root={escape(signal.root)}&signal_id={escape(signal.signal_id)}">Open in workspace</a>'
        "</div>"
        "</article>"
    )


def _render_metric_bars(items, *, compact: bool) -> str:
    if not items:
        return '<p class="empty">No chart data available yet.</p>'
    rendered = []
    for item in items:
        ratio = 0.0
        if item.max_value > 0:
            ratio = max(0.0, min(float(item.value) / float(item.max_value), 1.0))
        detail = f'<p class="muted">{escape(item.detail)}</p>' if item.detail and not compact else ""
        rendered.append(
            '<article class="metric-bar">'
            '<div class="metric-bar-head">'
            f"<strong>{escape(item.label)}</strong>"
            f"<span>{item.value:.2f}</span>"
            "</div>"
            '<div class="metric-bar-track">'
            f'<div class="metric-bar-fill tone-{escape(item.tone)}" style="width:{ratio * 100:.0f}%"></div>'
            "</div>"
            f"{detail}"
            "</article>"
        )
    return "".join(rendered)


def _render_timeline(items, *, compact: bool) -> str:
    if not items:
        return '<p class="empty">No lifecycle events recorded yet.</p>'
    limit = 4 if compact else len(items)
    rendered = []
    for item in items[-limit:]:
        rendered.append(
            f'<article class="timeline-item tone-{escape(item.tone)}">'
            f"<strong>{escape(item.title)}</strong>"
            f'<p class="muted">{escape(_format_timestamp(item.at))} | {escape(item.kind)}</p>'
            f'<p class="muted">{escape(item.detail)}</p>'
            "</article>"
        )
    return "".join(rendered)


def _render_horizon_pulse(items) -> str:
    if not items:
        return '<p class="empty">No horizon pulse data available yet.</p>'
    rendered = []
    for item in items:
        rendered.append(
            f'<article class="horizon-card tone-{escape(item.tone)}">'
            f"<strong>{escape(item.horizon)}</strong>"
            f'<p class="muted">signal probability {item.signal_probability:.2f}</p>'
            f'<p class="muted">return score {item.return_score:.2f}</p>'
            f'<p class="muted">volatility {item.realized_volatility:.2f} | trend {item.trend_slope:.2f}</p>'
            "</article>"
        )
    return "".join(rendered)


def _render_delivery_windows(items) -> str:
    if not items:
        return '<p class="empty">No delivery windows configured yet.</p>'
    rendered = []
    for item in items:
        next_run = escape(_format_timestamp(item.next_run_at)) if item.next_run_at is not None else "not scheduled"
        last_status = escape(item.last_run_status or "never")
        detail = escape(item.last_run_detail or item.quiet_hours_policy)
        skip_label = "Mute next digest" if item.event_kind == NotificationEventKind.DIGEST else "Skip next brief"
        skip_button = (
            f'<button class="button delivery-undo-skip" type="button" data-event-kind="{escape(item.event_kind.value)}">Undo skip</button>'
            if item.skip_next_pending
            else f'<button class="button delivery-skip-next" type="button" data-event-kind="{escape(item.event_kind.value)}">{escape(skip_label)}</button>'
        )
        rendered.append(
            f'<article class="delivery-card tone-{"positive" if item.subscription_enabled else "warning"}">'
            f"<strong>{escape(item.event_kind.value)}</strong>"
            f'<p class="muted">{escape(item.label)}</p>'
            f'<p class="muted">root {escape(item.root_scope)} | next {next_run}</p>'
            f'<p class="muted">subscription {"on" if item.subscription_enabled else "off"} | {escape(item.quiet_hours_policy)}</p>'
            f'<p class="muted">skip next {"pending" if item.skip_next_pending else "off"}</p>'
            f'<p class="muted">last run {last_status} | {detail}</p>'
            '<div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:10px;">'
            f'<button class="button delivery-send-now" type="button" data-event-kind="{escape(item.event_kind.value)}">Send now</button>'
            f'<button class="button delivery-send-now-force" type="button" data-event-kind="{escape(item.event_kind.value)}">Send now ignoring quiet hours</button>'
            f"{skip_button}"
            "</div>"
            "</article>"
        )
    return "".join(rendered)


def _render_delivery_activity(items) -> str:
    if not items:
        return '<p class="empty">No delivery actions recorded yet.</p>'
    rendered = []
    for item in items:
        title = {
            NotificationDeliveryActivityAction.SEND_NOW: "Manual send",
            NotificationDeliveryActivityAction.SEND_NOW_FORCE: "Manual send with quiet-hours override",
            NotificationDeliveryActivityAction.SCHEDULE_DELIVERY: "Scheduled delivery",
            NotificationDeliveryActivityAction.SKIP_NEXT: "Skip next",
            NotificationDeliveryActivityAction.UNDO_SKIP: "Undo skip",
        }.get(item.action, item.action.value)
        signal_info = (
            f"signals {len(item.signal_ids)}"
            if item.signal_ids
            else "no signal ids"
        )
        source = escape(item.delivery_source or "manual")
        root_scope = escape(item.root_scope or "profile default")
        rendered.append(
            f'<article class="delivery-card tone-{"positive" if item.status == "sent" else "warning"}">'
            f"<strong>{escape(title)}</strong>"
            f'<p class="muted">{escape(item.event_kind.value)} | {escape(_format_timestamp(item.created_at))}</p>'
            f'<p class="muted">root {root_scope} | source {source} | status {escape(item.status)}</p>'
            f'<p class="muted">{escape(item.detail)}</p>'
            f'<p class="muted">{escape(signal_info)}'
            f'{" | provider message " + escape(item.provider_message_id) if item.provider_message_id else ""}</p>'
            "</article>"
        )
    return "".join(rendered)


def _delivery_activity_filter_href(
    base_path: str,
    *,
    root: str | None = None,
    signal_id: str | None = None,
    activity_root_scope: str | None = None,
    activity_event_kind: NotificationEventKind | None = None,
    activity_status: str | None = None,
) -> str:
    params: dict[str, str] = {}
    if root is not None:
        params["root"] = root
    if signal_id is not None:
        params["signal_id"] = signal_id
    if activity_root_scope is not None:
        params["activity_root_scope"] = activity_root_scope
    if activity_event_kind is not None:
        params["activity_event_kind"] = activity_event_kind.value
    if activity_status is not None:
        params["activity_status"] = activity_status
    if not params:
        return base_path
    return f"{base_path}?{urlencode(params)}"


def _render_delivery_activity_controls(
    *,
    base_path: str,
    filters: NotificationDeliveryActivityFilters,
    by_event_kind: list[NotificationDeliveryActivityGroup],
    by_root_scope: list[NotificationDeliveryActivityGroup],
    by_status: list[NotificationDeliveryActivityGroup],
    root: str | None = None,
    signal_id: str | None = None,
) -> str:
    clear_href = _delivery_activity_filter_href(base_path, root=root, signal_id=signal_id)
    event_links = [
        (
            '<a class="filter-chip'
            f'{" is-active" if filters.event_kind is None else ""}" '
            f'href="{escape(clear_href)}">All events</a>'
        )
    ]
    for item in by_event_kind:
        href = _delivery_activity_filter_href(
            base_path,
            root=root,
            signal_id=signal_id,
            activity_root_scope=filters.root_scope,
            activity_event_kind=NotificationEventKind(item.value),
            activity_status=filters.status,
        )
        event_links.append(
            '<a class="filter-chip'
            f'{" is-active" if filters.event_kind is not None and filters.event_kind.value == item.value else ""}" '
            f'href="{escape(href)}">{escape(item.label)} ({item.count})</a>'
        )
    root_links: list[str] = []
    if len(by_root_scope) > 1:
        root_links.append(
            '<a class="filter-chip'
            f'{" is-active" if filters.root_scope is None else ""}" '
            f'href="{escape(_delivery_activity_filter_href(base_path, root=root, signal_id=signal_id, activity_event_kind=filters.event_kind, activity_status=filters.status))}">All roots</a>'
        )
        for item in by_root_scope:
            href = _delivery_activity_filter_href(
                base_path,
                root=root,
                signal_id=signal_id,
                activity_root_scope=item.value,
                activity_event_kind=filters.event_kind,
                activity_status=filters.status,
            )
            root_links.append(
                '<a class="filter-chip'
                f'{" is-active" if filters.root_scope == item.value else ""}" '
                f'href="{escape(href)}">{escape(item.label)} ({item.count})</a>'
            )
    status_links = [
        (
            '<a class="filter-chip'
            f'{" is-active" if filters.status is None else ""}" '
            f'href="{escape(_delivery_activity_filter_href(base_path, root=root, signal_id=signal_id, activity_root_scope=filters.root_scope, activity_event_kind=filters.event_kind))}">All statuses</a>'
        )
    ]
    for item in by_status:
        href = _delivery_activity_filter_href(
            base_path,
            root=root,
            signal_id=signal_id,
            activity_root_scope=filters.root_scope,
            activity_event_kind=filters.event_kind,
            activity_status=item.value,
        )
        status_links.append(
            '<a class="filter-chip'
            f'{" is-active" if filters.status == item.value else ""}" '
            f'href="{escape(href)}">{escape(item.label)} ({item.count})</a>'
        )
    summary_cards = []
    for group_title, groups in (
        ("By event", by_event_kind),
        ("By root", by_root_scope),
        ("By status", by_status),
    ):
        if not groups:
            continue
        summary_cards.append(
            '<article class="summary-card">'
            f"<strong>{escape(group_title)}</strong>"
            f'<span>{escape(", ".join(f"{item.label} {item.count}" for item in groups[:4]))}</span>'
            "</article>"
        )
    blocks = [
        '<div class="filter-stack">',
        '<div><strong>Event kind</strong><div class="filter-row">' + "".join(event_links) + "</div></div>",
    ]
    if root_links:
        blocks.append('<div><strong>Root scope</strong><div class="filter-row">' + "".join(root_links) + "</div></div>")
    blocks.append('<div><strong>Status</strong><div class="filter-row">' + "".join(status_links) + "</div></div>")
    blocks.append('<div class="stack" style="margin-top:8px;">' + "".join(summary_cards) + "</div>")
    blocks.append("</div>")
    return "".join(blocks)


def _render_delivery_activity_footer(
    *,
    base_path: str,
    export_path: str,
    filters: NotificationDeliveryActivityFilters,
    pagination: NotificationDeliveryActivityPagination,
    root: str | None = None,
    signal_id: str | None = None,
) -> str:
    links: list[str] = []
    if pagination.has_previous:
        prev_href = _delivery_activity_filter_href(
            base_path,
            root=root,
            signal_id=signal_id,
            activity_root_scope=filters.root_scope,
            activity_event_kind=filters.event_kind,
            activity_status=filters.status,
        )
        sep = "&" if "?" in prev_href else "?"
        links.append(f'<a class="filter-chip" href="{escape(prev_href)}{sep}activity_page={pagination.page - 1}&activity_page_size={pagination.page_size}">Previous</a>')
    if pagination.has_next:
        next_href = _delivery_activity_filter_href(
            base_path,
            root=root,
            signal_id=signal_id,
            activity_root_scope=filters.root_scope,
            activity_event_kind=filters.event_kind,
            activity_status=filters.status,
        )
        sep = "&" if "?" in next_href else "?"
        links.append(f'<a class="filter-chip" href="{escape(next_href)}{sep}activity_page={pagination.page + 1}&activity_page_size={pagination.page_size}">Next</a>')
    export_base = _delivery_activity_filter_href(
        export_path,
        root=root,
        signal_id=signal_id,
        activity_root_scope=filters.root_scope,
        activity_event_kind=filters.event_kind,
        activity_status=filters.status,
    )
    export_csv = f'{escape(export_base)}{"&" if "?" in export_base else "?"}export_format=csv'
    export_jsonl = f'{escape(export_base)}{"&" if "?" in export_base else "?"}export_format=jsonl'
    meta = (
        f'<p class="muted">Page {pagination.page} of {pagination.total_pages} | '
        f'{pagination.total_items} total events | page size {pagination.page_size}</p>'
    )
    return (
        '<div class="filter-stack" style="margin-top:14px;">'
        f"{meta}"
        '<div class="filter-row">'
        + "".join(links)
        + f'<a class="filter-chip" href="{export_csv}">Export CSV</a>'
        + f'<a class="filter-chip" href="{export_jsonl}">Export JSONL</a>'
        + "</div></div>"
    )


def _journal_filter_href(
    *,
    root: str | None = None,
    status: SignalStatus | None = None,
    kind: JournalEntryKind | None = None,
) -> str:
    params: dict[str, str] = {}
    if root is not None:
        params["root"] = root
    if status is not None:
        params["status"] = status.value
    if kind is not None:
        params["kind"] = kind.value
    if not params:
        return "/workspace/journal"
    return f"/workspace/journal?{urlencode(params)}"


def _with_optional_root(path: str, *, root: str | None = None) -> str:
    if not root:
        return path
    return f"{path}?{urlencode({'root': root})}"


def _sidebar_selected_root(roots, root: str | None):
    if roots:
        if root:
            match = next((item for item in roots if item.root_code == root), None)
            if match is not None:
                return match
        return roots[0]
    return None


def _render_page_sidebar_styles(max_width: str) -> str:
    return f"""
    .page-shell {{
      width: min({max_width}, calc(100% - 28px));
      margin: 20px auto 36px;
      display: grid;
      grid-template-columns: 248px minmax(0, 1fr);
      gap: 16px;
      align-items: start;
    }}
    .shell {{
      width: 100%;
      margin: 0;
    }}
    .page-sidebar {{
      position: sticky;
      top: 18px;
      align-self: start;
    }}
    .sidebar-card {{
      background: var(--paper, var(--panel));
      border: 1px solid var(--line);
      border-radius: 28px;
      box-shadow: var(--shadow);
      padding: 18px;
      display: grid;
      gap: 12px;
      backdrop-filter: blur(14px);
    }}
    .sidebar-kicker {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(23, 56, 79, 0.08);
      color: var(--navy, var(--teal));
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 12px;
    }}
    .sidebar-title {{
      margin: 0;
      font-family: Georgia, "Palatino Linotype", serif;
      font-size: 22px;
    }}
    .sidebar-nav {{
      display: grid;
      gap: 8px;
    }}
    .sidebar-link {{
      display: block;
      padding: 12px 14px;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.68);
      font-weight: 700;
    }}
    .sidebar-link.is-active {{
      background: rgba(17, 104, 102, 0.12);
      color: var(--teal);
      border-color: rgba(17, 104, 102, 0.28);
    }}
    .sidebar-meta {{
      padding: 14px 16px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.62);
    }}
    .sidebar-switch {{
      padding: 14px 16px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.62);
      display: grid;
      gap: 10px;
    }}
    .sidebar-switch select {{
      width: 100%;
      padding: 12px 14px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.84);
      color: var(--ink);
      font: inherit;
    }}
    .sidebar-meta label {{
      display: block;
      margin-bottom: 6px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 11px;
    }}
    .sidebar-switch label {{
      display: block;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 11px;
    }}
    .sidebar-meta strong {{
      font-size: 18px;
    }}
    .sidebar-meta small {{
      display: block;
      margin-top: 6px;
      color: var(--muted);
      line-height: 1.45;
    }}
    @media (max-width: 1040px) {{
      .page-shell {{
        grid-template-columns: 1fr;
        width: min(100% - 16px, {max_width});
      }}
      .page-sidebar {{
        position: static;
      }}
      .sidebar-nav {{
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      }}
    }}
"""


def _render_page_sidebar(
    page_key: str,
    *,
    root: str | None = None,
    roots=None,
    signal_id: str | None = None,
) -> str:
    items = [
        ("workspace", "Workspace", _with_optional_root("/workspace", root=root)),
        ("dashboard", "Operations", _with_optional_root("/dashboard", root=root)),
        ("council", "Decision flow", _with_optional_root("/workspace/council", root=root)),
        ("runtime", "Runtime control", _with_optional_root("/workspace/runtime", root=root)),
        ("journal", "Journal", _with_optional_root("/workspace/journal", root=root)),
        ("preferences", "Preferences", _with_optional_root("/workspace/preferences", root=root)),
        ("delivery-history", "Delivery history", _with_optional_root("/workspace/delivery-history", root=root)),
    ]
    if signal_id:
        items.append(("signal", "Signal detail", f"/workspace/signals/{escape(signal_id)}"))

    links = "".join(
        f'<a class="sidebar-link{" is-active" if key == page_key else ""}" href="{href}" data-swap-link>{label}</a>'
        for key, label, href in items
    )
    selected_root = _sidebar_selected_root(roots or [], root)
    current_root = selected_root.root_code if selected_root is not None else (root or "auto")
    switch_markup = ""
    if roots:
        fallback_attr = ' data-fallback-path="/workspace"' if page_key == "signal" else ""
        options = "".join(
            (
                f'<option value="{escape(item.root_code)}"'
                f'{" selected" if item.root_code == current_root else ""}>'
                f"{escape(item.root_code)} · {escape(item.active_contract)} · {escape(item.base_asset)}"
                "</option>"
            )
            for item in roots
        )
        switch_markup = (
            '<div class="sidebar-switch">'
            '<label for="sidebar-root-switch">Switch instrument</label>'
            f'<select id="sidebar-root-switch" data-root-switch data-page-key="{escape(page_key)}"{fallback_attr}>'
            f"{options}"
            "</select>"
            "</div>"
        )
    meta_detail = ""
    if selected_root is not None:
        meta_detail = f'<small>{escape(selected_root.active_contract)} · {escape(selected_root.base_asset)}</small>'
    return (
        '<aside class="page-sidebar">'
        '<div class="sidebar-card">'
        '<span class="sidebar-kicker">Navigation</span>'
        '<h2 class="sidebar-title">Move around the workspace</h2>'
        '<p class="muted">Jump between the main pages for the current root and signal.</p>'
        f'<div class="sidebar-nav">{links}</div>'
        f"{switch_markup}"
        f'<div class="sidebar-meta"><label>Current instrument</label><strong>{escape(current_root)}</strong>{meta_detail}</div>'
        "</div>"
        "</aside>"
    )


def _render_signal_card(signal) -> str:
    return (
        '<article class="signal-card">'
        '<div class="signal-top">'
        f'<div><strong>{escape(signal.root)} · {escape(signal.contract)}</strong><div class="signal-summary">{escape(signal.summary)}</div></div>'
        f'<span class="badge">{escape(signal.direction_final.value)} · {escape(signal.horizon.value)}</span>'
        "</div>"
        '<div class="signal-meta">'
        f"<small>confidence {signal.confidence_final:.2f}</small>"
        f"<small>skeptic {signal.skeptic_score:.2f}</small>"
        f"<small>priority {signal.priority_score}</small>"
        f"<small>workflow {_workflow_state_label(signal.workflow_state)}</small>"
        "</div>"
        "</article>"
    )


def _render_signal_row(signal) -> str:
    return (
        '<article class="signal-row">'
        f"<strong>{escape(signal.root)} · {escape(signal.horizon.value)} · {escape(signal.direction_final.value)}</strong>"
        f"<small>{escape(signal.summary)} | workflow {_workflow_state_label(signal.workflow_state)}</small>"
        "</article>"
    )


def _control_panel_data_mode_tone(mode: str) -> str:
    if mode == "live":
        return "tone-positive"
    if mode == "snapshot":
        return "tone-warning"
    return "tone-negative"


def _control_panel_data_mode_label(mode: str) -> str:
    labels = {
        "live": "Live",
        "snapshot": "Snapshot",
        "degraded_feed": "Degraded feed",
    }
    return labels.get(mode, mode.replace("_", " ").title())


def _control_panel_reference_sync_tone(status: str) -> str:
    if status == "fresh":
        return "tone-positive"
    if status == "stale":
        return "tone-warning"
    return "tone-negative"


def _control_panel_reference_sync_label(status: str) -> str:
    labels = {
        "fresh": "Fresh",
        "stale": "Stale",
        "fallback": "Fallback",
    }
    return labels.get(status, status.replace("_", " ").title())


def _control_panel_reference_sync_source(source: str) -> str:
    labels = {
        "moex_iss": "MOEX ISS",
        "bundled_fallback": "Bundled fallback",
    }
    return labels.get(source, source.replace("_", " ").title())


def _primary_market_feed(panel):
    primary = next((item for item in panel.market_data_feeds if item.primary), None)
    if primary is not None:
        return primary
    return panel.market_data_feeds[0] if panel.market_data_feeds else None


def _render_market_data_context(panel) -> str:
    primary_feed = _primary_market_feed(panel)
    if primary_feed is None:
        return (
            '<article><span>Price Source</span><strong>n/a</strong>'
            '<p class="muted">No market-data feed is attached yet.</p></article>'
        )

    data_mode_label = _control_panel_data_mode_label(panel.data_mode)
    updated_at = _format_timestamp(primary_feed.last_update_at)
    return (
        f'<article><span>Price Source</span><strong>{escape(primary_feed.owner)}</strong>'
        f'<p class="muted">{escape(data_mode_label)} | Updated {escape(updated_at)}</p></article>'
    )


def _render_control_panel(panel) -> str:
    latest_market_data = _format_timestamp(panel.latest_market_data_at)
    data_mode_label = _control_panel_data_mode_label(panel.data_mode)
    data_mode_tone = _control_panel_data_mode_tone(panel.data_mode)
    data_mode_detail = escape(panel.data_mode_detail or "No detail available.")
    reference_sync_label = _control_panel_reference_sync_label(panel.reference_sync.status)
    reference_sync_source = _control_panel_reference_sync_source(panel.reference_sync.source)
    reference_sync_tone = _control_panel_reference_sync_tone(panel.reference_sync.status)
    reference_sync_detail = escape(panel.reference_sync.detail or "No detail available.")
    latest_reference_sync = _format_timestamp(panel.reference_sync.last_sync_at)
    role_cards = "".join(
        (
            "<article>"
            f"<strong>{escape(item.role_label)}</strong>"
            f"<p>{escape(item.product)} &middot; {escape(item.model)} &middot; {escape(item.owner)}</p>"
            f'<p class="muted">{escape(item.detail or item.control_mode)}</p>'
            "</article>"
        )
        for item in panel.model_roles
    ) or '<p class="empty">No model roles configured yet.</p>'
    feed_cards = "".join(
        (
            "<article>"
            f"<strong>{escape(item.provider)} &middot; {escape(item.owner)}</strong>"
            f"<p>{escape(item.role)} &middot; {escape(item.status)} &middot; last {escape(_format_timestamp(item.last_update_at))}</p>"
            f'<p class="muted">{escape(item.detail or "No detail available.")}</p>'
            "</article>"
        )
        for item in panel.market_data_feeds
    ) or '<p class="empty">No market-data feeds are attached to this root yet.</p>'
    return (
        '<div class="control-summary-grid">'
        f'<article class="control-summary-card"><label>LLM runtime</label><strong>{escape(panel.llm_product)} &middot; {escape(panel.llm_model)}</strong></article>'
        f'<article class="control-summary-card"><label>LLM owner</label><strong>{escape(panel.llm_owner)}</strong></article>'
        f'<article class="control-summary-card is-wide {data_mode_tone}"><label>Data mode</label><strong>{escape(data_mode_label)}</strong><small>{data_mode_detail}</small></article>'
        f'<article class="control-summary-card"><label>Latest market data</label><strong>{escape(latest_market_data)}</strong></article>'
        f'<article class="control-summary-card is-wide {reference_sync_tone}"><label>Reference sync</label><strong>{escape(reference_sync_label)} &middot; {escape(reference_sync_source)}</strong><small>{escape(panel.reference_sync.owner)} | {reference_sync_detail}</small></article>'
        f'<article class="control-summary-card"><label>Latest reference sync</label><strong>{escape(latest_reference_sync)}</strong></article>'
        "</div>"
        '<div class="panel-head" style="margin-top:18px;"><h3>Role routing</h3></div>'
        f'<div class="metric-list">{role_cards}</div>'
        '<div class="panel-head" style="margin-top:18px;"><h3>Market-data feeds</h3></div>'
        f'<div class="metric-list">{feed_cards}</div>'
    )


def _render_quality_pair(pair: DashboardQualityPair) -> str:
    latest_contract = pair.latest_contract or "n/a"
    mismatch = _format_optional(pair.mismatch_rate_overlap)
    return (
        "<article>"
        f"<strong>{escape(pair.provider_a)} vs {escape(pair.provider_b)}</strong>"
        f"<p>contracts {pair.contracts_count} · latest {escape(latest_contract)} · mismatch {escape(mismatch)}</p>"
        "</article>"
    )


def _market_status_tone(status: str) -> str:
    normalized = status.lower()
    if normalized in {"fresh", "live", "ok"}:
        return "positive"
    if normalized in {"aging", "snapshot", "stale", "warning"}:
        return "warning"
    return "negative"


def _market_status_label(status: str, *, language: str) -> str:
    labels = {
        "fresh": "Свежие" if language == "ru" else "Fresh",
        "live": "Live",
        "ok": "OK",
        "aging": "Стареют" if language == "ru" else "Aging",
        "snapshot": "Снимок" if language == "ru" else "Snapshot",
        "stale": "Несвежие" if language == "ru" else "Stale",
        "warning": "Предупреждение" if language == "ru" else "Warning",
        "degraded": "Деградация" if language == "ru" else "Degraded",
    }
    return labels.get(status.lower(), status)


def _format_price_value(value: float | None) -> str:
    if value is None:
        return "n/a"
    if abs(value) >= 1000:
        return f"{value:,.2f}".replace(",", " ")
    return f"{value:.2f}"


def _format_signed_value(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.2f}"


def _format_signed_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.2%}"


def _format_optional(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.4f}"


def _format_timestamp(value: datetime | None) -> str:
    if value is None:
        return "n/a"
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(MOSCOW_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S MSK")


def _format_calendar_date(value: date | None, *, language: str) -> str:
    if value is None:
        return "n/a"
    if language == "ru":
        return value.strftime("%d.%m.%Y")
    return value.isoformat()


def _format_expiry_countdown(days_to_expiry: int, expiry_date: date | None, *, language: str) -> str:
    if expiry_date is None:
        return str(days_to_expiry)
    formatted_date = _format_calendar_date(expiry_date, language=language)
    if language == "ru":
        return f"{days_to_expiry} · до {formatted_date}"
    return f"{days_to_expiry} · until {formatted_date}"
