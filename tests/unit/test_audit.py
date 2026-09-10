import json

from chesscoach.audit import AuditFinding, AuditReport


def test_audit_report_serializes_findings_and_counts():
    report = AuditReport.start().finish(
        passed_sequences=4,
        failed_sequences=1,
        findings=(
            AuditFinding(
                "AUD-TEST",
                "medium",
                "navigation",
                "Open the page",
                "Page opens",
                "Page opened",
                "Keep a route regression test",
            ),
        ),
    )
    data = json.loads(report.to_json())
    assert data["passed_sequences"] == 4
    assert data["failed_sequences"] == 1
    assert data["findings"][0]["finding_id"] == "AUD-TEST"
