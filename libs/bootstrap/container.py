from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from libs.analysts.service import AnalystService
from libs.continuous.engine import ContinuousSeriesEngine
from libs.dashboard.service import DashboardService
from libs.domain.repository import SqlAlchemyContractMasterRepository
from libs.domain.service import ContractMasterService
from libs.evaluation.service import EvaluationService
from libs.features.service import FeatureService
from libs.journal.service import JournalService
from libs.maintenance.service import MaintenanceService
from libs.marketdata.service import get_market_data_service
from libs.notifications.alerts import TelegramOpsAlertService
from libs.notifications.service import TelegramNotificationService
from libs.observability.service import ObservabilityService
from libs.pipeline.service import PipelineService
from libs.preferences.service import NotificationPreferenceService
from libs.quality.repository import SqlAlchemySourceQualityRepository
from libs.reference.service import get_moex_reference_service
from libs.resolution.service import ResolutionService
from libs.runtime.service import RuntimeControlService
from libs.scheduler.service import SchedulerService
from libs.session.engine import SessionEngine
from libs.signals.service import SignalService
from libs.skeptic.service import SkepticService
from libs.universe.service import UniverseService
from libs.utils.db import get_session_factory


@dataclass
class AppContainer:
    repository: SqlAlchemyContractMasterRepository
    quality_repository: SqlAlchemySourceQualityRepository
    contract_master_service: ContractMasterService
    journal_service: JournalService
    signal_service: SignalService
    resolution_service: ResolutionService
    evaluation_service: EvaluationService
    pipeline_service: PipelineService
    maintenance_service: MaintenanceService
    observability_service: ObservabilityService
    dashboard_service: DashboardService
    runtime_control_service: RuntimeControlService
    preference_service: NotificationPreferenceService
    telegram_notification_service: TelegramNotificationService
    telegram_ops_alert_service: TelegramOpsAlertService
    scheduler_service: SchedulerService


@lru_cache(maxsize=1)
def get_app_container() -> AppContainer:
    session_factory = get_session_factory()
    repository = SqlAlchemyContractMasterRepository(session_factory)
    quality_repository = SqlAlchemySourceQualityRepository(session_factory)
    reference_service = get_moex_reference_service()
    resolution_service = ResolutionService(repository)
    journal_service = JournalService(repository)
    signal_service = SignalService(
        repository,
        resolution_service=resolution_service,
        journal_service=journal_service,
    )
    evaluation_service = EvaluationService(repository)
    contract_master_service = ContractMasterService(
        repository,
        SessionEngine(reference_service=reference_service),
        ContinuousSeriesEngine(),
        FeatureService(repository),
        reference_service,
        UniverseService(),
        AnalystService(repository),
        SkepticService(repository),
    )
    pipeline_service = PipelineService(
        contract_master_service,
        signal_service,
        resolution_service,
        evaluation_service,
    )
    maintenance_service = MaintenanceService(repository, quality_repository)
    observability_service = ObservabilityService(repository, maintenance_service=maintenance_service)
    runtime_control_service = RuntimeControlService(repository)
    market_data_service = get_market_data_service()
    preference_service = NotificationPreferenceService(
        repository,
        list_roots_callable=contract_master_service.list_roots,
    )
    dashboard_service = DashboardService(
        repository,
        quality_repository,
        contract_service=contract_master_service,
        signal_service=signal_service,
        evaluation_service=evaluation_service,
        observability_service=observability_service,
        runtime_control_service=runtime_control_service,
        market_data_service=market_data_service,
    )
    telegram_notification_service = TelegramNotificationService(
        dashboard_service,
        preferences_service=preference_service,
    )
    scheduler_service = SchedulerService(
        repository=repository,
        pipeline_service=pipeline_service,
        maintenance_service=maintenance_service,
        telegram_notification_service=telegram_notification_service,
        reference_service=reference_service,
    )
    telegram_ops_alert_service = TelegramOpsAlertService(
        scheduler_service=scheduler_service,
        observability_service=observability_service,
    )
    return AppContainer(
        repository=repository,
        quality_repository=quality_repository,
        contract_master_service=contract_master_service,
        journal_service=journal_service,
        signal_service=signal_service,
        resolution_service=resolution_service,
        evaluation_service=evaluation_service,
        pipeline_service=pipeline_service,
        maintenance_service=maintenance_service,
        observability_service=observability_service,
        dashboard_service=dashboard_service,
        runtime_control_service=runtime_control_service,
        preference_service=preference_service,
        telegram_notification_service=telegram_notification_service,
        telegram_ops_alert_service=telegram_ops_alert_service,
        scheduler_service=scheduler_service,
    )
