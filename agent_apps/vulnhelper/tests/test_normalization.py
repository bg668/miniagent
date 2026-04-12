from agent_apps.vulnhelper.domain.normalization import normalize_package_name, normalize_vuln_id


def test_normalize_package_name() -> None:
    assert normalize_package_name("TensorFlow CPU") == "tensorflow-cpu"


def test_normalize_vuln_id() -> None:
    assert normalize_vuln_id("cve-2023-1234") == "CVE-2023-1234"

