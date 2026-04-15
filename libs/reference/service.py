from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache

from libs.domain.contracts import AdminMoexReferenceSyncResult
from libs.reference.contracts import MoexCalendarDay, MoexContractReference
from libs.reference.iss import MoexIssClient
from libs.session.rules import DEFAULT_RULE_SETS, SessionRuleSet


class MoexReferenceService:
    def __init__(
        self,
        *,
        rule_sets: tuple[SessionRuleSet, ...] = DEFAULT_RULE_SETS,
        contracts: tuple[MoexContractReference, ...] | None = None,
    ) -> None:
        self.rule_sets = tuple(sorted(rule_sets, key=lambda item: item.effective_from))
        self.contracts = contracts or _default_contract_references()
        self.calendar_overrides: dict[date, tuple[date, bool]] = {}

    def get_rule_set(self, day: date) -> SessionRuleSet:
        active = self.rule_sets[0]
        for rule_set in self.rule_sets:
            if day >= rule_set.effective_from:
                active = rule_set
        return active

    def resolve_calendar_day(self, calendar_day: date) -> MoexCalendarDay:
        rule_set = self.get_rule_set(calendar_day)
        override = self.calendar_overrides.get(calendar_day)
        if override is not None:
            trading_day, is_weekend_session = override
        else:
            is_weekend_session = calendar_day.weekday() >= 5 and rule_set.code == "moex-unified-2026-03-23"
            trading_day = self._next_weekday(calendar_day) if is_weekend_session else calendar_day
        return MoexCalendarDay(
            calendar_day=calendar_day,
            trading_day=trading_day,
            is_weekend_session=is_weekend_session,
            rule_set=rule_set,
        )

    def list_contracts(self) -> list[MoexContractReference]:
        return list(self.contracts)

    def list_contracts_for_root(self, root_code: str) -> list[MoexContractReference]:
        rows = [item for item in self.contracts if item.root_code.upper() == root_code.upper()]
        rows.sort(key=lambda item: (item.last_trade_date, item.contract_code))
        return rows

    def get_contract(self, contract_code: str) -> MoexContractReference | None:
        for item in self.contracts:
            if item.contract_code.upper() == contract_code.upper():
                return item
        return None

    def sync_root_rule_set(self, *, calendar_day: date) -> str:
        return self.resolve_calendar_day(calendar_day).rule_set.code

    def sync_from_iss(
        self,
        *,
        client: MoexIssClient | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        sync_calendar: bool = True,
        sync_contracts: bool = True,
    ) -> AdminMoexReferenceSyncResult:
        iss_client = client or MoexIssClient()
        details: list[str] = []
        contracts_synced = 0
        calendar_days_synced = 0

        if sync_contracts:
            contracts_payload = iss_client.fetch_contracts_payload()
            contracts = iss_client.parse_contracts(contracts_payload)
            if contracts:
                self.contracts = tuple(contracts)
            contracts_synced = len(contracts)
            details.append(f"contracts_synced={contracts_synced}")

        if sync_calendar:
            calendar_payload = iss_client.fetch_calendar_payload(from_date=from_date, to_date=to_date)
            calendar_mapping = iss_client.parse_calendar(calendar_payload)
            if calendar_mapping:
                self.calendar_overrides.update(calendar_mapping)
            calendar_days_synced = len(calendar_mapping)
            details.append(f"calendar_days_synced={calendar_days_synced}")

        effective_day = from_date or date.today()
        return AdminMoexReferenceSyncResult(
            source="moex_iss",
            calendar_days_synced=calendar_days_synced,
            contracts_synced=contracts_synced,
            effective_rule_set=self.get_rule_set(effective_day).code,
            details=details,
        )

    def _next_weekday(self, current_day: date) -> date:
        candidate = current_day + timedelta(days=1)
        while candidate.weekday() >= 5:
            candidate += timedelta(days=1)
        return candidate


@lru_cache(maxsize=1)
def get_moex_reference_service() -> MoexReferenceService:
    return MoexReferenceService()


def _default_contract_references() -> tuple[MoexContractReference, ...]:
    return (
        MoexContractReference(
            contract_code="SiM6",
            root_code="Si",
            expiry_date=date(2026, 6, 19),
            last_trade_date=date(2026, 6, 17),
            tick_size=1.0,
            lot_size=1,
            currency="RUB",
        ),
        MoexContractReference(
            contract_code="SiU6",
            root_code="Si",
            expiry_date=date(2026, 9, 18),
            last_trade_date=date(2026, 9, 16),
            tick_size=1.0,
            lot_size=1,
            currency="RUB",
        ),
        MoexContractReference(
            contract_code="BRK6",
            root_code="BR",
            expiry_date=date(2026, 6, 11),
            last_trade_date=date(2026, 6, 9),
            tick_size=0.01,
            lot_size=10,
            currency="USD",
        ),
        MoexContractReference(
            contract_code="BRN6",
            root_code="BR",
            expiry_date=date(2026, 9, 10),
            last_trade_date=date(2026, 9, 8),
            tick_size=0.01,
            lot_size=10,
            currency="USD",
        ),
        MoexContractReference(
            contract_code="MXM6",
            root_code="MXI",
            expiry_date=date(2026, 6, 19),
            last_trade_date=date(2026, 6, 17),
            tick_size=1.0,
            lot_size=1,
            currency="PTS",
        ),
        MoexContractReference(
            contract_code="MXU6",
            root_code="MXI",
            expiry_date=date(2026, 9, 18),
            last_trade_date=date(2026, 9, 16),
            tick_size=1.0,
            lot_size=1,
            currency="PTS",
        ),
    )
