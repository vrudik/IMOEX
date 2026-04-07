# Техническое задание и план разработки
## Персональная сигнальная платформа для ликвидных фьючерсов MOEX
**Версия:** 1.0  
**Дата:** 2026-03-29  
**Режим:** signals only, без автоторговли  
**Архитектура:** мультиброкерная, broker-agnostic  

---

## 1. Назначение
Создать персональную сигнальную платформу для наиболее ликвидных фьючерсов MOEX, которая:
- собирает рыночные данные и события;
- строит futures-native признаки;
- формирует объяснимые вероятностные сигналы;
- показывает причины сигнала и причины сомнений;
- ведёт историю версий сигнала и журнал действий пользователя;
- автоматически считает качество сигналов после разрешения горизонта.

Система **не** выставляет заявки, не управляет счётом и не содержит UI-команд исполнения.

---

## 2. Зафиксированные вводные
- Рынок: MOEX Derivatives / FORTS.
- Инструменты: наиболее ликвидные фьючерсы, universe формируется автоматически.
- Горизонты:
  - краткосрочный: 1–3 сессии;
  - среднесрочный: 3–20 торговых дней.
- Пользователь: один человек, personal use.
- Требование: предусмотреть подключение всех доступных в РФ брокеров с нужным API.
- Принцип: решения принимает пользователь, система выдаёт только сигналы.

---

## 3. Главные продуктовые принципы
1. **Signals only by design** — торговые методы не реализуются в MVP и не доступны через UI/API.
2. **Exchange truth first** — биржа является источником истины для календаря, экспираций, режимов торгов и справочников.
3. **Futures-native domain** — root series, tradable contract, roll, expiry, clearing и weekend session моделируются явно.
4. **Metrics-first** — любые новые сигнальные контуры включаются только после честной OOS-оценки.
5. **Reproducibility** — любой сигнал воспроизводим по версии данных, признаков и кода.
6. **Graceful degradation** — отказ одного адаптера не должен класть весь продукт.
7. **MVP = modular monolith** — без преждевременной микросервисности.

---

## 4. Внешние предпосылки, влияющие на дизайн
- Срочный рынок MOEX с 23.03.2026 работает в режиме единой торговой сессии.
- Дополнительная сессия выходного дня относится к следующему торговому дню.
- MOEX ISS покрывает инструменты, свечи, сделки, котировки, историю и метаданные.
- MOEX Algopack может использоваться как premium-слой, включая OI/open positions.
- T-Invest API имеет futures, market data, streams и sandbox.
- ALOR даёт HTTP, WebSocket и GraphQL.
- Finam даёт REST, gRPC и WebSocket; нужен reconnect manager.
- БКС даёт market data streams, стакан, сделки и futures limits.
- Банк России публикует календарь решений по ключевой ставке и времена релизов.

Подробный реестр URL см. в конце документа.

---

## 5. Доменная модель
### 5.1 Root series vs tradable contract
Система должна различать:
- **root series** — аналитическая непрерывная серия;
- **tradable contract** — конкретный контракт для наблюдения и ручного решения.

### 5.2 Основные сущности
- `root_series`
- `contract_meta`
- `trading_session`
- `normalized_market_event`
- `normalized_business_event`
- `feature_snapshot`
- `analyst_output`
- `skeptic_review`
- `final_signal`
- `signal_version`
- `signal_resolution`
- `user_journal_entry`

### 5.3 Горизонты
- `H1S` — 1 сессия
- `H3S` — 2–3 сессии
- `H2W` — 1–2 недели
- `H4W` — 2–4 недели

---

## 6. Целевая архитектура
```text
[ MOEX ISS / Trading Calendar / Algopack ]   [ T-Bank ] [ ALOR ] [ Finam ] [ BCS ]
                    \                          |         |        |       /
                     \------------------ Broker & Exchange Adapters -------------/
                                              |
                                              v
                                  Contract Master + Session Engine
                                              |
                                              v
                            Continuous Series Builder + Liquidity Ranker
                                              |
                                              v
                               Ingestion / Storage / Feature Pipelines
                                              |
                      +-----------------------+------------------------+
                      |                       |                        |
                      v                       v                        v
               Trend/Vol Analyst     OrderFlow/Liquidity Analyst   OI/Roll Analyst
                                              |
                                              v
                                      Macro/Event Analyst
                                              |
                                              v
                                        Skeptic / Verifier
                                              |
                                              v
                                        Arbiter / Calibrator
                                              |
                                              v
                                 Signal API / Dashboard / Telegram
```

