import re
from typing import List, Dict, Any, Tuple
from app.schemas.query import SafetyEscalationInfo

class SafetyRuleEngine:
    """
    Deterministic rule engine for flagging high-risk and safety-critical shop-floor queries.
    Enforces mandatory human expert escalation.
    
    SAFETY MANDATE:
    No AI model confidence score is permitted to bypass mandatory safety escalation.
    """
    RULES = [
        {
            "id": "RULE-INTERLOCK-BYPASS",
            "name": "Safety Interlock / Enclosure Guard Bypass",
            "pattern": r"\b(?:bypass|disable|override|defeat|ignore|jump)\b.{0,40}\b(?:interlock|safety\s*gate|enclosure|door\s*guard|light\s*curtain)",
            "risk_level": "critical",
            "escalation_reason": "Attempting to bypass safety interlock violates OSHA 1910.212 and creates severe pinch/crush/amputation hazard.",
        },
        {
            "id": "RULE-LOTO-ELECTRICAL",
            "name": "Live Electrical Cabinet Access Without Lockout/Tagout",
            "pattern": r"\b(?:open|access|touch|service|probe|wire)\b.{0,40}\b(?:electrical\s*cabinet|main\s*power|high\s*voltage|480v|transformer)\b",
            "risk_level": "critical",
            "escalation_reason": "Servicing electrical panels without verified Lockout/Tagout (LOTO) poses fatal electrocution and arc-flash risk.",
        },
        {
            "id": "RULE-SPINDLE-OVERRIDE",
            "name": "Spindle Speed RPM Limits Override",
            "pattern": r"\b(?:exceed|overclock|override|push|run\s*above)\b.{0,40}\b(?:spindle|rpm|speed)\b",
            "risk_level": "high",
            "escalation_reason": "Exceeding maximum rated spindle RPM risks catastrophic tool holder explosion and bearing destruction.",
        },
        {
            "id": "RULE-COOLANT-SHUTOFF",
            "name": "Coolant Shutoff During Active Cutting Cycle",
            "pattern": r"\b(?:turn\s*off|shut\s*off|disable|stop)\b.{0,40}\b(?:flood|coolant|mist|high\s*pressure)\b.{0,40}\b(?:during|while|cutting|machining)",
            "risk_level": "high",
            "escalation_reason": "Disabling coolant during active cutting creates extreme thermal expansion, tool fracture, and potential titanium chip fire.",
        },
        {
            "id": "RULE-ESTOP-DISABLE",
            "name": "Emergency Stop Circuit Modification",
            "pattern": r"\b(?:disable|disconnect|short|jumper|reset)\b.{0,40}\b(?:e-stop|emergency\s*stop|safety\s*relay)",
            "risk_level": "critical",
            "escalation_reason": "Modifying or jumpering emergency stop circuits removes fail-safe operator protection.",
        },
        {
            "id": "RULE-HYDRAULIC-PRESSURE",
            "name": "Hydraulic Chuck Clamp Pressure Tampering",
            "pattern": r"\b(?:increase|boost|override|max\s*out)\b.{0,40}\b(?:hydraulic|chuck|clamping)\s*pressure",
            "risk_level": "medium",
            "escalation_reason": "Over-pressuring hydraulic chuck can distort thin-walled workpieces or rupture hydraulic lines.",
        },
    ]

    def evaluate(self, query_text: str) -> SafetyEscalationInfo:
        matched_rule_ids = []
        highest_risk = "none"
        escalation_reasons = []

        risk_priority = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}

        for rule in self.RULES:
            if re.search(rule["pattern"], query_text, re.IGNORECASE):
                matched_rule_ids.append(rule["name"])
                rule_risk = rule["risk_level"]
                escalation_reasons.append(rule["escalation_reason"])
                
                if risk_priority[rule_risk] > risk_priority[highest_risk]:
                    highest_risk = rule_risk

        is_critical = highest_risk in ["high", "critical"]

        return SafetyEscalationInfo(
            is_safety_critical=is_critical,
            risk_level=highest_risk,
            matched_rules=matched_rule_ids,
            escalation_reason="; ".join(escalation_reasons) if escalation_reasons else None,
            requires_expert_review=is_critical,
            review_item_id=None,
        )

safety_rules = SafetyRuleEngine()
