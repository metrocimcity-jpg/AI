"""CSV and single-page PDF exports. No network calls."""

from __future__ import annotations

import csv
import io
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Attendance, Event, PPESample


def _between(column, start: datetime | None, end: datetime | None):  # type: ignore[no-untyped-def]
    clauses = []
    if start is not None:
        clauses.append(column >= start)
    if end is not None:
        clauses.append(column <= end)
    return clauses


def export_report(
    session: Session,
    kind: str,
    fmt: str,
    start: datetime | None,
    end: datetime | None,
) -> tuple[bytes, str, str]:
    if kind == "events":
        rows = session.scalars(
            select(Event).where(*_between(Event.ts, start, end)).order_by(Event.ts.desc()).limit(2000)
        ).all()
        header = ["id", "ts", "camera_id", "event_type", "severity", "status", "track_id"]
        data = [
            [row.id, row.ts.isoformat(), row.camera_id, row.event_type, row.severity, row.status, row.track_id]
            for row in rows
        ]
    elif kind == "attendance":
        rows = session.scalars(select(Attendance).order_by(Attendance.date.desc()).limit(2000)).all()
        header = ["worker_id", "camera_id", "date", "first_seen", "last_seen"]
        data = [
            [row.worker_id, row.camera_id, row.date, row.first_seen.isoformat(), row.last_seen.isoformat()]
            for row in rows
        ]
    else:
        rows = session.scalars(
            select(PPESample).where(*_between(PPESample.ts, start, end)).order_by(PPESample.ts.desc()).limit(2000)
        ).all()
        header = ["ts", "camera_id", "track_id", "helmet", "vest", "gloves", "boots"]
        data = [
            [row.ts.isoformat(), row.camera_id, row.track_id, row.helmet, row.vest, row.gloves, row.boots]
            for row in rows
        ]
    if fmt == "pdf":
        lines = [", ".join(header)] + [", ".join(str(cell) for cell in row) for row in data[:40]]
        return simple_pdf(lines or ["No rows"]), "application/pdf", f"{kind}.pdf"
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    writer.writerows(data)
    return buf.getvalue().encode("utf-8"), "text/csv", f"{kind}.csv"


def simple_pdf(lines: list[str]) -> bytes:
    commands = ["BT", "/F1 10 Tf", "40 800 Td", "14 TL"]
    for index, line in enumerate(lines[:45]):
        safe = (
            line.replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
            .encode("latin-1", errors="replace")
            .decode("latin-1")
        )
        if index == 0:
            commands.append(f"({safe}) Tj")
        else:
            commands.append(f"T* ({safe}) Tj")
    commands.append("ET")
    stream = "\n".join(commands).encode("latin-1", errors="replace")
    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Count 1 /Kids [3 0 R] >> endobj\n",
        (
            b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n"
        ),
        b"4 0 obj << /Length " + str(len(stream)).encode() + b" >> stream\n" + stream + b"\nendstream endobj\n",
        b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(out))
        out.extend(obj)
    xref = len(out)
    out.extend(f"xref\n0 {len(offsets)}\n".encode())
    out.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        out.extend(f"{offset:010d} 00000 n \n".encode())
    out.extend(
        f"trailer << /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    )
    return bytes(out)
