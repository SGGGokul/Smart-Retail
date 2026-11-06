import datetime
import logging
from typing import Any, Dict, List, Optional
import uuid

from app.core.config import get_settings
from app.schemas.alerts import AlertItem, AlertUpdateRequest, Severity

logger = logging.getLogger("retailiq.rule_engine")


class RuleEngine:
    """Evaluates verified Computer Vision telemetry against operational retail rules

    to generate verifiable alerts. Every alert has a genuine CV source trigger.
    """

    def __init__(self) -> None:
        self._alerts: Dict[str, AlertItem] = {}
        self._alert_counter = 0

    def _next_alert_id(self) -> str:
        self._alert_counter += 1
        return f"al-{self._alert_counter:02d}"

    def evaluate_cv_results(self, cv_data: Dict[str, Any]) -> List[AlertItem]:
        """Evaluate a processed video's metrics and trigger rule-based alerts."""
        settings = get_settings()
        now_str = datetime.datetime.now().strftime("%H:%M")
        generated_alerts: List[AlertItem] = []

        peak_occupancy = cv_data.get("peak_occupancy", 0)
        avg_dwell_seconds = cv_data.get("average_dwell_seconds", 0.0)
        entries = cv_data.get("entries", 0)
        unique_customers = cv_data.get("unique_customers", 0)

        # Rule 1: Occupancy Critical or Warning Threshold Exceeded
        if peak_occupancy >= settings.ALERT_OCCUPANCY_CRITICAL_THRESHOLD:
            alert = AlertItem(
                id=self._next_alert_id(),
                type="Critical Store Occupancy",
                time=now_str,
                area="Main Floor",
                severity="critical",
                description=(
                    f"Peak occupancy reached {peak_occupancy} persons, exceeding critical "
                    f"safety threshold ({settings.ALERT_OCCUPANCY_CRITICAL_THRESHOLD})."
                ),
                acknowledged=False,
            )
            self._alerts[alert.id] = alert
            generated_alerts.append(alert)
        elif peak_occupancy >= settings.ALERT_OCCUPANCY_WARNING_THRESHOLD:
            alert = AlertItem(
                id=self._next_alert_id(),
                type="High Store Occupancy",
                time=now_str,
                area="Main Floor",
                severity="warning",
                description=(
                    f"Peak occupancy reached {peak_occupancy} persons, exceeding warning "
                    f"threshold ({settings.ALERT_OCCUPANCY_WARNING_THRESHOLD})."
                ),
                acknowledged=False,
            )
            self._alerts[alert.id] = alert
            generated_alerts.append(alert)

        # Rule 2: Customer Dwell Time Threshold Exceeded
        if avg_dwell_seconds >= settings.ALERT_DWELL_SECONDS_THRESHOLD:
            alert = AlertItem(
                id=self._next_alert_id(),
                type="Prolonged Dwell Time",
                time=now_str,
                area="Department Aisles",
                severity="warning",
                description=(
                    f"Average customer dwell time reached {avg_dwell_seconds:.1f} seconds, "
                    f"exceeding expected threshold ({settings.ALERT_DWELL_SECONDS_THRESHOLD:.0f}s)."
                ),
                acknowledged=False,
            )
            self._alerts[alert.id] = alert
            generated_alerts.append(alert)

        # Rule 3: High Entrance Traffic Surge
        if entries >= settings.ALERT_ENTRY_SURGE_THRESHOLD or (unique_customers >= 25 and entries >= 10):
            alert = AlertItem(
                id=self._next_alert_id(),
                type="Customer Influx Surge",
                time=now_str,
                area="Entrance Zone",
                severity="info",
                description=(
                    f"Entrance zone observed a traffic surge with {entries} registered entries "
                    f"and {unique_customers} unique visitors."
                ),
                acknowledged=False,
            )
            self._alerts[alert.id] = alert
            generated_alerts.append(alert)

        if generated_alerts:
            logger.info(f"RuleEngine generated {len(generated_alerts)} alerts from CV event data.")

        return generated_alerts

    def list_alerts(
        self,
        severity: Optional[str] = None,
        acknowledged: Optional[bool] = None,
    ) -> List[AlertItem]:
        """List all alerts filtered by severity and acknowledgment state."""
        alerts = list(self._alerts.values())

        if severity and severity.lower() != "all":
            alerts = [a for a in alerts if a.severity.lower() == severity.lower()]

        if acknowledged is not None:
            alerts = [a for a in alerts if a.acknowledged == acknowledged]

        # Sort newest first
        return list(reversed(alerts))

    def get_alert(self, alert_id: str) -> Optional[AlertItem]:
        """Retrieve single alert by identifier."""
        return self._alerts.get(alert_id)

    def update_alert(self, alert_id: str, update: AlertUpdateRequest) -> Optional[AlertItem]:
        """Update an alert's status (acknowledgment / notes)."""
        alert = self._alerts.get(alert_id)
        if alert is None:
            return None

        # Return updated copy
        updated = alert.model_copy(update={"acknowledged": update.acknowledged})
        self._alerts[alert_id] = updated
        logger.info(f"Alert {alert_id} updated: acknowledged={update.acknowledged}")
        return updated


_rule_engine: Optional[RuleEngine] = None


def get_rule_engine() -> RuleEngine:
    """Singleton getter for the rule engine."""
    global _rule_engine
    if _rule_engine is None:
        _rule_engine = RuleEngine()
    return _rule_engine
