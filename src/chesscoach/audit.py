"""Structured audit findings shared by stress tests and release reports."""

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class AuditFinding:
    """One reproducible behavior observed during an application audit."""

    finding_id: str
    severity: str
    area: str
    reproduction: str
    expected: str
    actual: str
    regression: str
    status: str = "open"


@dataclass(frozen=True)
class AuditReport:
    """Machine-readable result for one deterministic audit run."""

    started_at: str
    completed_at: str
    passed_sequences: int
    failed_sequences: int
    findings: tuple[AuditFinding, ...] = ()

    @classmethod
    def start(cls) -> "AuditReport":
        now = datetime.now(UTC).isoformat()
        return cls(now, now, 0, 0)

    def finish(
        self,
        *,
        passed_sequences: int,
        failed_sequences: int,
        findings: tuple[AuditFinding, ...] = (),
    ) -> "AuditReport":
        return AuditReport(
            self.started_at,
            datetime.now(UTC).isoformat(),
            passed_sequences,
            failed_sequences,
            findings,
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)
