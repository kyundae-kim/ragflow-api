from __future__ import annotations

from ragflow.health import run_health_checks


def test_health_checks_report_each_dependency_and_hide_exception_details() -> None:
    calls: list[str] = []

    def healthy_check() -> None:
        calls.append("healthy")

    def failing_check() -> None:
        calls.append("failing")
        raise RuntimeError("postgresql://user:secret@database")

    result = run_health_checks(
        (
            ("healthy", healthy_check),
            ("failing", failing_check),
        )
    )

    assert calls == ["healthy", "failing"]
    assert result.ok is False
    assert [(service.service_name, service.ok, service.error) for service in result.services] == [
        ("healthy", True, None),
        ("failing", False, "Dependency check failed"),
    ]
    assert all(service.duration_seconds >= 0 for service in result.services)
