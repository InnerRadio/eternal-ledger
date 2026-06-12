import json
from datetime import datetime

from backend.app.database import SessionLocal
from backend.app.models import NginxSecurityEvent, NginxSecurityAlert
from backend.app.nginx_security_importer import import_nginx_security_logs
from backend.app.cms.reports import (
    build_nginx_threat_alerts,
    existing_nginx_alert_keys,
    nginx_alert_key,
)


def generate_nginx_security_alert_records(limit: int = 1000):
    db = SessionLocal()

    try:
        records = db.query(NginxSecurityEvent).order_by(
            NginxSecurityEvent.created_at.desc()
        ).limit(limit).all()

        alert_report = build_nginx_threat_alerts(records)
        known = existing_nginx_alert_keys(db)

        created = 0
        skipped = 0

        for alert in alert_report["alerts"]:
            key = nginx_alert_key(alert)

            if key in known:
                skipped += 1
                continue

            db.add(NginxSecurityAlert(
                severity=alert.get("severity"),
                alert_type=alert.get("type"),
                message=alert.get("message"),
                remote_ip=alert.get("remote_ip"),
                request_path=alert.get("request_path"),
                value=alert.get("value"),
                threshold=alert.get("threshold"),
                status="open",
                source="nginx_runner_v7",
            ))

            known.add(key)
            created += 1

        db.commit()

        return {
            "module": "Nginx Security Alert Runner",
            "status": "complete",
            "limit": limit,
            "events_analyzed": len(records),
            "alerts": {
                "created": created,
                "skipped": skipped,
                "detected": alert_report["alert_count"],
            },
            "threat_summary": alert_report["threat_summary"],
        }

    finally:
        db.close()


def run_nginx_security_pipeline(limit: int = 1000):
    started_at = datetime.utcnow()

    import_result = import_nginx_security_logs(limit=limit)
    alert_result = generate_nginx_security_alert_records(limit=limit)

    finished_at = datetime.utcnow()

    return {
        "module": "Nginx Security Pipeline Runner",
        "status": "complete",
        "limit": limit,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_seconds": round((finished_at - started_at).total_seconds(), 3),
        "steps": {
            "import": import_result,
            "alerts": alert_result,
        }
    }


if __name__ == "__main__":
    result = run_nginx_security_pipeline(limit=1000)
    print(json.dumps(result, indent=2, default=str))
