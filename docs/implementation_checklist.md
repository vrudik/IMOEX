# Чеклист реализации IMOEX signals platform

Обновлено: 2026-04-14

Ниже фиксирую рабочий прогресс по спецификации из `moex_futures_signals_spec_v1_ru.md` и `moex_futures_signals_spec_v1_ru.docx`.

## Уже подтверждено

- [x] Спецификация из `.md` изучена и сверена с текущим репозиторием.
- [x] `.docx` открыт и проверен на соответствие ключевым разделам спецификации.
- [x] Подтверждено главное ограничение: только signals-only, без order routing и торговых кнопок.
- [x] В репозитории уже есть базовый FastAPI bootstrap и заготовка quality API.
- [x] Создан этот чеклист как источник текущего статуса реализации.

## Текущий фокус

- [x] Завести доменные контракты для roots, signals, session snapshots и source health.
- [x] Поднять первые API-эндпоинты по спецификации: `GET /api/v1/roots`, `GET /api/v1/roots/{root}/deep-dive`, `GET /api/v1/signals`, `GET /api/v1/signals/{signal_id}`, `GET /api/v1/health/sources`.
- [x] Добавить demo-данные, чтобы API отражал будущую доменную модель, а не пустой каркас.
- [x] Перевести `roots`/`deep-dive` с чистого demo-слоя на contract master repository с persistent seed/fallback.
- [x] Реализовать rule-based session engine и подключить его к `roots/{root}/deep-dive`.
- [x] Реализовать front/next selection, roll-risk и roll preview поверх contract master и session engine.
- [x] Реализовать полноценный back-adjusted continuous series builder.
- [x] Реализовать baseline rule-based signal builder поверх feature snapshots.
- [x] Реализовать liquidity ranking и dynamic universe policy.
- [x] Реализовать rule-based analyst layer c 4 analyst outputs в `deep-dive`.
- [x] Реализовать Skeptic и Arbiter поверх analyst outputs.
- [x] Реализовать signal resolution pipeline, journal и post-mortem flow.
- [x] Реализовать admin replay/recalculate flows и evaluation metrics baseline.
- [x] Реализовать replay mode и расширенные evaluation reports по regime slices.
- [x] Реализовать admin/health screen и operational observability baseline.
- [x] Реализовать backups/retention cleanup и более глубокую инфраструктурную observability.
- [x] Реализовать baseline adapter registry, normalized adapter contracts и source registry.
- [x] Реализовать первый credential-ready broker adapter для T-Bank с sandbox/live конфигурацией.
- [x] Реализовать credential-ready ALOR adapter с refresh/access token flow и test/prod конфигурацией.
- [x] Реализовать credential-ready Finam adapter с reconnect-managed stream constraints и secret/JWT auth path.
- [x] Реализовать credential-ready BCS adapter и baseline shadow comparison между primary и secondary provider.
- [x] Реализовать baseline MOEX reference/calendar layer и перевести contract metadata/session rules на него.
- [x] Реализовать live-capable MOEX ISS sync path с admin endpoint для ручного обновления reference/calendar snapshot.
- [x] Реализовать baseline dashboard delivery module поверх signals, evaluation, health и quality snapshot.
- [x] Реализовать baseline Telegram notification channel с preview/send flow и readiness visibility.

## Верификация текущего среза

- [x] Добавлены API-тесты на roots, signals и source health.
- [x] Локально прогнать `pytest` в этом окружении.
- [x] Локально прогнать `ruff check` в этом окружении.
- [x] Локально поднять `uvicorn apps.api.main:app --reload` в этом окружении.
- [x] Добавить local smoke-run и integration smoke flows по runbook.

## Этап 1. Bootstrap и архитектурный фундамент

- [x] FastAPI app c health endpoints.
- [x] Базовая DB-конфигурация и SQLAlchemy bootstrap.
- [x] Доменные API-контракты для signals-only сценария.
- [x] Полный modular-monolith skeleton по всем пакетам из спецификации.
- [x] Worker app и orchestration entrypoints.
- [x] Config-driven scheduler / recurring orchestration для worker jobs.
- [x] Scheduler run history, idempotency keys и DB-backed locks.
- [x] Leader-aware scheduler loop и singleton lease policy для нескольких инстансов.
- [x] Deployment recipes для Windows Task Scheduler, cron и Docker Compose.
- [x] Structured export для scheduler history и Telegram ops alerts по failed jobs / stale leader.
- [x] Alembic migrations и нормальная bootstrap-история схемы.
- [x] Structured logging, metrics, feature flags.
- [x] Актуальные `.env.example` и docker assets без битых ссылок.

