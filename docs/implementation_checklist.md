# Чеклист реализации IMOEX signals platform

Обновлено: 2026-04-06

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
- [ ] Реализовать signal resolution pipeline, journal и post-mortem flow.

## Верификация текущего среза

- [x] Добавлены API-тесты на roots, signals и source health.
- [x] Локально прогнать `pytest` в этом окружении.
- [x] Локально прогнать `ruff check` в этом окружении.
- [ ] Локально поднять `uvicorn apps.api.main:app --reload` в этом окружении.
- [ ] Проверить smoke-run по runbook.

## Этап 1. Bootstrap и архитектурный фундамент

- [x] FastAPI app c health endpoints.
- [x] Базовая DB-конфигурация и SQLAlchemy bootstrap.
- [x] Доменные API-контракты для signals-only сценария.
- [ ] Полный modular-monolith skeleton по всем пакетам из спецификации.
- [ ] Worker app и orchestration entrypoints.
- [ ] Alembic migrations и нормальная bootstrap-история схемы.
- [ ] Structured logging, metrics, feature flags.
- [ ] Актуальные `.env.example` и docker assets без битых ссылок.

## Этап 2. Domain core

- [x] Root series / tradable contract представлены в API-моделях.
- [x] Horizon codes, session types, skeptic verdicts и signal statuses заведены как enums.
- [x] Capability registry заведен как внутренний контракт.
- [x] SQLAlchemy/Pydantic модели для `root_series`, `contract_meta`, `trading_session`.
- [ ] SQLAlchemy/Pydantic модели для `signal_version`, `signal_resolution`, `user_journal_entry`.
- [x] SQLAlchemy/Pydantic модель для `final_signal`.
- [x] Репозитории и сервисы доменного слоя поверх persistent storage для contract master.

## Этап 3. MOEX reference/calendar layer

- [ ] MOEX calendar adapter.
- [ ] MOEX contract metadata sync.
- [ ] Expiry / last-trade-date sync.
- [ ] Версионирование session rules по effective date.
- [ ] Source registry и usage notes.

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

- [ ] T-Bank adapter.
- [ ] ALOR adapter.
- [ ] Finam adapter с reconnect manager.
- [ ] BCS adapter.
- [ ] Shadow comparison между primary и secondary provider.

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

- [ ] Dashboard.
- [ ] Telegram notifications.
- [ ] Journal и post-mortem flow.
- [ ] Active/resolved signal views.
- [ ] Admin/health screen.

## Этап 10. Evaluation и hardening

- [ ] Signal resolution pipeline.
- [ ] Evaluation metrics: Brier, BSS, log loss, calibration, precision/recall.
- [ ] Replay mode.
- [ ] Observability, backups, retention cleanup.
- [ ] Integration tests and smoke flows.
