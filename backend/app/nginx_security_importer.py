import re
from datetime import datetime

from backend.app.database import SessionLocal
from backend.app.models import NginxSecurityEvent


ACCESS_LOG_PATTERN = re.compile(
    r'(?P<remote_ip>\S+) \S+ \S+ '
    r'\[(?P<timestamp>[^\]]+)\] '
    r'"(?P<method>\S+) (?P<path>\S+) [^"]+" '
    r'(?P<status>\d{3}) \S+ '
    r'"(?P<referer>[^"]*)" '
    r'"(?P<user_agent>[^"]*)"'
)

ERROR_LOG_PATTERN = re.compile(
    r'(?P<timestamp>\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}).*?'
    r'client: (?P<remote_ip>[^,]+).*?'
    r'request: "(?P<method>\S+) (?P<path>\S+) [^"]+"'
)


def parse_access_line(line: str):
    match = ACCESS_LOG_PATTERN.search(line)

    if not match:
        return None

    data = match.groupdict()

    try:
        created_at = datetime.strptime(
            data["timestamp"].split()[0],
            "%d/%b/%Y:%H:%M:%S"
        )
    except Exception:
        created_at = datetime.utcnow()

    return {
        "remote_ip": data.get("remote_ip"),
        "request_method": data.get("method"),
        "request_path": data.get("path"),
        "status_code": int(data.get("status")),
        "user_agent": data.get("user_agent"),
        "referer": data.get("referer"),
        "country": None,
        "source": "nginx_access",
        "created_at": created_at,
    }


def parse_error_line(line: str):
    match = ERROR_LOG_PATTERN.search(line)

    if not match:
        return None

    data = match.groupdict()

    try:
        created_at = datetime.strptime(
            data["timestamp"],
            "%Y/%m/%d %H:%M:%S"
        )
    except Exception:
        created_at = datetime.utcnow()

    return {
        "remote_ip": data.get("remote_ip"),
        "request_method": data.get("method"),
        "request_path": data.get("path"),
        "status_code": 403 if "access forbidden" in line else None,
        "user_agent": None,
        "referer": None,
        "country": None,
        "source": "nginx_error",
        "created_at": created_at,
    }


def existing_event_keys(db):
    rows = db.query(NginxSecurityEvent).all()

    return set(
        (
            row.remote_ip,
            row.request_method,
            row.request_path,
            row.status_code,
            row.source,
            row.created_at,
        )
        for row in rows
    )


def import_log_file(path: str, parser, limit: int | None = None):
    db = SessionLocal()

    imported = 0
    skipped = 0
    failed = 0

    try:
        known = existing_event_keys(db)

        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            lines = handle.readlines()

        if limit:
            lines = lines[-limit:]

        for line in lines:
            parsed = parser(line)

            if not parsed:
                failed += 1
                continue

            key = (
                parsed["remote_ip"],
                parsed["request_method"],
                parsed["request_path"],
                parsed["status_code"],
                parsed["source"],
                parsed["created_at"],
            )

            if key in known:
                skipped += 1
                continue

            db.add(NginxSecurityEvent(**parsed))
            known.add(key)
            imported += 1

        db.commit()

        return {
            "path": path,
            "imported": imported,
            "skipped": skipped,
            "failed": failed,
        }

    finally:
        db.close()


def import_nginx_security_logs(limit: int = 1000):
    results = []

    results.append(
        import_log_file(
            "/var/log/nginx/access.log",
            parse_access_line,
            limit
        )
    )

    results.append(
        import_log_file(
            "/var/log/nginx/error.log",
            parse_error_line,
            limit
        )
    )

    return {
        "module": "Nginx Security Importer",
        "status": "complete",
        "limit": limit,
        "results": results,
    }


if __name__ == "__main__":
    print(import_nginx_security_logs())
