from agent_apps.vulnhelper.domain.record_parser import parse_vendors_products


def test_parse_vendors_products() -> None:
    raw = '["tensorflow-cpu", "tensorflow-cpu affected range (ECOSYSTEM): >= 0, < 2.5.3", "tensorflow-cpu fixed in (ECOSYSTEM): 2.5.3"]'
    impacts = parse_vendors_products(raw)
    assert impacts
    assert impacts[0].product_name == "tensorflow-cpu"
    assert impacts[0].fixed_versions == ["2.5.3"]

