from typing import List
from libs.events.schemas import Severity
from ..domain.entities.security_finding import SecurityFinding

def calculate_security_score(findings: List[SecurityFinding]) -> int:
    """
    Calculates the security risk score starting at 100 and deducting points:
      - CRITICAL: -20
      - HIGH: -10
      - MEDIUM: -5
      - LOW: -2
      - INFO: -0
    Clamped between 0 and 100.
    """
    score = 100
    for f in findings:
        if f.severity == Severity.CRITICAL:
            score -= 20
        elif f.severity == Severity.HIGH:
            score -= 10
        elif f.severity == Severity.MEDIUM:
            score -= 5
        elif f.severity == Severity.LOW:
            score -= 2
        # INFO findings carry no penalty

    return max(0, score)
