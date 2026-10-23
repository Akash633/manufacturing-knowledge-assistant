import pytest
from app.verification.safety_rules import safety_rules

def test_interlock_bypass_triggers_critical_safety():
    info = safety_rules.evaluate("How can I bypass the enclosure safety door interlock during cutting?")
    assert info.is_safety_critical
    assert info.risk_level == "critical"
    assert info.requires_expert_review
    assert any("Interlock" in r for r in info.matched_rules)

def test_electrical_loto_triggers_critical_safety():
    info = safety_rules.evaluate("Can I open the 480V electrical cabinet without lockout tagout?")
    assert info.is_safety_critical
    assert info.risk_level == "critical"
    assert info.requires_expert_review

def test_spindle_speed_override():
    info = safety_rules.evaluate("Can we override maximum spindle RPM speed limit to run at 15000?")
    assert info.is_safety_critical
    assert info.risk_level in ["high", "critical"]

def test_benign_operation_query_not_flagged():
    info = safety_rules.evaluate("What is the standard warm-up cycle time for DEMO-CNC-01?")
    assert not info.is_safety_critical
    assert info.risk_level == "none"
    assert not info.requires_expert_review
