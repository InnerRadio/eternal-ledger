from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime

from backend.app.database import get_db
from backend.app.models import (
    MetricEvent,
    Memorial,
    MediaAsset,
    Contribution,
    AffiliateClick,
    AffiliateConversion,
    AccountSecurityEvent,
    AffiliateCommission,
    NginxSecurityEvent,
    NginxSecurityAlert,
    NginxSecurityActivation,
    NginxAlertSuppression,
    NginxSecurityIncident,
)
from backend.app.cms.security import require_roles

router = APIRouter(prefix="/cms/reports", tags=["CMS Reports"])


def metric_count_by_field(records, field):
    result = {}

    for record in records:
        value = getattr(record, field, None) or "unknown"

        if value not in result:
            result[value] = {
                "count": 0
            }

        result[value]["count"] += 1

    return result


def serialize_metric_event(event: MetricEvent):
    return {
        "id": event.id,
        "event_type": event.event_type,
        "project": event.project,
        "source": event.source,
        "actor_user_id": event.actor_user_id,
        "session_id": event.session_id,
        "target_type": event.target_type,
        "target_id": event.target_id,
        "campaign_id": event.campaign_id,
        "organization_id": event.organization_id,
        "affiliate_id": event.affiliate_id,
        "referral_code": event.referral_code,
        "page_url": event.page_url,
        "metadata_json": event.metadata_json,
        "client_event_at": event.client_event_at,
        "created_at": event.created_at,
    }


def ranked_metric_counts(records, field, limit: int = 25):
    counts = metric_count_by_field(records, field)

    ranked = [
        {
            field: key,
            "count": value["count"],
        }
        for key, value in counts.items()
        if key != "unknown"
    ]

    ranked.sort(key=lambda item: item["count"], reverse=True)

    return [
        {
            "rank": index + 1,
            **item
        }
        for index, item in enumerate(ranked[:limit])
    ]


def metric_records_for_project(db: Session, project: str | None = None):
    query = db.query(MetricEvent)

    if project:
        query = query.filter(MetricEvent.project == project)

    return query.all()


def commission_total_cents(records):
    return sum(
        record.amount_cents or 0
        for record in records
    )


def build_funnel_summary(
    views_count: int,
    clicks_count: int,
    enrollments_count: int,
    conversions_count: int,
    commissions_count: int,
    commission_cents: int
):
    click_through_rate = round((clicks_count / views_count) * 100, 2) if views_count else 0
    enrollment_rate = round((enrollments_count / clicks_count) * 100, 2) if clicks_count else 0
    conversion_rate = round((conversions_count / enrollments_count) * 100, 2) if enrollments_count else 0
    commission_per_conversion_cents = round(commission_cents / conversions_count, 2) if conversions_count else 0

    return {
        "views": views_count,
        "clicks": clicks_count,
        "enrollments": enrollments_count,
        "conversions": conversions_count,
        "commissions": commissions_count,
        "commission_cents": commission_cents,
        "rates": {
            "click_through_rate_percent": click_through_rate,
            "enrollment_rate_percent": enrollment_rate,
            "conversion_rate_percent": conversion_rate,
            "commission_per_conversion_cents": commission_per_conversion_cents,
        }
    }


def group_metric_events_by_session(records):
    sessions = {}

    for record in records:
        session_id = record.session_id or "unknown"

        if session_id not in sessions:
            sessions[session_id] = []

        sessions[session_id].append(record)

    return sessions


def serialize_session_summary(session_id, events):
    ordered = sorted(events, key=lambda event: event.client_event_at or event.created_at)

    start_time = (ordered[0].client_event_at or ordered[0].created_at) if ordered else None
    end_time = (ordered[-1].client_event_at or ordered[-1].created_at) if ordered else None

    duration_seconds = 0

    if start_time and end_time:
        duration_seconds = round((end_time - start_time).total_seconds(), 2)

    page_urls = sorted(set([
        event.page_url
        for event in ordered
        if event.page_url
    ]))

    event_types = metric_count_by_field(ordered, "event_type")

    scroll_events = [
        event
        for event in ordered
        if event.event_type == "scroll_depth"
    ]

    return {
        "session_id": session_id,
        "events": len(ordered),
        "duration_seconds": duration_seconds,
        "pages_visited": len(page_urls),
        "page_urls": page_urls,
        "first_event_type": ordered[0].event_type if ordered else None,
        "last_event_type": ordered[-1].event_type if ordered else None,
        "event_types": event_types,
        "scroll_events": len(scroll_events),
        "started_at": start_time,
        "ended_at": end_time,
    }


def serialize_account_security_event(event: AccountSecurityEvent):
    return {
        "id": event.id,
        "user_id": event.user_id,
        "email": event.email,
        "event_type": event.event_type,
        "status": event.status,
        "ip_address": event.ip_address,
        "user_agent": event.user_agent,
        "created_at": event.created_at,
    }


def serialize_nginx_security_event(event: NginxSecurityEvent):
    return {
        "id": event.id,
        "remote_ip": event.remote_ip,
        "request_method": event.request_method,
        "request_path": event.request_path,
        "status_code": event.status_code,
        "user_agent": event.user_agent,
        "referer": event.referer,
        "country": event.country,
        "source": event.source,
        "created_at": event.created_at,
    }


