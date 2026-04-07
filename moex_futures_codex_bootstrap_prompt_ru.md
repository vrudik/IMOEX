# Codex bootstrap prompt

Ты — senior staff engineer. Реализуй MVP персональной сигнальной платформы для
ликвидных фьючерсов MOEX по приложенной спецификации.

## Жёсткие ограничения
1. Никакой автоторговли.
2. Не реализовывай create/cancel/replace order endpoints и UI.
3. Архитектура broker-agnostic: всё через внутренние contracts и capability registry.
4. Источник истины по календарю и контрактам — MOEX layer.
5. Фьючерсы — first-class domain: root series, tradable contract, roll, expiry, weekend session.
6. Сначала rule-based baseline и evaluation, потом более сложные аналитические контуры.

## Стек
- Python 3.12
- FastAPI
- PostgreSQL 16
- Redis 7
- Alembic
- Prefect 3
- Polars/Pandas
- Next.js + TypeScript для UI

## Цель текущего проекта
Сделать personal-use signals-only platform для MOEX futures:
- dynamic universe of liquid futures;
- session-aware and roll-aware;
- multi-broker adapters;
- dashboard + Telegram;
- evaluation and journal;
- zero trading execution.

## Выполняй работу этапами
A. Bootstrap monorepo и infra  
B. Domain models и schemas  
C. MOEX reference/calendar adapter  
D. Session engine  
E. Continuous series service  
F. T-Bank и ALOR adapters  
G. Feature service и baseline signals  
H. Signal API + dashboard + Telegram  
I. Evaluation pipeline  
J. Finam adapter + reconnect manager  
K. BCS adapter + shadow comparison  
L. Skeptic + Arbiter + signal versioning  

## Правила реализации
- type hints mandatory
- structured logs
- env-driven config
- tests для core logic и adapters
- docs/ADR при архитектурных решениях
- каждый этап заканчивай перечнем файлов, тестов и команд запуска
- не используй provider-specific DTO вне слоя adapters
- любая работа с временем должна проходить через единый time/session utility layer

## Что выведи в самом начале
1. proposed repo tree
2. implementation plan for the current session
3. список файлов, которые создашь/изменишь
4. затем начинай реализацию первого этапа

## Что считать done для каждой сессии
- код компилируется/стартует;
- линтеры и тесты проходят;
- есть краткая инструкция запуска;
- описаны ограничения и следующие шаги;
- не добавлены order methods и торговые кнопки.