---

## 7. Рекомендуемый стек
### Backend / data
- Python 3.12
- FastAPI
- PostgreSQL 16
- Redis 7
- SQLAlchemy 2
- Alembic
- Prefect 3
- Polars / Pandas / PyArrow
- scikit-learn + LightGBM
- Pydantic v2

### Frontend
- Next.js + TypeScript
- Tailwind / простая UI-библиотека
- Telegram bot/service

### Infra
- Docker Compose
- Prometheus-compatible metrics
- Grafana
- structured logs JSON

---

## 8. Состав модулей
1. `contract-master`
2. `session-engine`
3. `adapters`
4. `market-ingestor`
5. `event-ingestor`
6. `continuous-series`
7. `feature-service`
8. `analyst-engine`
9. `skeptic`
10. `arbiter`
11. `signal-api`
12. `evaluation`
13. `journal`
14. `notifications`

---

## 9. Источники данных
### Обязательные
- MOEX reference/calendar layer
- MOEX trading calendar
- MOEX contract metadata / expiry schedule
- Bank of Russia key rate calendar

### Broker adapters to implement
- T-Bank
- ALOR
- Finam
- BCS

### Optional premium layer
- MOEX Algopack

### Источник истины
- календарь, session rules, contract meta: **MOEX**
- live market data: configurable `primary_provider`
- shadow/fallback: configurable `secondary_provider`

---

## 10. Требования к мультиброкерности
Каждый адаптер обязан публиковать capability registry:

```python
class CapabilityRegistry(BaseModel):
    historical_bars: bool
    stream_bars: bool
    trades: bool
    order_book: bool
    status: bool
    futures_limits: bool
    sandbox: bool
    auth_type: str
    known_constraints: list[str]
```

Все provider-specific DTO должны нормализоваться во внутренние контракты:
- `Bar`
- `Trade`
- `OrderBook`
- `TradingStatus`
- `ContractMeta`
- `BusinessEvent`

---

## 11. Session Engine
Session Engine — обязательный сервис.

Он должен:
- различать `calendar_day` и `trading_day`;
- моделировать `morning`, `main`, `evening`, `weekend`, `clearing`, `halted`;
- иметь версионирование правил по effective date;
- маппить weekend session к следующему trading day;
- знать окна near-clearing и near-expiry.

Ключевые поля:
- `trading_day`
- `session_type`
- `session_start_at`
- `session_end_at`
- `is_weekend_linked`
- `is_clearing_window`
- `effective_rule_set`

---

## 12. Continuous Series / Roll Engine
Обязательные функции:
- front contract selection;
- next contract detection;
- back-adjusted continuous series;
- roll event generation;
- `days_to_expiry`, `days_to_last_trade`, `roll_risk_flag`, `next_contract_share`.

Нельзя обучать среднесрочные сигналы по raw front-only серии без учёта roll.

---

## 13. Universe policy
Universe не должен быть зашит вручную.

### Policy
- еженедельный liquidity ranking;
- top-N root series;
- диверсификация по классам активов;
- ручной allow/deny list;
- lock/unlock policy для root-series.

### Liquidity score
- rolling ADTV
- median spread
- depth near best bid/ask
- open interest
- volume stability
- front-vs-next dominance

---

## 14. Feature layer
### Price/vol
- returns by horizon
- ATR
- realized volatility
- breakout state
- trend slope
- VWAP distance
- gap flags

### Flow/liquidity
- relative volume
- trade imbalance
- top-of-book imbalance
- spread regime
- depth regime
- acceleration of tape

### OI/roll
- OI level / delta
- price + OI interaction
- front/next spread
- roll state
- days_to_expiry
- days_to_last_trade

### Session
- session_of_day
- proximity_to_clearing
- weekend-linked flag
- overnight_gap_regime