@router.get("/nginx/events")
def cms_nginx_security_events_report(
    remote_ip: str | None = None,
    request_method: str | None = None,
    status_code: int | None = None,
    request_path: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    query = db.query(NginxSecurityEvent)

    if remote_ip:
        query = query.filter(NginxSecurityEvent.remote_ip == remote_ip)

    if request_method:
        query = query.filter(NginxSecurityEvent.request_method == request_method)

    if status_code:
        query = query.filter(NginxSecurityEvent.status_code == status_code)

    if request_path:
        query = query.filter(NginxSecurityEvent.request_path.contains(request_path))

    records = query.order_by(NginxSecurityEvent.created_at.desc()).limit(limit).all()

    return {
        "module": "CMS Nginx Security Events",
        "status": "active",
        "count": len(records),
        "filters": {
            "remote_ip": remote_ip,
            "request_method": request_method,
            "status_code": status_code,
            "request_path": request_path,
            "limit": limit,
        },
        "records": [
            serialize_nginx_security_event(event)
            for event in records
        ]
    }


@router.get("/nginx/summary")
def cms_nginx_security_summary_report(
    limit: int = 1000,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    records = db.query(NginxSecurityEvent).order_by(
        NginxSecurityEvent.created_at.desc()
    ).limit(limit).all()

    return {
        "module": "CMS Nginx Security Summary",
        "status": "active",
        "count": len(records),
        "filters": {
            "limit": limit,
        },
        "summary": {
            "by_remote_ip": metric_count_by_field(records, "remote_ip"),
            "by_request_method": metric_count_by_field(records, "request_method"),
            "by_status_code": metric_count_by_field(records, "status_code"),
            "by_request_path": metric_count_by_field(records, "request_path"),
            "by_country": metric_count_by_field(records, "country"),
        }
    }


@router.get("/nginx/intelligence")
def cms_nginx_security_intelligence_report(
    limit: int = 1000,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    records = db.query(NginxSecurityEvent).order_by(
        NginxSecurityEvent.created_at.desc()
    ).limit(limit).all()

    error_records = [
        record
        for record in records
        if record.status_code and record.status_code >= 400
    ]

    suspicious_path_records = [
        record
        for record in records
        if record.request_path and any(token in record.request_path.lower() for token in [
            "wp-admin",
            "wp-login",
            ".env",
            "phpmyadmin",
            "xmlrpc",
            "admin.php",
            "config",
            "shell",
        ])
    ]

    return {
        "module": "CMS Nginx Security Intelligence",
        "status": "active",
        "count": len(records),
        "filters": {
            "limit": limit,
        },
        "records": {
            "top_remote_ip_addresses": ranked_metric_counts(records, "remote_ip", 25),
            "top_status_codes": ranked_metric_counts(records, "status_code", 25),
            "top_request_paths": ranked_metric_counts(records, "request_path", 25),
            "top_user_agents": ranked_metric_counts(records, "user_agent", 25),
            "error_ip_addresses": ranked_metric_counts(error_records, "remote_ip", 25),
            "suspicious_paths": ranked_metric_counts(suspicious_path_records, "request_path", 25),
            "suspicious_ip_addresses": ranked_metric_counts(suspicious_path_records, "remote_ip", 25),
        }
    }


def classify_nginx_threat(event: NginxSecurityEvent):
    path = (event.request_path or "").lower()
    user_agent = (event.user_agent or "").lower()
    status_code = event.status_code or 0

    critical_patterns = [
        ".env",
        ".git/config",
        "wp_filemanager",
        "shell",
        "backdoor",
        "config.php",
    ]

    high_patterns = [
        "wp-admin",
        "wp-login",
        "admin.php",
        "xmlrpc",
        "phpmyadmin",
    ]

    medium_patterns = [
        "_next",
        "_nuxt",
        "actuator",
        "bundle.js",
        "main.js",
    ]

    low_patterns = [
        "robots.txt",
        "favicon.ico",
    ]

    if any(pattern in path for pattern in critical_patterns):
        return {
            "severity": "critical",
            "score": 10,
            "matched_path": event.request_path,
            "matched_agent": event.user_agent,
        }

    if any(pattern in path for pattern in high_patterns):
        return {
            "severity": "high",
            "score": 5,
            "matched_path": event.request_path,
            "matched_agent": event.user_agent,
        }

    if any(pattern in path for pattern in medium_patterns):
        return {
            "severity": "medium",
            "score": 2,
            "matched_path": event.request_path,
            "matched_agent": event.user_agent,
        }

    if any(pattern in path for pattern in low_patterns):
        return {
            "severity": "low",
            "score": 1,
            "matched_path": event.request_path,
            "matched_agent": event.user_agent,
        }

    if status_code >= 500:
        return {
            "severity": "high",
            "score": 5,
            "matched_path": event.request_path,
            "matched_agent": event.user_agent,
        }

    if status_code in [401, 403, 404, 405]:
        return {
            "severity": "low",
            "score": 1,
            "matched_path": event.request_path,
            "matched_agent": event.user_agent,
        }

    return {
        "severity": "informational",
        "score": 0,
        "matched_path": event.request_path,
        "matched_agent": event.user_agent,
    }


def threat_level_from_score(score: int):
    if score >= 500:
        return "critical"

    if score >= 200:
        return "high"

    if score >= 75:
        return "medium"

    if score >= 20:
        return "low"

    return "informational"


def summarize_threat_records(records):
    severity_counts = {
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "informational": 0,
    }

    score_by_ip = {}
    count_by_ip = {}
    score_by_path = {}
    count_by_path = {}

    total_score = 0

    classified = []

    for event in records:
        classification = classify_nginx_threat(event)
        severity = classification["severity"]
        score = classification["score"]

        severity_counts[severity] += 1
        total_score += score

        ip = event.remote_ip or "unknown"
        path = event.request_path or "unknown"

        score_by_ip[ip] = score_by_ip.get(ip, 0) + score
        count_by_ip[ip] = count_by_ip.get(ip, 0) + 1

        score_by_path[path] = score_by_path.get(path, 0) + score
        count_by_path[path] = count_by_path.get(path, 0) + 1

        classified.append({
            "id": event.id,
            "remote_ip": event.remote_ip,
            "request_method": event.request_method,
            "request_path": event.request_path,
            "status_code": event.status_code,
            "source": event.source,
            "created_at": event.created_at,
            "severity": severity,
            "score": score,
        })

    top_attackers = [
        {
            "rank": index + 1,
            "remote_ip": ip,
            "score": score,
            "events": count_by_ip.get(ip, 0),
        }
        for index, (ip, score) in enumerate(
            sorted(score_by_ip.items(), key=lambda item: item[1], reverse=True)[:25]
        )
    ]

    top_vectors = [
        {
            "rank": index + 1,
            "request_path": path,
            "score": score,
            "events": count_by_path.get(path, 0),
        }
        for index, (path, score) in enumerate(
            sorted(score_by_path.items(), key=lambda item: item[1], reverse=True)[:25]
        )
    ]

    classified.sort(
        key=lambda item: (
            item["score"],
            item["created_at"],
        ),
        reverse=True
    )

    return {
        "threat_score": total_score,
        "threat_level": threat_level_from_score(total_score),
        "severity_counts": severity_counts,
        "top_attackers": top_attackers,
        "top_vectors": top_vectors,
        "highest_severity_events": classified[:50],
    }


@router.get("/nginx/threats")
def cms_nginx_threat_intelligence_report(
    limit: int = 1000,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    records = db.query(NginxSecurityEvent).order_by(
        NginxSecurityEvent.created_at.desc()
    ).limit(limit).all()

    summary = summarize_threat_records(records)

    return {
        "module": "CMS Nginx Threat Intelligence",
        "status": "active",
        "count": len(records),
        "filters": {
            "limit": limit,
        },
        "summary": summary,
    }


def count_nginx_path_contains(records, token: str):
    token = token.lower()

    return len([
        record
        for record in records
        if record.request_path and token in record.request_path.lower()
    ])


def count_nginx_status(records, status_code: int):
    return len([
        record
        for record in records
        if record.status_code == status_code
    ])


def build_nginx_threat_alerts(records):
    summary = summarize_threat_records(records)

    alerts = []

    threat_score = summary["threat_score"]

    if threat_score >= 500:
        alerts.append({
            "severity": "critical",
            "type": "threat_score",
            "message": "Overall Nginx threat score exceeded critical threshold.",
            "value": threat_score,
            "threshold": 500,
        })

    env_count = count_nginx_path_contains(records, ".env")

    if env_count:
        alerts.append({
            "severity": "critical",
            "type": "env_probe",
            "message": ".env probe attempts detected.",
            "value": env_count,
            "threshold": 1,
        })

    git_count = count_nginx_path_contains(records, ".git/config")

    if git_count:
        alerts.append({
            "severity": "critical",
            "type": "git_probe",
            "message": ".git/config probe attempts detected.",
            "value": git_count,
            "threshold": 1,
        })

    wp_filemanager_count = count_nginx_path_contains(records, "wp_filemanager")

    if wp_filemanager_count:
        alerts.append({
            "severity": "critical",
            "type": "wp_filemanager_probe",
            "message": "WordPress file manager exploit probes detected.",
            "value": wp_filemanager_count,
            "threshold": 1,
        })

    for attacker in summary["top_attackers"]:
        if attacker["events"] >= 100:
            alerts.append({
                "severity": "high",
                "type": "aggressive_ip_event_volume",
                "message": f'{attacker["remote_ip"]} generated high request volume.',
                "remote_ip": attacker["remote_ip"],
                "value": attacker["events"],
                "threshold": 100,
            })

        if attacker["score"] >= 100:
            alerts.append({
                "severity": "high",
                "type": "aggressive_ip_threat_score",
                "message": f'{attacker["remote_ip"]} generated high threat score.',
                "remote_ip": attacker["remote_ip"],
                "value": attacker["score"],
                "threshold": 100,
            })

    not_found_count = count_nginx_status(records, 404)

    if not_found_count >= 250:
        alerts.append({
            "severity": "medium",
            "type": "high_404_volume",
            "message": "High volume of 404 probing detected.",
            "value": not_found_count,
            "threshold": 250,
        })

    forbidden_count = count_nginx_status(records, 403)

    if forbidden_count >= 100:
        alerts.append({
            "severity": "medium",
            "type": "high_403_volume",
            "message": "High volume of forbidden-path probing detected.",
            "value": forbidden_count,
            "threshold": 100,
        })

    for vector in summary["top_vectors"]:
        if vector["events"] >= 10:
            alerts.append({
                "severity": "low",
                "type": "repeated_vector_probe",
                "message": "Repeated probing of the same request path detected.",
                "request_path": vector["request_path"],
                "value": vector["events"],
                "threshold": 10,
            })

    severity_order = {
        "critical": 4,
        "high": 3,
        "medium": 2,
        "low": 1,
        "informational": 0,
    }

    alerts.sort(
        key=lambda alert: (
            severity_order.get(alert["severity"], 0),
            alert.get("value", 0),
        ),
        reverse=True
    )

    return {
        "alert_count": len(alerts),
        "alerts": alerts,
        "threat_summary": {
            "threat_score": summary["threat_score"],
            "threat_level": summary["threat_level"],
            "severity_counts": summary["severity_counts"],
        }
    }


def serialize_nginx_security_alert(alert: NginxSecurityAlert):
    return {
        "id": alert.id,
        "severity": alert.severity,
        "alert_type": alert.alert_type,
        "message": alert.message,
        "remote_ip": alert.remote_ip,
        "request_path": alert.request_path,
        "value": alert.value,
        "threshold": alert.threshold,
        "status": alert.status,
        "source": alert.source,
        "created_at": alert.created_at,
        "reviewed_at": alert.reviewed_at,
        "resolved_at": alert.resolved_at,
    }


def load_active_nginx_suppressions(db: Session):
    return db.query(NginxAlertSuppression).filter(
        NginxAlertSuppression.status == "active"
    ).all()


def nginx_alert_matches_suppression(alert: dict, suppression: NginxAlertSuppression):
    alert_type = alert.get("type")
    request_path = alert.get("request_path")
    remote_ip = alert.get("remote_ip")

    if suppression.alert_type and suppression.alert_type != alert_type:
        return False

    if suppression.request_path and suppression.request_path != request_path:
        return False

    if suppression.remote_ip and suppression.remote_ip != remote_ip:
        return False

    return True


def filter_suppressed_nginx_alerts(db: Session, alerts: list[dict]):
    suppressions = load_active_nginx_suppressions(db)

    active_alerts = []
    suppressed_alerts = []

    for alert in alerts:
        matched = None

        for suppression in suppressions:
            if nginx_alert_matches_suppression(alert, suppression):
                matched = suppression
                break

        if matched:
            suppressed_alerts.append({
                **alert,
                "suppressed_by": matched.id,
            })
        else:
            active_alerts.append(alert)

    return {
        "active_alerts": active_alerts,
        "suppressed_alerts": suppressed_alerts,
        "suppression_count": len(suppressed_alerts),
    }


def nginx_alert_key(alert):
    return (
        alert.get("severity"),
        alert.get("type"),
        alert.get("message"),
        alert.get("remote_ip"),
        alert.get("request_path"),
        alert.get("value"),
        alert.get("threshold"),
    )


def existing_nginx_alert_keys(db: Session):
    records = db.query(NginxSecurityAlert).all()

    return set([
        (
            record.severity,
            record.alert_type,
            record.message,
            record.remote_ip,
            record.request_path,
            record.value,
            record.threshold,
        )
        for record in records
    ])


@router.get("/nginx/alerts")
def cms_nginx_threat_alerts_report(
    limit: int = 1000,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    records = db.query(NginxSecurityEvent).order_by(
        NginxSecurityEvent.created_at.desc()
    ).limit(limit).all()

    alert_report = build_nginx_threat_alerts(records)
    suppression_result = filter_suppressed_nginx_alerts(
        db,
        alert_report["alerts"]
    )

    alert_report["alerts"] = suppression_result["active_alerts"]
    alert_report["alert_count"] = len(alert_report["alerts"])

    return {
        "module": "CMS Nginx Threat Alerts",
        "status": "active",
        "count": len(records),
        "filters": {
            "limit": limit,
        },
        "suppression": {
            "suppressed": suppression_result["suppression_count"],
            "records": suppression_result["suppressed_alerts"],
        },
        **alert_report,
    }


@router.get("/nginx/alerts/ledger")
def cms_nginx_alert_ledger_report(
    severity: str | None = None,
    alert_type: str | None = None,
    status: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    query = db.query(NginxSecurityAlert)

    if severity:
        query = query.filter(NginxSecurityAlert.severity == severity)

    if alert_type:
        query = query.filter(NginxSecurityAlert.alert_type == alert_type)

    if status:
        query = query.filter(NginxSecurityAlert.status == status)

    records = query.order_by(
        NginxSecurityAlert.created_at.desc()
    ).limit(limit).all()

    return {
        "module": "CMS Nginx Security Alert Ledger",
        "status": "active",
        "count": len(records),
        "filters": {
            "severity": severity,
            "alert_type": alert_type,
            "status": status,
            "limit": limit,
        },
        "records": [
            serialize_nginx_security_alert(alert)
            for alert in records
        ]
    }


@router.post("/nginx/alerts/generate")
def cms_generate_nginx_security_alerts(
    limit: int = 1000,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    records = db.query(NginxSecurityEvent).order_by(
        NginxSecurityEvent.created_at.desc()
    ).limit(limit).all()

    alert_report = build_nginx_threat_alerts(records)
    suppression_result = filter_suppressed_nginx_alerts(
        db,
        alert_report["alerts"]
    )

    alert_report["alerts"] = suppression_result["active_alerts"]
    alert_report["alert_count"] = len(alert_report["alerts"])

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
            source="nginx_alerts_v5",
        ))

        known.add(key)
        created += 1

    db.commit()

    return {
        "module": "CMS Nginx Security Alert Generator",
        "status": "complete",
        "count": len(records),
        "filters": {
            "limit": limit,
        },
        "generated": {
            "created": created,
            "skipped": skipped,
            "total_alerts_detected": alert_report["alert_count"],
            "suppressed": suppression_result["suppression_count"],
        },
        "suppression": {
            "records": suppression_result["suppressed_alerts"],
        },
        "threat_summary": alert_report["threat_summary"],
    }



@router.get("/nginx/geoip")
def cms_nginx_geoip_intelligence_report(
    limit: int = 1000,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    records = db.query(NginxSecurityEvent).order_by(
        NginxSecurityEvent.created_at.desc()
    ).limit(limit).all()

    total = len(records)

    enriched_records = [
        record
        for record in records
        if record.country
    ]

    unenriched_records = [
        record
        for record in records
        if not record.country
    ]

    return {
        "module": "CMS Nginx GeoIP Intelligence",
        "status": "active",
        "count": total,
        "filters": {
            "limit": limit,
        },
        "geoip_status": {
            "available": False,
            "mode": "prepared",
            "message": "GeoIP database is not installed yet. Country field is ready for enrichment.",
        },
        "coverage": {
            "enriched": len(enriched_records),
            "unenriched": len(unenriched_records),
            "enriched_percent": round((len(enriched_records) / total) * 100, 2) if total else 0,
        },
        "countries": ranked_metric_counts(enriched_records, "country", 25),
        "top_unenriched_ip_addresses": ranked_metric_counts(unenriched_records, "remote_ip", 25),
    }


def bucket_records_by_hour(records, datetime_field: str = "created_at"):
    buckets = {}

    for record in records:
        value = getattr(record, datetime_field, None)

        if not value:
            continue

        hour = value.strftime("%Y-%m-%d %H:00")

        if hour not in buckets:
            buckets[hour] = 0

        buckets[hour] += 1

    return [
        {
            "hour": hour,
            "count": count,
        }
        for hour, count in sorted(buckets.items())
    ]


@router.get("/nginx/trends")
def cms_nginx_security_trends_report(
    limit: int = 1000,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    events = db.query(NginxSecurityEvent).order_by(
        NginxSecurityEvent.created_at.desc()
    ).limit(limit).all()

    alerts = db.query(NginxSecurityAlert).order_by(
        NginxSecurityAlert.created_at.desc()
    ).limit(limit).all()

    critical_events = [
        event
        for event in events
        if classify_nginx_threat(event).get("severity") == "critical"
    ]

    return {
        "module": "CMS Nginx Security Trends",
        "status": "active",
        "filters": {
            "limit": limit,
        },
        "events": {
            "count": len(events),
            "by_hour": bucket_records_by_hour(events),
            "critical_by_hour": bucket_records_by_hour(critical_events),
        },
        "alerts": {
            "count": len(alerts),
            "by_status": metric_count_by_field(alerts, "status"),
            "by_severity": metric_count_by_field(alerts, "severity"),
            "by_type": metric_count_by_field(alerts, "alert_type"),
            "by_hour": bucket_records_by_hour(alerts),
        },
    }


def nginx_path_block_reason(path: str):
    lowered = (path or "").lower()

    block_patterns = [
        ".env",
        ".git/config",
        "wp_filemanager",
        "xmlrpc",
        "wp-login",
        "phpmyadmin",
    ]

    for pattern in block_patterns:
        if pattern in lowered:
            return pattern

    return None


@router.get("/nginx/blocking-recommendations")
def cms_nginx_blocking_recommendations_report(
    limit: int = 1000,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    records = db.query(NginxSecurityEvent).order_by(
        NginxSecurityEvent.created_at.desc()
    ).limit(limit).all()

    summary = summarize_threat_records(records)

    block_ip_candidates = []
    watch_ip_candidates = []

    for attacker in summary["top_attackers"]:
        score = attacker.get("score", 0)
        events = attacker.get("events", 0)

        if score >= 250 or events >= 250:
            block_ip_candidates.append({
                **attacker,
                "recommendation": "block",
                "reason": "Threat score or request volume exceeded block threshold.",
                "thresholds": {
                    "score": 250,
                    "events": 250,
                }
            })

        elif score >= 100 or events >= 100:
            watch_ip_candidates.append({
                **attacker,
                "recommendation": "watch",
                "reason": "Threat score or request volume exceeded watch threshold.",
                "thresholds": {
                    "score": 100,
                    "events": 100,
                }
            })

    block_path_candidates = []
    watch_path_candidates = []

    for vector in summary["top_vectors"]:
        path = vector.get("request_path")
        score = vector.get("score", 0)
        events = vector.get("events", 0)

        block_reason = nginx_path_block_reason(path)

        if block_reason:
            block_path_candidates.append({
                **vector,
                "recommendation": "block_path_pattern",
                "reason": f"Path matched high-risk probe pattern: {block_reason}",
            })

        elif score >= 25 or events >= 10:
            watch_path_candidates.append({
                **vector,
                "recommendation": "watch_path_pattern",
                "reason": "Repeated path probing exceeded watch threshold.",
                "thresholds": {
                    "score": 25,
                    "events": 10,
                }
            })

    return {
        "module": "CMS Nginx Blocking Recommendations",
        "status": "active",
        "mode": "recommendation_only",
        "filters": {
            "limit": limit,
        },
        "summary": {
            "events_analyzed": len(records),
            "threat_score": summary["threat_score"],
            "threat_level": summary["threat_level"],
        },
        "recommendations": {
            "block_ip_candidates": block_ip_candidates,
            "watch_ip_candidates": watch_ip_candidates,
            "block_path_candidates": block_path_candidates,
            "watch_path_candidates": watch_path_candidates,
        },
        "safety": {
            "auto_blocking_enabled": False,
            "message": "Recommendations only. No firewall or Nginx rules were changed.",
        }
    }


@router.get("/nginx/firewall-export")
def cms_nginx_firewall_export_report(
    limit: int = 1000,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    records = db.query(NginxSecurityEvent).order_by(
        NginxSecurityEvent.created_at.desc()
    ).limit(limit).all()

    summary = summarize_threat_records(records)

    deny_ips = []

    for attacker in summary["top_attackers"]:
        score = attacker.get("score", 0)
        events = attacker.get("events", 0)
        remote_ip = attacker.get("remote_ip")

        if remote_ip and (score >= 250 or events >= 250):
            deny_ips.append(remote_ip)

    block_path_patterns = [
        ".env",
        ".git/config",
        "wp_filemanager",
        "xmlrpc",
        "wp-login",
        "phpmyadmin",
    ]

    nginx_deny_ip_lines = [
        f"deny {ip};"
        for ip in deny_ips
    ]

    nginx_block_location = """location ~* (\\.env|\\.git/config|wp_filemanager|xmlrpc|wp-login|phpmyadmin) {
    return 403;
}"""

    return {
        "module": "CMS Nginx Firewall Export",
        "status": "active",
        "mode": "export_only",
        "filters": {
            "limit": limit,
        },
        "summary": {
            "events_analyzed": len(records),
            "threat_score": summary["threat_score"],
            "threat_level": summary["threat_level"],
        },
        "exports": {
            "nginx_deny_ips": nginx_deny_ip_lines,
            "nginx_block_location": nginx_block_location,
            "fail2ban_candidates": deny_ips,
            "block_path_patterns": block_path_patterns,
        },
        "safety": {
            "auto_apply_enabled": False,
            "message": "Export only. No Nginx, firewall, or fail2ban rules were changed.",
        }
    }


def serialize_nginx_security_activation(record: NginxSecurityActivation):
    return {
        "id": record.id,
        "domain": record.domain,
        "config_path": record.config_path,
        "include_path": record.include_path,
        "status": record.status,
        "notes": record.notes,
        "activated_at": record.activated_at,
        "created_at": record.created_at,
    }


@router.get("/nginx/activations")
def cms_nginx_security_activations_report(
    domain: str | None = None,
    status: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    query = db.query(NginxSecurityActivation)

    if domain:
        query = query.filter(NginxSecurityActivation.domain == domain)

    if status:
        query = query.filter(NginxSecurityActivation.status == status)

    records = query.order_by(
        NginxSecurityActivation.created_at.desc()
    ).limit(limit).all()

    return {
        "module": "CMS Nginx Security Activation Ledger",
        "status": "active",
        "count": len(records),
        "filters": {
            "domain": domain,
            "status": status,
            "limit": limit,
        },
        "records": [
            serialize_nginx_security_activation(record)
            for record in records
        ]
    }


@router.post("/nginx/activations/record")
def cms_record_nginx_security_activation(
    domain: str,
    config_path: str,
    include_path: str,
    notes: str | None = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    existing = db.query(NginxSecurityActivation).filter(
        NginxSecurityActivation.domain == domain,
        NginxSecurityActivation.config_path == config_path,
        NginxSecurityActivation.include_path == include_path,
        NginxSecurityActivation.status == "active",
    ).first()

    if existing:
        return {
            "module": "CMS Nginx Security Activation Recorder",
            "status": "exists",
            "record": serialize_nginx_security_activation(existing),
        }

    record = NginxSecurityActivation(
        domain=domain,
        config_path=config_path,
        include_path=include_path,
        status="active",
        notes=notes,
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    return {
        "module": "CMS Nginx Security Activation Recorder",
        "status": "recorded",
        "record": serialize_nginx_security_activation(record),
    }


def hours_between(start, end):
    if not start or not end:
        return None

    return round((end - start).total_seconds() / 3600, 2)


def average_number(values):
    clean = [
        value
        for value in values
        if value is not None
    ]

    if not clean:
        return None

    return round(sum(clean) / len(clean), 2)


def serialize_nginx_security_incident(record: NginxSecurityIncident):
    return {
        "id": record.id,
        "alert_type": record.alert_type,
        "severity": record.severity,
        "status": record.status,
        "occurrences": record.occurrences,
        "first_seen": record.first_seen,
        "last_seen": record.last_seen,
        "notes": record.notes,
        "created_at": record.created_at,
        "reviewed_at": record.reviewed_at,
        "resolved_at": record.resolved_at,
    }


def incident_severity_rank(severity: str):
    ranks = {
        "critical": 4,
        "high": 3,
        "medium": 2,
        "low": 1,
        "informational": 0,
    }

    return ranks.get(severity or "informational", 0)


@router.post("/nginx/incidents/generate")
def cms_generate_nginx_security_incidents(
    status: str | None = "open",
    limit: int = 1000,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    query = db.query(NginxSecurityAlert)

    if status:
        query = query.filter(NginxSecurityAlert.status == status)

    alerts = query.order_by(
        NginxSecurityAlert.created_at.asc()
    ).limit(limit).all()

    grouped = {}

    for alert in alerts:
        key = alert.alert_type

        if key not in grouped:
            grouped[key] = []

        grouped[key].append(alert)

    created = 0
    updated = 0

    for alert_type, records in grouped.items():
        first_seen = min(record.created_at for record in records)
        last_seen = max(record.created_at for record in records)

        severity = sorted(
            [record.severity for record in records],
            key=incident_severity_rank,
            reverse=True
        )[0]

        incident = db.query(NginxSecurityIncident).filter(
            NginxSecurityIncident.alert_type == alert_type,
            NginxSecurityIncident.status == "open",
        ).first()

        if not incident:
            incident = NginxSecurityIncident(
                alert_type=alert_type,
                severity=severity,
                status="open",
                occurrences=len(records),
                first_seen=first_seen,
                last_seen=last_seen,
                notes="Generated from Nginx alert correlation.",
            )

            db.add(incident)
            created += 1
        else:
            incident.severity = severity
            incident.occurrences = len(records)
            incident.first_seen = first_seen
            incident.last_seen = last_seen

            updated += 1

    db.commit()

    return {
        "module": "CMS Nginx Security Incident Generator",
        "status": "complete",
        "filters": {
            "alert_status": status,
            "limit": limit,
        },
        "alerts_analyzed": len(alerts),
        "incident_groups": len(grouped),
        "created": created,
        "updated": updated,
        "groups": [
            {
                "alert_type": alert_type,
                "count": len(records),
            }
            for alert_type, records in grouped.items()
        ],
    }


@router.get("/nginx/incidents")
def cms_nginx_security_incidents_report(
    status: str | None = None,
    alert_type: str | None = None,
    severity: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    query = db.query(NginxSecurityIncident)

    if status:
        query = query.filter(NginxSecurityIncident.status == status)

    if alert_type:
        query = query.filter(NginxSecurityIncident.alert_type == alert_type)

    if severity:
        query = query.filter(NginxSecurityIncident.severity == severity)

    records = query.order_by(
        NginxSecurityIncident.last_seen.desc()
    ).limit(limit).all()

    return {
        "module": "CMS Nginx Security Incidents",
        "status": "active",
        "count": len(records),
        "filters": {
            "status": status,
            "alert_type": alert_type,
            "severity": severity,
            "limit": limit,
        },
        "records": [
            serialize_nginx_security_incident(record)
            for record in records
        ],
    }


def get_nginx_incident_or_error(db: Session, incident_id: int):
    incident = db.query(NginxSecurityIncident).filter(
        NginxSecurityIncident.id == incident_id
    ).first()

    return incident


@router.post("/nginx/incidents/{incident_id}/review")
def cms_review_nginx_security_incident(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    incident = get_nginx_incident_or_error(db, incident_id)

    if not incident:
        return {
            "status": "error",
            "message": "Incident not found.",
            "incident_id": incident_id,
        }

    incident.status = "reviewed"
    incident.reviewed_at = datetime.utcnow()

    db.commit()
    db.refresh(incident)

    return {
        "module": "CMS Nginx Security Incident Workflow",
        "status": "reviewed",
        "record": serialize_nginx_security_incident(incident),
    }


@router.post("/nginx/incidents/{incident_id}/resolve")
def cms_resolve_nginx_security_incident(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    incident = get_nginx_incident_or_error(db, incident_id)

    if not incident:
        return {
            "status": "error",
            "message": "Incident not found.",
            "incident_id": incident_id,
        }

    incident.status = "resolved"

    if not incident.reviewed_at:
        incident.reviewed_at = datetime.utcnow()

    incident.resolved_at = datetime.utcnow()

    db.commit()
    db.refresh(incident)

    return {
        "module": "CMS Nginx Security Incident Workflow",
        "status": "resolved",
        "record": serialize_nginx_security_incident(incident),
    }


@router.post("/nginx/incidents/{incident_id}/reopen")
def cms_reopen_nginx_security_incident(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    incident = get_nginx_incident_or_error(db, incident_id)

    if not incident:
        return {
            "status": "error",
            "message": "Incident not found.",
            "incident_id": incident_id,
        }

    incident.status = "open"
    incident.reviewed_at = None
    incident.resolved_at = None

    db.commit()
    db.refresh(incident)

    return {
        "module": "CMS Nginx Security Incident Workflow",
        "status": "open",
        "record": serialize_nginx_security_incident(incident),
    }


@router.get("/nginx/alerts/sla")
def cms_nginx_alert_sla_report(
    limit: int = 1000,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    now = datetime.utcnow()

    alerts = db.query(NginxSecurityAlert).order_by(
        NginxSecurityAlert.created_at.desc()
    ).limit(limit).all()

    open_alerts = [
        alert
        for alert in alerts
        if alert.status == "open"
    ]

    reviewed_alerts = [
        alert
        for alert in alerts
        if alert.reviewed_at
    ]

    resolved_alerts = [
        alert
        for alert in alerts
        if alert.resolved_at
    ]

    open_age_hours = [
        hours_between(alert.created_at, now)
        for alert in open_alerts
    ]

    review_hours = [
        hours_between(alert.created_at, alert.reviewed_at)
        for alert in reviewed_alerts
    ]

    resolution_hours = [
        hours_between(alert.created_at, alert.resolved_at)
        for alert in resolved_alerts
    ]

    return {
        "module": "CMS Nginx Alert SLA",
        "status": "active",
        "filters": {
            "limit": limit,
        },
        "counts": {
            "total": len(alerts),
            "open": len(open_alerts),
            "reviewed": len(reviewed_alerts),
            "resolved": len(resolved_alerts),
        },
        "aging": {
            "open_over_24h": len([
                hours
                for hours in open_age_hours
                if hours is not None and hours >= 24
            ]),
            "open_over_72h": len([
                hours
                for hours in open_age_hours
                if hours is not None and hours >= 72
            ]),
            "open_over_7d": len([
                hours
                for hours in open_age_hours
                if hours is not None and hours >= 168
            ]),
            "oldest_open_hours": max(open_age_hours) if open_age_hours else None,
        },
        "sla": {
            "mean_time_to_review_hours": average_number(review_hours),
            "mean_time_to_resolve_hours": average_number(resolution_hours),
        },
        "critical": {
            "open": len([
                alert
                for alert in open_alerts
                if alert.severity == "critical"
            ]),
            "open_over_24h": len([
                alert
                for alert in open_alerts
                if alert.severity == "critical"
                and hours_between(alert.created_at, now) is not None
                and hours_between(alert.created_at, now) >= 24
            ]),
        },
        "oldest_open_alerts": [
            serialize_nginx_security_alert(alert)
            for alert in sorted(
                open_alerts,
                key=lambda item: item.created_at
            )[:10]
        ],
    }


@router.get("/nginx/scorecard")
def cms_nginx_security_scorecard(
    limit: int = 1000,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    events = db.query(NginxSecurityEvent).order_by(
        NginxSecurityEvent.created_at.desc()
    ).limit(limit).all()

    alerts = db.query(NginxSecurityAlert).all()
    activations = db.query(NginxSecurityActivation).all()
    suppressions = db.query(NginxAlertSuppression).all()
    incidents = db.query(NginxSecurityIncident).all()

    threat_summary = summarize_threat_records(events)

    open_alerts = [
        alert for alert in alerts
        if alert.status == "open"
    ]

    critical_open_alerts = [
        alert for alert in open_alerts
        if alert.severity == "critical"
    ]

    active_activations = [
        activation for activation in activations
        if activation.status == "active"
    ]

    active_suppressions = [
        suppression for suppression in suppressions
        if suppression.status == "active"
    ]

    open_incidents = [
        incident for incident in incidents
        if incident.status == "open"
    ]

    critical_open_incidents = [
        incident for incident in open_incidents
        if incident.severity == "critical"
    ]

    score = 100

    if threat_summary["threat_level"] == "critical":
        score -= 30
    elif threat_summary["threat_level"] == "high":
        score -= 20
    elif threat_summary["threat_level"] == "medium":
        score -= 10

    if len(critical_open_alerts) > 0:
        score -= 20

    if len(open_alerts) >= 25:
        score -= 15
    elif len(open_alerts) >= 10:
        score -= 10

    if not active_activations:
        score -= 15

    if threat_summary["severity_counts"].get("critical", 0) >= 100:
        score -= 10

    if len(critical_open_incidents) > 0:
        score -= 15

    if len(open_incidents) >= 10:
        score -= 10
    elif len(open_incidents) >= 5:
        score -= 5

    score = max(0, min(100, score))

    if score >= 85:
        grade = "A"
        posture = "strong"
    elif score >= 70:
        grade = "B"
        posture = "good"
    elif score >= 55:
        grade = "C"
        posture = "watch"
    elif score >= 40:
        grade = "D"
        posture = "weak"
    else:
        grade = "F"
        posture = "critical"

    recommendations = []

    if threat_summary["threat_level"] == "critical":
        recommendations.append("Review critical threat activity and continue blocking high-risk probes.")

    if critical_open_alerts:
        recommendations.append("Review or resolve open critical alerts.")

    if len(open_alerts) >= 25:
        recommendations.append("Triage open alert backlog.")

    if not active_activations:
        recommendations.append("Activate generated Nginx security include on at least one protected domain.")

    if active_activations:
        recommendations.append("Continue monitoring activated security includes before expanding to additional domains.")

    if active_suppressions:
        recommendations.append("Monitor active suppression rules to ensure known noise is reduced without hiding real incidents.")

    return {
        "module": "CMS Nginx Security Scorecard",
        "status": "active",
        "filters": {
            "limit": limit,
        },
        "scorecard": {
            "score": score,
            "grade": grade,
            "posture": posture,
        },
        "threat": {
            "score": threat_summary["threat_score"],
            "level": threat_summary["threat_level"],
            "severity_counts": threat_summary["severity_counts"],
        },
        "alerts": {
            "total": len(alerts),
            "open": len(open_alerts),
            "critical_open": len(critical_open_alerts),
            "resolved": len([alert for alert in alerts if alert.status == "resolved"]),
            "reviewed": len([alert for alert in alerts if alert.status == "reviewed"]),
        },
        "activations": {
            "total": len(activations),
            "active": len(active_activations),
            "domains": [
                activation.domain
                for activation in active_activations
            ],
        },
        "suppressions": {
            "total": len(suppressions),
            "active": len(active_suppressions),
            "rules": [
                {
                    "id": suppression.id,
                    "alert_type": suppression.alert_type,
                    "request_path": suppression.request_path,
                    "remote_ip": suppression.remote_ip,
                }
                for suppression in active_suppressions
            ],
        },
        "incidents": {
            "total": len(incidents),
            "open": len(open_incidents),
            "critical_open": len(critical_open_incidents),
            "resolved": len([
                incident for incident in incidents
                if incident.status == "resolved"
            ]),
            "reviewed": len([
                incident for incident in incidents
                if incident.status == "reviewed"
            ]),
        },
        "recommendations": recommendations,
    }


def serialize_nginx_alert_suppression(record: NginxAlertSuppression):
    return {
        "id": record.id,
        "alert_type": record.alert_type,
        "request_path": record.request_path,
        "remote_ip": record.remote_ip,
        "status": record.status,
        "notes": record.notes,
        "created_at": record.created_at,
    }


@router.get("/nginx/suppressions")
def cms_nginx_alert_suppressions_report(
    alert_type: str | None = None,
    request_path: str | None = None,
    remote_ip: str | None = None,
    status: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    query = db.query(NginxAlertSuppression)

    if alert_type:
        query = query.filter(NginxAlertSuppression.alert_type == alert_type)

    if request_path:
        query = query.filter(NginxAlertSuppression.request_path == request_path)

    if remote_ip:
        query = query.filter(NginxAlertSuppression.remote_ip == remote_ip)

    if status:
        query = query.filter(NginxAlertSuppression.status == status)

    records = query.order_by(
        NginxAlertSuppression.created_at.desc()
    ).limit(limit).all()

    return {
        "module": "CMS Nginx Alert Suppressions",
        "status": "active",
        "count": len(records),
        "filters": {
            "alert_type": alert_type,
            "request_path": request_path,
            "remote_ip": remote_ip,
            "status": status,
            "limit": limit,
        },
        "records": [
            serialize_nginx_alert_suppression(record)
            for record in records
        ]
    }


@router.post("/nginx/suppressions/record")
def cms_record_nginx_alert_suppression(
    alert_type: str | None = None,
    request_path: str | None = None,
    remote_ip: str | None = None,
    notes: str | None = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    existing = db.query(NginxAlertSuppression).filter(
        NginxAlertSuppression.alert_type == alert_type,
        NginxAlertSuppression.request_path == request_path,
        NginxAlertSuppression.remote_ip == remote_ip,
        NginxAlertSuppression.status == "active",
    ).first()

    if existing:
        return {
            "module": "CMS Nginx Alert Suppression Recorder",
            "status": "exists",
            "record": serialize_nginx_alert_suppression(existing),
        }

    record = NginxAlertSuppression(
        alert_type=alert_type,
        request_path=request_path,
        remote_ip=remote_ip,
        status="active",
        notes=notes,
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    return {
        "module": "CMS Nginx Alert Suppression Recorder",
        "status": "recorded",
        "record": serialize_nginx_alert_suppression(record),
    }


@router.get("/nginx/dashboard")
def cms_nginx_security_dashboard(
    limit: int = 1000,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    events = db.query(NginxSecurityEvent).order_by(
        NginxSecurityEvent.created_at.desc()
    ).limit(limit).all()

    threat_summary = summarize_threat_records(events)

    total_events = db.query(NginxSecurityEvent).count()

    total_alerts = db.query(NginxSecurityAlert).count()

    open_alerts = db.query(NginxSecurityAlert).filter(
        NginxSecurityAlert.status == "open"
    ).count()

    reviewed_alerts = db.query(NginxSecurityAlert).filter(
        NginxSecurityAlert.status == "reviewed"
    ).count()

    resolved_alerts = db.query(NginxSecurityAlert).filter(
        NginxSecurityAlert.status == "resolved"
    ).count()

    latest_event = db.query(NginxSecurityEvent).order_by(
        NginxSecurityEvent.created_at.desc()
    ).first()

    latest_alert = db.query(NginxSecurityAlert).order_by(
        NginxSecurityAlert.created_at.desc()
    ).first()

    total_suppressions = db.query(NginxAlertSuppression).count()

    active_suppressions = db.query(NginxAlertSuppression).filter(
        NginxAlertSuppression.status == "active"
    ).count()

    total_incidents = db.query(NginxSecurityIncident).count()

    open_incidents = db.query(NginxSecurityIncident).filter(
        NginxSecurityIncident.status == "open"
    ).count()

    reviewed_incidents = db.query(NginxSecurityIncident).filter(
        NginxSecurityIncident.status == "reviewed"
    ).count()

    resolved_incidents = db.query(NginxSecurityIncident).filter(
        NginxSecurityIncident.status == "resolved"
    ).count()

    critical_open_incidents = db.query(NginxSecurityIncident).filter(
        NginxSecurityIncident.status == "open",
        NginxSecurityIncident.severity == "critical",
    ).count()

    return {
        "module": "CMS Nginx Security Dashboard",
        "status": "active",
        "events": {
            "total": total_events
        },
        "alerts": {
            "total": total_alerts,
            "open": open_alerts,
            "reviewed": reviewed_alerts,
            "resolved": resolved_alerts,
        },
        "suppressions": {
            "total": total_suppressions,
            "active": active_suppressions,
        },
        "incidents": {
            "total": total_incidents,
            "open": open_incidents,
            "reviewed": reviewed_incidents,
            "resolved": resolved_incidents,
            "critical_open": critical_open_incidents,
        },
        "threat": {
            "score": threat_summary["threat_score"],
            "level": threat_summary["threat_level"],
            "severity_counts": threat_summary["severity_counts"],
        },
        "top_attackers": threat_summary["top_attackers"][:10],
        "top_vectors": threat_summary["top_vectors"][:10],
        "latest_event": (
            latest_event.created_at
            if latest_event else None
        ),
        "latest_alert": (
            latest_alert.created_at
            if latest_alert else None
        ),
    }


def nginx_alert_status_report(db: Session, status: str, limit: int = 100):
    records = db.query(NginxSecurityAlert).filter(
        NginxSecurityAlert.status == status
    ).order_by(
        NginxSecurityAlert.created_at.desc()
    ).limit(limit).all()

    return {
        "module": f"CMS Nginx Security Alerts - {status.title()}",
        "status": "active",
        "count": len(records),
        "filters": {
            "status": status,
            "limit": limit,
        },
        "records": [
            serialize_nginx_security_alert(alert)
            for alert in records
        ]
    }


def get_nginx_alert_or_error(db: Session, alert_id: int):
    alert = db.query(NginxSecurityAlert).filter(
        NginxSecurityAlert.id == alert_id
    ).first()

    if not alert:
        return None

    return alert


@router.get("/nginx/alerts/open")
def cms_nginx_open_alerts_report(
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    return nginx_alert_status_report(db, "open", limit)


@router.get("/nginx/alerts/reviewed")
def cms_nginx_reviewed_alerts_report(
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    return nginx_alert_status_report(db, "reviewed", limit)


@router.get("/nginx/alerts/resolved")
def cms_nginx_resolved_alerts_report(
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    return nginx_alert_status_report(db, "resolved", limit)


def batch_update_nginx_alerts(
    db: Session,
    target_status: str,
    severity: str | None = None,
    alert_type: str | None = None,
    status: str | None = "open",
    limit: int = 1000,
):
    query = db.query(NginxSecurityAlert)

    if severity:
        query = query.filter(NginxSecurityAlert.severity == severity)

    if alert_type:
        query = query.filter(NginxSecurityAlert.alert_type == alert_type)

    if status:
        query = query.filter(NginxSecurityAlert.status == status)

    records = query.order_by(
        NginxSecurityAlert.created_at.desc()
    ).limit(limit).all()

    now = datetime.utcnow()

    for alert in records:
        alert.status = target_status

        if target_status == "reviewed":
            alert.reviewed_at = now
            alert.resolved_at = None

        if target_status == "resolved":
            if not alert.reviewed_at:
                alert.reviewed_at = now
            alert.resolved_at = now

        if target_status == "open":
            alert.reviewed_at = None
            alert.resolved_at = None

    db.commit()

    return {
        "module": "CMS Nginx Alert Batch Workflow",
        "status": "complete",
        "action": target_status,
        "updated": len(records),
        "filters": {
            "severity": severity,
            "alert_type": alert_type,
            "status": status,
            "limit": limit,
        }
    }


@router.post("/nginx/alerts/batch/review")
def cms_batch_review_nginx_alerts(
    severity: str | None = None,
    alert_type: str | None = None,
    status: str | None = "open",
    limit: int = 1000,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    return batch_update_nginx_alerts(
        db=db,
        target_status="reviewed",
        severity=severity,
        alert_type=alert_type,
        status=status,
        limit=limit,
    )


@router.post("/nginx/alerts/batch/resolve")
def cms_batch_resolve_nginx_alerts(
    severity: str | None = None,
    alert_type: str | None = None,
    status: str | None = "open",
    limit: int = 1000,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    return batch_update_nginx_alerts(
        db=db,
        target_status="resolved",
        severity=severity,
        alert_type=alert_type,
        status=status,
        limit=limit,
    )


@router.post("/nginx/alerts/batch/reopen")
def cms_batch_reopen_nginx_alerts(
    severity: str | None = None,
    alert_type: str | None = None,
    status: str | None = "resolved",
    limit: int = 1000,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    return batch_update_nginx_alerts(
        db=db,
        target_status="open",
        severity=severity,
        alert_type=alert_type,
        status=status,
        limit=limit,
    )


@router.post("/nginx/alerts/{alert_id}/review")
def cms_review_nginx_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    alert = get_nginx_alert_or_error(db, alert_id)

    if not alert:
        return {
            "status": "error",
            "message": "Alert not found.",
            "alert_id": alert_id,
        }

    alert.status = "reviewed"
    alert.reviewed_at = datetime.utcnow()

    db.commit()
    db.refresh(alert)

    return {
        "module": "CMS Nginx Security Alert Workflow",
        "status": "reviewed",
        "record": serialize_nginx_security_alert(alert),
    }


@router.post("/nginx/alerts/{alert_id}/resolve")
def cms_resolve_nginx_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    alert = get_nginx_alert_or_error(db, alert_id)

    if not alert:
        return {
            "status": "error",
            "message": "Alert not found.",
            "alert_id": alert_id,
        }

    alert.status = "resolved"

    if not alert.reviewed_at:
        alert.reviewed_at = datetime.utcnow()

    alert.resolved_at = datetime.utcnow()

    db.commit()
    db.refresh(alert)

    return {
        "module": "CMS Nginx Security Alert Workflow",
        "status": "resolved",
        "record": serialize_nginx_security_alert(alert),
    }


@router.post("/nginx/alerts/{alert_id}/reopen")
def cms_reopen_nginx_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    alert = get_nginx_alert_or_error(db, alert_id)

    if not alert:
        return {
            "status": "error",
            "message": "Alert not found.",
            "alert_id": alert_id,
        }

    alert.status = "open"
    alert.reviewed_at = None
    alert.resolved_at = None

    db.commit()
    db.refresh(alert)

    return {
        "module": "CMS Nginx Security Alert Workflow",
        "status": "open",
        "record": serialize_nginx_security_alert(alert),
    }


@router.get("/security/events")
def cms_security_events_report(
    event_type: str | None = None,
    status: str | None = None,
    email: str | None = None,
    ip_address: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    query = db.query(AccountSecurityEvent)

    if event_type:
        query = query.filter(AccountSecurityEvent.event_type == event_type)

    if status:
        query = query.filter(AccountSecurityEvent.status == status)

    if email:
        query = query.filter(AccountSecurityEvent.email == email)

    if ip_address:
        query = query.filter(AccountSecurityEvent.ip_address == ip_address)

    records = query.order_by(AccountSecurityEvent.created_at.desc()).limit(limit).all()

    return {
        "module": "CMS Security Events",
        "status": "active",
        "count": len(records),
        "filters": {
            "event_type": event_type,
            "status": status,
            "email": email,
            "ip_address": ip_address,
            "limit": limit,
        },
        "records": [
            serialize_account_security_event(event)
            for event in records
        ]
    }


@router.get("/security/summary")
def cms_security_summary_report(
    limit: int = 1000,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    records = db.query(AccountSecurityEvent).order_by(
        AccountSecurityEvent.created_at.desc()
    ).limit(limit).all()

    return {
        "module": "CMS Security Summary",
        "status": "active",
        "count": len(records),
        "filters": {
            "limit": limit,
        },
        "summary": {
            "by_event_type": metric_count_by_field(records, "event_type"),
            "by_status": metric_count_by_field(records, "status"),
            "by_ip_address": metric_count_by_field(records, "ip_address"),
            "by_email": metric_count_by_field(records, "email"),
        }
    }


@router.get("/security/intelligence")
def cms_security_intelligence_report(
    limit: int = 1000,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    records = db.query(AccountSecurityEvent).order_by(
        AccountSecurityEvent.created_at.desc()
    ).limit(limit).all()

    failed_login_records = [
        record
        for record in records
        if record.event_type in ["login_failed", "blocked_login_attempt", "login_lockout"]
    ]

    return {
        "module": "CMS Security Intelligence",
        "status": "active",
        "count": len(records),
        "filters": {
            "limit": limit,
        },
        "records": {
            "top_event_types": ranked_metric_counts(records, "event_type", 25),
            "top_statuses": ranked_metric_counts(records, "status", 25),
            "top_ip_addresses": ranked_metric_counts(records, "ip_address", 25),
            "top_emails": ranked_metric_counts(records, "email", 25),
            "failed_login_ip_addresses": ranked_metric_counts(failed_login_records, "ip_address", 25),
            "failed_login_emails": ranked_metric_counts(failed_login_records, "email", 25),
        }
    }


@router.get("/metrics/sessions")
def cms_metrics_sessions_report(
    project: str | None = None,
    source: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer", "reviewer"))
):
    query = db.query(MetricEvent)

    if project:
        query = query.filter(MetricEvent.project == project)

    if source:
        query = query.filter(MetricEvent.source == source)

    records = query.order_by(MetricEvent.created_at.desc()).limit(limit).all()

    sessions = group_metric_events_by_session(records)

    session_records = [
        serialize_session_summary(session_id, events)
        for session_id, events in sessions.items()
    ]

    session_records.sort(
        key=lambda item: item["ended_at"] or item["started_at"],
        reverse=True
    )

    return {
        "module": "CMS Metrics Sessions",
        "status": "active",
        "count": len(session_records),
        "filters": {
            "project": project,
            "source": source,
            "limit": limit,
        },
        "records": session_records
    }


@router.get("/intelligence/sessions")
def cms_metrics_session_intelligence(
    project: str | None = None,
    source: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer", "reviewer"))
):
    query = db.query(MetricEvent)

    if project:
        query = query.filter(MetricEvent.project == project)

    if source:
        query = query.filter(MetricEvent.source == source)

    records = query.order_by(MetricEvent.created_at.desc()).limit(limit).all()

    sessions = group_metric_events_by_session(records)

    session_records = [
        serialize_session_summary(session_id, events)
        for session_id, events in sessions.items()
    ]

    session_records.sort(
        key=lambda item: (
            item["events"],
            item["duration_seconds"],
            item["pages_visited"],
        ),
        reverse=True
    )

    return {
        "module": "CMS Metrics Intelligence Sessions",
        "status": "active",
        "count": len(session_records),
        "filters": {
            "project": project,
            "source": source,
            "limit": limit,
        },
        "records": [
            {
                "rank": index + 1,
                **record
            }
            for index, record in enumerate(session_records)
        ]
    }


@router.get("/attribution/campaigns")
def cms_attribution_campaign_funnels(
    project: str | None = None,
    limit: int = 25,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer", "reviewer"))
):
    metric_events = metric_records_for_project(db, project)

    clicks_query = db.query(AffiliateClick)
    conversions_query = db.query(AffiliateConversion)
    commissions_query = db.query(AffiliateCommission)

    if project:
        commissions_query = commissions_query.filter(AffiliateCommission.project == project)

    clicks = clicks_query.all()
    conversions = conversions_query.all()
    commissions = commissions_query.all()

    campaign_ids = sorted(set([
        record.campaign_id
        for record in metric_events
        if record.campaign_id
    ] + [
        click.campaign_id
        for click in clicks
        if click.campaign_id
    ]))

    records = []

    for campaign_id in campaign_ids:
        campaign_views = [
            event
            for event in metric_events
            if event.campaign_id == campaign_id and event.event_type in ["campaign_view", "page_view"]
        ]

        campaign_clicks = [
            click
            for click in clicks
            if click.campaign_id == campaign_id
        ]

        campaign_referral_codes = list(set([
            click.referral_code
            for click in campaign_clicks
            if click.referral_code
        ] + [
            event.referral_code
            for event in campaign_views
            if event.referral_code
        ]))

        campaign_conversions = [
            conversion
            for conversion in conversions
            if conversion.referral_code in campaign_referral_codes
        ]

        campaign_commissions = [
            commission
            for commission in commissions
            if commission.referral_code in campaign_referral_codes
        ]

        records.append({
            "campaign_id": campaign_id,
            "summary": build_funnel_summary(
                views_count=len(campaign_views),
                clicks_count=len(campaign_clicks),
                enrollments_count=0,
                conversions_count=len(campaign_conversions),
                commissions_count=len(campaign_commissions),
                commission_cents=commission_total_cents(campaign_commissions),
            )
        })

    records.sort(
        key=lambda record: (
            record["summary"]["conversions"],
            record["summary"]["commission_cents"],
            record["summary"]["clicks"],
            record["summary"]["views"],
        ),
        reverse=True
    )

    return {
        "module": "CMS Attribution Intelligence Campaigns",
        "status": "active",
        "count": len(records[:limit]),
        "filters": {
            "project": project,
            "limit": limit,
        },
        "records": [
            {
                "rank": index + 1,
                **record
            }
            for index, record in enumerate(records[:limit])
        ]
    }


@router.get("/attribution/affiliates")
def cms_attribution_affiliate_funnels(
    project: str | None = None,
    limit: int = 25,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer", "reviewer"))
):
    metric_events = metric_records_for_project(db, project)

    clicks = db.query(AffiliateClick).all()
    conversions = db.query(AffiliateConversion).all()

    commissions_query = db.query(AffiliateCommission)

    if project:
        commissions_query = commissions_query.filter(AffiliateCommission.project == project)

    commissions = commissions_query.all()

    referral_codes = sorted(set([
        event.referral_code
        for event in metric_events
        if event.referral_code
    ] + [
        click.referral_code
        for click in clicks
        if click.referral_code
    ] + [
        conversion.referral_code
        for conversion in conversions
        if conversion.referral_code
    ] + [
        commission.referral_code
        for commission in commissions
        if commission.referral_code
    ]))

    records = []

    for referral_code in referral_codes:
        affiliate_views = [
            event
            for event in metric_events
            if event.referral_code == referral_code
        ]

        affiliate_clicks = [
            click
            for click in clicks
            if click.referral_code == referral_code
        ]

        affiliate_conversions = [
            conversion
            for conversion in conversions
            if conversion.referral_code == referral_code
        ]

        affiliate_commissions = [
            commission
            for commission in commissions
            if commission.referral_code == referral_code
        ]

        records.append({
            "referral_code": referral_code,
            "summary": build_funnel_summary(
                views_count=len(affiliate_views),
                clicks_count=len(affiliate_clicks),
                enrollments_count=0,
                conversions_count=len(affiliate_conversions),
                commissions_count=len(affiliate_commissions),
                commission_cents=commission_total_cents(affiliate_commissions),
            )
        })

    records.sort(
        key=lambda record: (
            record["summary"]["conversions"],
            record["summary"]["commission_cents"],
            record["summary"]["clicks"],
            record["summary"]["views"],
        ),
        reverse=True
    )

    return {
        "module": "CMS Attribution Intelligence Affiliates",
        "status": "active",
        "count": len(records[:limit]),
        "filters": {
            "project": project,
            "limit": limit,
        },
        "records": [
            {
                "rank": index + 1,
                **record
            }
            for index, record in enumerate(records[:limit])
        ]
    }


@router.get("/intelligence/campaigns")
def cms_metrics_campaign_intelligence(
    project: str | None = None,
    limit: int = 25,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer", "reviewer"))
):
    records = metric_records_for_project(db, project)

    campaign_records = [
        record
        for record in records
        if record.campaign_id
    ]

    campaigns = ranked_metric_counts(campaign_records, "campaign_id", limit)

    return {
        "module": "CMS Metrics Intelligence Campaigns",
        "status": "active",
        "count": len(campaigns),
        "filters": {
            "project": project,
            "limit": limit,
        },
        "records": campaigns
    }


@router.get("/intelligence/organizations")
def cms_metrics_organization_intelligence(
    project: str | None = None,
    limit: int = 25,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer", "reviewer"))
):
    records = metric_records_for_project(db, project)

    organization_records = [
        record
        for record in records
        if record.organization_id
    ]

    organizations = ranked_metric_counts(organization_records, "organization_id", limit)

    return {
        "module": "CMS Metrics Intelligence Organizations",
        "status": "active",
        "count": len(organizations),
        "filters": {
            "project": project,
            "limit": limit,
        },
        "records": organizations
    }


@router.get("/intelligence/affiliates")
def cms_metrics_affiliate_intelligence(
    project: str | None = None,
    limit: int = 25,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer", "reviewer"))
):
    records = metric_records_for_project(db, project)

    affiliate_records = [
        record
        for record in records
        if record.referral_code or record.affiliate_id
    ]

    by_referral_code = ranked_metric_counts(affiliate_records, "referral_code", limit)
    by_affiliate_id = ranked_metric_counts(affiliate_records, "affiliate_id", limit)

    return {
        "module": "CMS Metrics Intelligence Affiliates",
        "status": "active",
        "filters": {
            "project": project,
            "limit": limit,
        },
        "records": {
            "by_referral_code": by_referral_code,
            "by_affiliate_id": by_affiliate_id,
        }
    }


@router.get("/intelligence/pages")
def cms_metrics_page_intelligence(
    project: str | None = None,
    limit: int = 25,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer", "reviewer"))
):
    records = metric_records_for_project(db, project)

    page_records = [
        record
        for record in records
        if record.event_type == "page_view"
    ]

    pages = ranked_metric_counts(page_records, "page_url", limit)
    targets = ranked_metric_counts(page_records, "target_id", limit)

    return {
        "module": "CMS Metrics Intelligence Pages",
        "status": "active",
        "filters": {
            "project": project,
            "limit": limit,
        },
        "records": {
            "by_page_url": pages,
            "by_target_id": targets,
        }
    }


@router.get("/metrics")
def cms_metrics_report(
    project: str | None = None,
    event_type: str | None = None,
    source: str | None = None,
    campaign_id: str | None = None,
    organization_id: int | None = None,
    referral_code: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer", "reviewer"))
):
    query = db.query(MetricEvent)

    if project:
        query = query.filter(MetricEvent.project == project)

    if event_type:
        query = query.filter(MetricEvent.event_type == event_type)

    if source:
        query = query.filter(MetricEvent.source == source)

    if campaign_id:
        query = query.filter(MetricEvent.campaign_id == campaign_id)

    if organization_id:
        query = query.filter(MetricEvent.organization_id == organization_id)

    if referral_code:
        query = query.filter(MetricEvent.referral_code == referral_code)

    records = query.order_by(MetricEvent.created_at.desc()).limit(limit).all()

    return {
        "module": "CMS Metrics Report",
        "status": "active",
        "count": len(records),
        "filters": {
            "project": project,
            "event_type": event_type,
            "source": source,
            "campaign_id": campaign_id,
            "organization_id": organization_id,
            "referral_code": referral_code,
            "limit": limit,
        },
        "records": [
            serialize_metric_event(event)
            for event in records
        ]
    }


@router.get("/metrics/summary")
def cms_metrics_summary_report(
    project: str | None = None,
    source: str | None = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer", "reviewer"))
):
    query = db.query(MetricEvent)

    if project:
        query = query.filter(MetricEvent.project == project)

    if source:
        query = query.filter(MetricEvent.source == source)

    records = query.all()

    return {
        "module": "CMS Metrics Summary",
        "status": "active",
        "count": len(records),
        "filters": {
            "project": project,
            "source": source,
        },
        "summary": {
            "by_event_type": metric_count_by_field(records, "event_type"),
            "by_project": metric_count_by_field(records, "project"),
            "by_source": metric_count_by_field(records, "source"),
            "by_target_type": metric_count_by_field(records, "target_type"),
            "by_campaign": metric_count_by_field(records, "campaign_id"),
            "by_organization": metric_count_by_field(records, "organization_id"),
            "by_referral_code": metric_count_by_field(records, "referral_code"),
        }
    }


@router.get("/metrics/pages")
def cms_metrics_pages_report(
    project: str | None = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer", "reviewer"))
):
    query = db.query(MetricEvent).filter(
        MetricEvent.event_type == "page_view"
    )

    if project:
        query = query.filter(MetricEvent.project == project)

    records = query.all()

    return {
        "module": "CMS Metrics Pages",
        "status": "active",
        "count": len(records),
        "filters": {
            "project": project,
            "event_type": "page_view",
        },
        "summary": {
            "by_page_url": metric_count_by_field(records, "page_url"),
            "by_target_id": metric_count_by_field(records, "target_id"),
            "by_source": metric_count_by_field(records, "source"),
            "by_referral_code": metric_count_by_field(records, "referral_code"),
        }
    }


@router.get("/metrics/events")
def cms_metrics_events_report(
    project: str | None = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer", "reviewer"))
):
    query = db.query(MetricEvent)

    if project:
        query = query.filter(MetricEvent.project == project)

    records = query.all()

    return {
        "module": "CMS Metrics Events",
        "status": "active",
        "count": len(records),
        "filters": {
            "project": project,
        },
        "summary": {
            "by_event_type": metric_count_by_field(records, "event_type"),
            "by_target_type": metric_count_by_field(records, "target_type"),
            "by_campaign": metric_count_by_field(records, "campaign_id"),
            "by_organization": metric_count_by_field(records, "organization_id"),
        }
    }


@router.get("/summary")
def cms_summary_report(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer", "reviewer"))
):
    memorials = db.query(Memorial).all()
    media_assets = db.query(MediaAsset).all()
    contributions = db.query(Contribution).all()
    affiliate_clicks = db.query(AffiliateClick).all()
    affiliate_conversions = db.query(AffiliateConversion).all()

    def count_by_status(records):
        counts = {}
        for record in records:
            status = getattr(record, "status", "unknown") or "unknown"
            counts[status] = counts.get(status, 0) + 1
        return counts

    def count_by_field(records, field):
        counts = {}
        for record in records:
            value = getattr(record, field, "unknown") or "unknown"
            counts[value] = counts.get(value, 0) + 1
        return counts

    return {
        "module": "CMS Reports",
        "status": "active",
        "summary": {
            "memorials": {
                "total": len(memorials),
                "by_status": count_by_status(memorials),
                "by_environment_theme": count_by_field(memorials, "environment_theme")
            },
            "media_assets": {
                "total": len(media_assets),
                "by_status": count_by_status(media_assets),
                "by_media_type": count_by_field(media_assets, "media_type")
            },
            "contributions": {
                "total": len(contributions),
                "by_status": count_by_status(contributions),
                "by_contribution_type": count_by_field(contributions, "contribution_type")
            },
            "affiliate_program": {
                "total_clicks": len(affiliate_clicks),
                "total_conversions": len(affiliate_conversions),
                "pending_conversions": len([
                    conversion for conversion in affiliate_conversions
                    if conversion.status == "pending"
                ]),
                "approved_conversions": len([
                    conversion for conversion in affiliate_conversions
                    if conversion.status == "approved"
                ]),
                "by_conversion_type": count_by_field(affiliate_conversions, "conversion_type")
            }
        }
    }
