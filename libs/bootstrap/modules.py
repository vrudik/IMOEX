from __future__ import annotations

from pydantic import BaseModel, Field


class ModuleSpec(BaseModel):
    name: str
    layer: str
    description: str
    entrypoints: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)


def list_module_specs() -> list[ModuleSpec]:
    return [
        ModuleSpec(
            name="bootstrap",
            layer="platform",
            description="Shared composition root and module catalog for API and worker entrypoints.",
            entrypoints=["libs.bootstrap.container", "libs.bootstrap.modules"],
            dependencies=["runtime"],
        ),
        ModuleSpec(
            name="domain",
            layer="core",
            description="Persistent domain contracts, models and contract-master services.",
            entrypoints=["libs.domain.contracts", "libs.domain.repository", "libs.domain.service"],
            dependencies=["reference", "session", "continuous", "features", "universe", "analysts", "skeptic"],
        ),
        ModuleSpec(
            name="universe",
            layer="core",
            description="Liquidity ranking and dynamic active-universe selection policy.",
            entrypoints=["libs.universe.service"],
            dependencies=["domain"],
        ),
        ModuleSpec(
            name="reference",
            layer="core",
            description="MOEX reference and calendar layer with optional ISS sync.",
            entrypoints=["libs.reference.service", "libs.reference.iss"],
            dependencies=["runtime"],
        ),
        ModuleSpec(
            name="session",
            layer="core",
            description="Rule-based trading session resolution over calendar/trading day semantics.",
            entrypoints=["libs.session.engine", "libs.session.rules"],
            dependencies=["reference"],
        ),
        ModuleSpec(
            name="continuous",
            layer="core",
            description="Front/next contract selection, roll logic and back-adjusted builders.",
            entrypoints=["libs.continuous.engine", "libs.continuous.builder"],
            dependencies=["domain"],
        ),
        ModuleSpec(
            name="features",
            layer="analysis",
            description="Point-in-time feature snapshots over session and continuous state.",
            entrypoints=["libs.features.service"],
            dependencies=["domain", "session", "continuous"],
        ),
        ModuleSpec(
            name="analysts",
            layer="analysis",
            description="Trend/vol, flow, OI/roll and macro rule-based analyst outputs.",
            entrypoints=["libs.analysts.service"],
            dependencies=["features", "domain"],
        ),
        ModuleSpec(
            name="skeptic",
            layer="analysis",
            description="Skeptic scoring and verdict generation over analyst outputs.",
            entrypoints=["libs.skeptic.service"],
            dependencies=["analysts", "features"],
        ),
        ModuleSpec(
            name="arbiter",
            layer="analysis",
            description="Signal arbitration and final signal assembly.",
            entrypoints=["libs.arbiter.service"],
            dependencies=["analysts", "skeptic", "features"],
        ),
        ModuleSpec(
            name="signals",
            layer="application",
            description="Signal read/write service and materialization paths.",
            entrypoints=["libs.signals.service"],
            dependencies=["arbiter", "resolution", "journal"],
        ),
        ModuleSpec(
            name="journal",
            layer="application",
            description="User journal and post-mortem entries attached to signals.",
            entrypoints=["libs.journal.service", "apps.api.routes.journal"],
            dependencies=["signals", "domain"],
        ),
        ModuleSpec(
            name="resolution",
            layer="application",
            description="Signal resolution and post-factum outcome attribution.",
            entrypoints=["libs.resolution.service"],
            dependencies=["domain"],
        ),
        ModuleSpec(
            name="evaluation",
            layer="application",
            description="Calibration and quality metrics over resolved signals.",
            entrypoints=["libs.evaluation.service"],
            dependencies=["signals", "resolution"],
        ),
        ModuleSpec(
            name="pipeline",
            layer="application",
            description="Recalculate/replay orchestration across contract, signal and evaluation services.",
            entrypoints=["libs.pipeline.service"],
            dependencies=["domain", "signals", "resolution", "evaluation"],
        ),
        ModuleSpec(
            name="quality",
            layer="application",
            description="Shadow comparison and source quality persistence.",
            entrypoints=["libs.quality.service", "libs.quality.repository"],
            dependencies=["adapters", "domain"],
        ),
        ModuleSpec(
            name="dashboard",
            layer="delivery",
            description="Delivery snapshot and HTML dashboard over platform state.",
            entrypoints=["libs.dashboard.service", "apps.api.routes.dashboard"],
            dependencies=["domain", "signals", "evaluation", "observability", "quality", "runtime"],
        ),
        ModuleSpec(
            name="notifications",
            layer="delivery",
            description="Telegram preview/send delivery channel.",
            entrypoints=["libs.notifications.service", "apps.api.routes.notifications"],
            dependencies=["dashboard", "runtime"],
        ),
        ModuleSpec(
            name="scheduler",
            layer="ops",
            description="Config-driven recurring orchestration for worker commands and operational jobs.",
            entrypoints=["libs.scheduler.service"],
            dependencies=["pipeline", "maintenance", "notifications", "reference", "runtime"],
        ),
        ModuleSpec(
            name="observability",
            layer="ops",
            description="Admin health snapshot and operational inventory.",
            entrypoints=["libs.observability.service"],
            dependencies=["domain", "maintenance", "notifications", "scheduler", "runtime"],
        ),
        ModuleSpec(
            name="maintenance",
            layer="ops",
            description="Backup and retention cleanup services.",
            entrypoints=["libs.maintenance.service"],
            dependencies=["domain", "quality"],
        ),
        ModuleSpec(
            name="adapters",
            layer="integration",
            description="Normalized provider contracts and broker/reference adapters.",
            entrypoints=["libs.adapters.registry", "libs.adapters.base"],
            dependencies=["runtime"],
        ),
        ModuleSpec(
            name="runtime",
            layer="platform",
            description="Feature flags, runtime metrics and structured logging.",
            entrypoints=["libs.runtime.feature_flags", "libs.runtime.metrics", "libs.utils.logging"],
            dependencies=[],
        ),
        ModuleSpec(
            name="api",
            layer="entrypoint",
            description="FastAPI delivery entrypoint and HTTP routes.",
            entrypoints=["apps.api.factory", "apps.api.main"],
            dependencies=["bootstrap", "dashboard", "notifications", "pipeline", "observability", "quality", "journal"],
        ),
        ModuleSpec(
            name="worker",
            layer="entrypoint",
            description="CLI worker/orchestration entrypoints for reference, pipeline and delivery flows.",
            entrypoints=["apps.worker.runner"],
            dependencies=["bootstrap", "pipeline", "maintenance", "notifications", "reference", "scheduler"],
        ),
    ]