### Macro/event
- key_rate_event_proximity
- exchange_notice_type
- trading_status_change
- macro regime flags

Все признаки должны быть point-in-time correct.

---

## 15. Analyst layer
MVP должен содержать 4 аналитических контура:

1. **Trend/Vol Analyst**
2. **OrderFlow/Liquidity Analyst**
3. **OI/Roll Analyst**
4. **Macro/Event Analyst**

Каждый контур возвращает:
```json
{
  "analyst": "oi_roll",
  "direction": "bullish",
  "probability": 0.63,
  "confidence": 0.71,
  "drivers": ["price up + OI up"],
  "objections": ["near clearing risk"],
  "invalidation_conditions": ["OI delta turns negative"],
  "freshness_score": 0.92
}
```

---

## 16. Skeptic
Skeptic обязателен.

### Что он делает
- штрафует сигнал за stale data;
- штрафует за low liquidity;
- штрафует за near-expiry;
- штрафует за unconfirmed event;
- ищет противоречия между analyst outputs;
- может перевести сигнал в `soft_fail`, `reject`, `human_review`.

### Output
- `skeptic_score`
- `verdict`
- `main_objections`
- `data_quality_flags`

---

## 17. Arbiter
Arbiter:
- агрегирует аналитические контуры;
- учитывает skeptic penalties;
- делает calibration;
- выпускает versioned final signal;
- пересчитывает `priority_score`.

### Final signal
```json
{
  "signal_id": "SIG-2026-03-29-Si-H3S-000017",
  "version": 4,
  "root": "Si",
  "contract": "SiM6",
  "direction_final": "bullish",
  "probability_up": 0.64,
  "probability_down": 0.19,
  "probability_no_edge": 0.17,
  "confidence_final": 0.72,
  "priority_score": 81,
  "roll_risk": 0.11,
  "expiry_risk": 0.07,
  "skeptic_verdict": "pass"
}
```

---

## 18. Функциональные требования
### Contract master
- хранить root и contracts раздельно;
- хранить specs, expiry, tick, lot, currency;
- weekly dynamic universe;
- allow/deny lists.

### Session engine
- versioned session rules;
- mapping weekend to trading day;
- support clearing windows;
- store session type in all snapshots and signals.

### Ingestion
- historical + streaming;
- immutable raw layer;
- dedup/out-of-order handling;
- replay mode;
- source freshness metrics.

### Event layer
- MOEX calendar
- exchange notices
- CBR calendar
- optional generic news
- novelty / importance / uncertainty scoring

### Feature layer
- feature versioning
- point-in-time correctness
- horizon-specific snapshots

### Signal layer
- 4 analysts
- Skeptic
- Arbiter
- versioned signals
- invalidation logic

### UX layer
- dashboard
- Telegram
- journal
- resolved signals
- post-mortem

### Evaluation
- labels per horizon
- Brier, BSS, log loss
- precision/recall
- calibration
- top-K precision
- regime slices

---

## 19. Internal API
### REST
- `GET /api/v1/roots`
- `GET /api/v1/signals`
- `GET /api/v1/signals/{signal_id}`
- `GET /api/v1/roots/{root}/deep-dive`
- `GET /api/v1/health/sources`
- `POST /api/v1/admin/replay`
- `POST /api/v1/admin/recalculate`
- `POST /api/v1/journal/{signal_id}`

### Internal topics
```text
market.bars.1m.{provider}.{root}
market.orderbook.{provider}.{contract}
market.trades.{provider}.{contract}
reference.contracts.updated
session.calendar.updated
event.expiry.detected
event.roll.detected
features.snapshot.created.{horizon}
analyst.output.created.{analyst}.{horizon}
skeptic.review.completed
signal.version.created
signal.invalidated
signal.resolved
alerts.telegram.dispatch
```

---

## 20. UI / UX
### Main screens
- active signals
- root deep-dive
- evaluation
- journal
- admin/health

### Telegram
- new signal
- confidence change
- invalidation
- source outage / stale source

### Hard UX restriction
Никаких кнопок Buy / Sell / Close / Reverse.

---

## 21. Нефункциональные требования
### Reliability
- restart-safe pipelines
- provider failover
- daily backups
- replay support

