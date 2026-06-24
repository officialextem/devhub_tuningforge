from __future__ import annotations

from dataclasses import dataclass, field

from core.app_config import APP_VERSION


@dataclass(frozen=True)
class ModuleManifest:
    id: str
    name: str
    version: str
    status: str
    capabilities: list[str]
    risk_level: str
    requires_admin: bool
    reports: list[str] = field(default_factory=list)
    configurable: bool = False


def default_module_manifests() -> list[ModuleManifest]:
    return [
        ModuleManifest(
            id="controldeck",
            name="DEVHub ControlDeck",
            version=APP_VERSION,
            status="active",
            capabilities=["status", "recommendations", "reports", "daily-report-preview", "configuration"],
            risk_level="niedrig",
            requires_admin=False,
            reports=["session"],
            configurable=False,
        ),
        ModuleManifest(
            id="tuningforge",
            name="DEVHub TuningForge",
            version=APP_VERSION,
            status="active",
            capabilities=["setup", "repair", "updates", "uninstall", "offline-cache", "risk-engine", "configuration", "reports"],
            risk_level="mittel",
            requires_admin=True,
            reports=["setup", "session"],
            configurable=True,
        ),
        ModuleManifest(
            id="guardforge",
            name="DEVHub GuardForge",
            version="0.2.0-alpha",
            status="alpha",
            capabilities=["file-watch", "event-log", "risk-preview"],
            risk_level="niedrig",
            requires_admin=False,
            reports=["guard-events"],
            configurable=True,
        ),
        ModuleManifest(
            id="scanforge",
            name="DEVHub ScanForge",
            version="planned",
            status="planned",
            capabilities=["hash-scan", "pattern-scan", "optional-provider-adapters"],
            risk_level="niedrig",
            requires_admin=False,
            reports=["scan-summary"],
            configurable=True,
        ),
        ModuleManifest(
            id="recoveryforge",
            name="DEVHub RecoveryForge",
            version="0.6.0-alpha",
            status="alpha",
            capabilities=["backup-preview", "restore-point-adapter", "recovery-reports"],
            risk_level="mittel",
            requires_admin=True,
            reports=["recovery-summary"],
            configurable=True,
        ),
        ModuleManifest(
            id="riskengine",
            name="DEVHub Risk Engine",
            version="0.7.0-preview",
            status="preview",
            capabilities=["risk-score", "module-risk-summary", "read-only-recommendations"],
            risk_level="niedrig",
            requires_admin=False,
            reports=["risk-summary"],
            configurable=False,
        ),
        ModuleManifest(
            id="alertdeck",
            name="DEVHub AlertDeck",
            version="0.8.0-preview",
            status="preview",
            capabilities=["local-alerts", "daily-summary", "report-recommendations"],
            risk_level="niedrig",
            requires_admin=False,
            reports=["daily-summary"],
            configurable=False,
        ),
        ModuleManifest(
            id="configdeck",
            name="DEVHub ConfigDeck",
            version="0.9.1-preview",
            status="preview",
            capabilities=["local-config", "dry-run-preview", "import-export", "module-settings"],
            risk_level="niedrig",
            requires_admin=False,
            reports=["configuration"],
            configurable=True,
        ),
        ModuleManifest(
            id="systeminfo",
            name="DEVHub SystemInfoForge",
            version="0.9.2-preview",
            status="preview",
            capabilities=["msinfo32-export", "local-system-inventory", "agent-ready-report"],
            risk_level="niedrig",
            requires_admin=False,
            reports=["system-info"],
            configurable=True,
        ),
        ModuleManifest(
            id="agentdeck",
            name="DEVHub AgentDeck / NexusMind Core",
            version="planned",
            status="planned",
            capabilities=["workflow-orchestration", "module-routing", "assistant-adapters"],
            risk_level="niedrig",
            requires_admin=False,
            reports=["agent-session"],
            configurable=True,
        ),
    ]