## Этап 2. Domain core

- [x] Root series / tradable contract представлены в API-моделях.
- [x] Horizon codes, session types, skeptic verdicts и signal statuses заведены как enums.
- [x] Capability registry заведен как внутренний контракт.
- [x] SQLAlchemy/Pydantic модели для `root_series`, `contract_meta`, `trading_session`.
- [x] SQLAlchemy/Pydantic модели для `signal_version`, `signal_resolution`, `user_journal_entry`.
- [x] SQLAlchemy/Pydantic модель для `final_signal`.
- [x] Репозитории и сервисы доменного слоя поверх persistent storage для contract master.

## Этап 3. MOEX reference/calendar layer

- [x] MOEX calendar adapter.
- [x] MOEX contract metadata sync.
- [x] Expiry / last-trade-date sync.
- [x] Версионирование session rules по effective date.
- [x] Source registry и usage notes.
- [x] Optional live-capable MOEX ISS sync через admin flow.

## Этап 4. Session engine

- [x] Разделение `calendar_day` и `trading_day`.
- [x] Weekend session mapping к следующему trading day.
- [x] Clearing windows и near-expiry windows.
- [x] Unit tests для edge cases по сессиям.

## Этап 5. Continuous series / roll engine

- [x] Front/next contract selection.
- [x] Back-adjusted continuous series.
- [x] Roll event generation.
- [x] `days_to_expiry`, `days_to_last_trade`, `roll_risk_flag`, `next_contract_share`.

## Этап 6. Adapters

- [x] Baseline adapter registry, capability registry и normalized DTO для `Bar` / `Trade` / `OrderBook` / `TradingStatus` / `ContractMeta` / `BusinessEvent`.
- [x] Reconnect manager contract для stream-адаптеров и baseline wiring для Finam.
- [x] T-Bank adapter.
- [x] ALOR adapter.
- [x] Finam adapter с reconnect manager.
- [x] BCS adapter.
- [x] Shadow comparison между primary и secondary provider.

## Этап 7. Features и baseline signals

- [x] Feature service.
- [x] Liquidity ranking и dynamic universe policy.
- [x] Rule-based baseline signals.
- [x] Point-in-time correctness checks.

## Этап 8. Analysts, Skeptic, Arbiter

- [x] Trend/Vol analyst.
- [x] OrderFlow/Liquidity analyst.
- [x] OI/Roll analyst.
- [x] Macro/Event analyst.
- [x] Skeptic penalties и verdicts.
- [x] Arbiter, calibration и versioned final signals.

## Этап 9. UX и delivery

- [x] Dashboard.
- [x] User workspace с focus signal, action plan и quick journal capture.
- [x] Отдельная signal detail page для одного сигнала.
- [x] Journal workspace с фильтрами по root/status/kind.
- [x] Notification preferences center с default root, subscriptions и quiet hours.
- [x] Visual charts and lifecycle timelines для workspace и signal detail page.
- [x] Telegram notifications.
- [x] Delivery calendar actions и delivery activity feed в `/workspace` и `/workspace/preferences`.
- [x] Фильтры и grouped summaries для delivery activity по event kind, root scope и status.
- [x] Pagination и quick export (`csv` / `jsonl`) для delivery activity audit trail.
- [x] Отдельная user-facing страница `/workspace/delivery-history` для delivery audit trail.
- [x] Journal и post-mortem flow.
- [x] Active/resolved signal views.
- [x] Admin/health screen.

## Этап 10. Evaluation и hardening

- [x] Signal resolution pipeline.
- [x] Evaluation metrics: Brier, BSS, log loss, calibration, precision/recall.
- [x] Replay mode.
- [x] Observability, backups, retention cleanup.
- [x] Integration tests and smoke flows.