### Observability
- structured logs
- metrics for freshness, lag, reconnect, drops
- health dashboard

### Security
- secrets in env/secret store
- no trading scopes in MVP
- explicit feature flags

### Legal
- source registry with usage notes
- research-only marking where needed
- no public redistribution without rights

---

## 22. Рекомендуемая структура репозитория
```text
repo/
  apps/
    api/
    worker/
    ui/
  libs/
    domain/
    adapters/
    session/
    continuous/
    features/
    analysts/
    evaluation/
    notifications/
    utils/
  infra/
    docker/
    migrations/
    prefect/
    grafana/
  tests/
    unit/
    integration/
    contract/
    replay/
  docs/
    adr/
    api/
    runbooks/
```

---

## 23. Этапы внедрения
1. Scope freeze
2. Repo bootstrap
3. MOEX reference/calendar layer
4. Session engine
5. Continuous series engine
6. T-Bank + ALOR adapters
7. Baseline features + rule-based signals
8. UI + Telegram
9. Evaluation pipeline
10. Finam + BCS adapters
11. Skeptic + Arbiter
12. Hardening + monitoring

Ключевое правило: **до ML/LLM должен появиться полезный baseline с честной оценкой качества**.

---

## 24. Acceptance criteria
MVP принят, если:
1. подключён MOEX reference/calendar layer;
2. подключены минимум два broker adapters;
3. реализован dynamic universe;
4. есть session engine и continuous-series logic;
5. есть 4 analysts + Skeptic + Arbiter;
6. есть active/resolved signals;
7. есть dashboard и Telegram;
8. есть journal;
9. есть evaluation reports;
10. отсутствуют order methods и trading UI.

---

## 25. Work packages для Codex
### Session 1
Bootstrap monorepo, infra, config, logging, migrations.

### Session 2
Domain models, enums, schemas, internal contracts.

### Session 3
MOEX reference/calendar adapter.

### Session 4
Session engine + unit tests.

### Session 5
Continuous series + roll engine.

### Session 6
T-Bank adapter.

### Session 7
ALOR adapter.

### Session 8
Feature service + baseline signals.

### Session 9
Signal API + dashboard + Telegram.

### Session 10
Evaluation pipeline.

### Session 11
Finam adapter + reconnect manager.

### Session 12
BCS adapter + shadow comparison.

### Session 13
Skeptic + Arbiter + signal versioning + journal.

---

## 26. Definition of done
Для каждого work package:
- проходят тесты и линтеры;
- есть минимум один unit/integration test;
- обновлена документация;
- описаны изменённые файлы;
- нет скрытых TODO;
- код не содержит торговых методов.

---

## 27. Риски
- изменение правил MOEX;
- divergence between providers;
- licensing issues;
- leakage in backtests;
- near-expiry distortions;
- reconnect failures;
- LLM overconfidence.

Снижение:
- versioned rules;
- shadow provider comparison;
- source registry;
- replay / OOS-only evaluation;
- expiry-zone flags;
- reconnect manager;
- Skeptic and metrics-first.

---

## 28. Официальные URL для handoff
- https://www.moex.com/ru/derivatives/unified-trading-session
- https://www.moex.com/derivatives/weekend-session
- https://www.moex.com/ru/tradingcalendar/
- https://www.moex.com/a8531
- https://www.moex.com/a2193
- https://data.moex.com/products/algopack
- https://www.moex.com/ru/derivatives/open-positions-online.aspx
- https://developer.tbank.ru/invest/api
- https://developer.tbank.ru/invest/api/instruments-service-futures
- https://alor.dev/docs/
- https://alor.dev/docs/api/usage/data
- https://alor.dev/docs/api/graphql/overview
- https://tradeapi.finam.ru/getting-started/
- https://tradeapi.finam.ru/docs/grpc/
- https://tradeapi.finam.ru/docs-new/async-api-new/
- https://trade-api.bcs.ru/websocket/market-data/
- https://trade-api.bcs.ru/websocket/market-data/order-book/
- https://trade-api.bcs.ru/websocket/limits/
- https://cbr.ru/eng/DKP/cal_mp/
