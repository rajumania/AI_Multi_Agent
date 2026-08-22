from typing import Dict, Any, List, Tuple


class PolicyEngine:
    """
    Campus Emergency Policy & Guardrail Engine.
    Determines whether agent-recommended actions may be executed autonomously by the system,
    or if they strictly require human commander authorization before deployment.
    """

    HIGH_IMPACT_KEYWORDS = [
        "broadcast",
        "siren",
        "campus-wide",
        "evacuate entire",
        "lockdown entire",
        "sms blast",
        "public alert",
        "power grid shutdown"
    ]

    def evaluate_plan_actions(self, actions: List[str], severity: str) -> Tuple[List[str], List[str], bool]:
        """
        Evaluates a list of recommended tactical actions against campus governance policy.
        Returns:
            - auto_executable_actions: List of safe actions agents can execute autonomously.
            - required_approvals: List of high-impact actions needing human commander authorization.
            - requires_approval: Boolean flag indicating if approval gateway is triggered.
        """
        auto_executable = []
        required_approvals = []

        is_critical = severity.lower() == "critical"

        for action in actions:
            act_lower = action.lower()
            is_high_impact = any(k in act_lower for k in self.HIGH_IMPACT_KEYWORDS)

            if is_high_impact or (is_critical and any(k in act_lower for k in ["dispatch", "deploy", "lockdown", "evacuate"])):
                required_approvals.append(action)
            else:
                auto_executable.append(action)

        requires_approval = len(required_approvals) > 0 or is_critical

        return auto_executable, required_approvals, requires_approval


policy_engine = PolicyEngine()
