"""Mechanism 4 — Trigger/Action (spec §5, §9 /internal/trigger-check).

Runs as a daily Cloud Scheduler job hitting POST /internal/trigger-check. Scans
for time-based preventive gaps (assessment cadence, checkup gaps, mental-health
check-ins, policy renewals), writes rows to `notifications`, and fans out to
Pub/Sub. Idempotent-ish for the demo: it won't duplicate an unread notification
of the same (user, type).
"""
from __future__ import annotations

from datetime import date, timedelta

import config
import db


def run_daily_check() -> dict:
    created = 0
    created += _assessment_due()
    created += _renewals_due()
    created += _wellbeing_checkins()
    return {"notifications_created": created}


def _assessment_due() -> int:
    """Users whose last assessment is older than the overdue threshold (or none)."""
    rows = db.query(
        """
        SELECT u.id AS user_id,
               MAX(h.event_date) FILTER (WHERE h.event_type = 'assessment') AS last_assessment
        FROM users u
        LEFT JOIN health_events h ON h.user_id = u.id
        WHERE u.user_type = 'existing'
        GROUP BY u.id
        """
    )
    count = 0
    cutoff = (date.today() - timedelta(days=30 * config.ASSESSMENT_OVERDUE_MONTHS)).isoformat()
    for r in rows:
        last = r["last_assessment"]
        # normalise date/str to an ISO string so the comparison is dialect-safe
        last_s = last.isoformat() if hasattr(last, "isoformat") else last
        if last_s is None or last_s < cutoff:
            msg = ("Your last health assessment was over "
                   f"{config.ASSESSMENT_OVERDUE_MONTHS} months ago - you may be due for another."
                   if last else "We don't have a recent health assessment on file for you.")
            count += _notify(r["user_id"], "assessment_due", "health_assessment", msg)
    return count


def _renewals_due(within_days: int = 30) -> int:
    rows = db.query(
        "SELECT user_id, renewal_date FROM policies "
        "WHERE status = 'active' AND renewal_date IS NOT NULL "
        "AND renewal_date BETWEEN %s AND %s",
        (date.today(), date.today() + timedelta(days=within_days)),
    )
    count = 0
    for r in rows:
        msg = f"Your policy renews on {r['renewal_date']:%d %b %Y}."
        count += _notify(r["user_id"], "renewal_alarm", None, msg)
    return count


def _wellbeing_checkins() -> int:
    if db.IS_SQLITE:
        # SQLite: risk_flags is JSON text; match the key by substring (demo-grade).
        rows = db.query(
            "SELECT DISTINCT user_id FROM health_events "
            "WHERE risk_flags LIKE '%stress%'")
    else:
        rows = db.query(
            "SELECT DISTINCT user_id FROM health_events "
            "WHERE risk_flags ? 'stress' OR risk_flags ? 'high_stress'")
    count = 0
    for r in rows:
        msg = ("A quick wellbeing check-in might be worthwhile - support is "
               "available whenever you need it.")
        count += _notify(r["user_id"], "mh_checkin", "mental_health", msg)
    return count


def _notify(user_id, ntype: str, service_family, message: str) -> int:
    """Insert a notification unless an unread one of the same type already exists."""
    exists = db.query_one(
        "SELECT 1 FROM notifications WHERE user_id = %s AND type = %s AND read = false LIMIT 1",
        (user_id, ntype),
    )
    if exists:
        return 0
    db.execute(
        "INSERT INTO notifications (user_id, type, service_family, message) "
        "VALUES (%s, %s, %s, %s)",
        (user_id, ntype, service_family, message),
    )
    _publish(user_id, ntype, message)
    return 1


def _publish(user_id, ntype: str, message: str) -> None:
    """Fan out to Pub/Sub if configured (spec §5 Trigger/Action)."""
    if not config.PUBSUB_TOPIC or not config.GCP_PROJECT:
        return
    try:  # pragma: no cover - requires cloud env
        import json
        from google.cloud import pubsub_v1

        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(config.GCP_PROJECT, config.PUBSUB_TOPIC)
        payload = json.dumps({"user_id": str(user_id), "type": ntype, "message": message})
        publisher.publish(topic_path, payload.encode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"[trigger] pubsub publish skipped: {exc}")
