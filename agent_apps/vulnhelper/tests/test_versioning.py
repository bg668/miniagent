from agent_apps.vulnhelper.domain.versioning import parse_range, version_in_range


def test_version_in_range() -> None:
    range_ = parse_range(">= 2.0.0, < 2.5.0")
    assert version_in_range("2.4.1", range_) is True
    assert version_in_range("2.5.0", range_) is False

