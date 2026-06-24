from core.app_config import (
    APP_DISPLAY_NAME,
    APP_MODULE,
    APP_VERSION,
    LOG_FILE_NAME,
    SESSION_REPORT_PREFIX,
    SETUP_REPORT_PREFIX,
)
from core.modules import default_module_manifests
from core.safety import SafetyGateError, assert_action_allowed, decide_action_safety


def test_app_identity_is_tuningforge() -> None:
    assert APP_DISPLAY_NAME == "DEVHub TuningForge"
    assert APP_MODULE == "TuningForge"
    assert APP_VERSION == "0.9.2"
    assert LOG_FILE_NAME == "tuningforge.log"
    assert SETUP_REPORT_PREFIX == "tuningforge"
    assert SESSION_REPORT_PREFIX == "devhub-session"


def test_default_module_manifests_are_plug_and_play_ready() -> None:
    manifests = {manifest.id: manifest for manifest in default_module_manifests()}

    assert {"controldeck", "tuningforge", "guardforge", "scanforge", "recoveryforge", "riskengine", "alertdeck", "configdeck", "systeminfo", "agentdeck"}.issubset(manifests)
    assert manifests["tuningforge"].status == "active"
    assert manifests["tuningforge"].requires_admin is True
    assert "repair" in manifests["tuningforge"].capabilities
    assert "offline-cache" in manifests["tuningforge"].capabilities
    assert "risk-engine" in manifests["tuningforge"].capabilities
    assert "configuration" in manifests["tuningforge"].capabilities
    assert manifests["guardforge"].status == "alpha"
    assert manifests["guardforge"].version == "0.2.0-alpha"
    assert manifests["scanforge"].configurable is True
    assert manifests["recoveryforge"].status == "alpha"
    assert manifests["recoveryforge"].version == "0.6.0-alpha"
    assert manifests["riskengine"].status == "preview"
    assert manifests["riskengine"].version == "0.7.0-preview"
    assert manifests["riskengine"].requires_admin is False
    assert manifests["alertdeck"].status == "preview"
    assert manifests["alertdeck"].version == "0.8.0-preview"
    assert manifests["alertdeck"].requires_admin is False
    assert manifests["configdeck"].status == "preview"
    assert manifests["configdeck"].version == "0.9.1-preview"
    assert manifests["configdeck"].configurable is True
    assert manifests["systeminfo"].status == "preview"
    assert manifests["systeminfo"].version == "0.9.2-preview"
    assert "msinfo32-export" in manifests["systeminfo"].capabilities


def test_safety_gate_blocks_high_risk_and_medium_defaults() -> None:
    low = decide_action_safety("niedrig")
    medium = decide_action_safety("mittel")
    high = decide_action_safety("hoch")

    assert low.allowed is True
    assert low.requires_second_confirmation is False
    assert medium.allowed is True
    assert medium.requires_second_confirmation is True
    assert high.allowed is False

    try:
        assert_action_allowed("mittel", enabled_by_default=True)
    except SafetyGateError as exc:
        assert "Mittlere Risiken duerfen nicht vorausgewaehlt sein" in str(exc)
    else:
        raise AssertionError("medium default action was not blocked")
