# IMOEX trading system (signals-only)

This repo contains a **signals-only** MOEX futures research/ops stack.

## Invariants

- **No autotrading**: no order placement/cancel/replace.
- **Broker-agnostic contracts**: adapters live under `libs/adapters/*`.

## Quick start

```powershell
pip install -e ".[dev]"
uvicorn apps.api.main:app --reload
```

