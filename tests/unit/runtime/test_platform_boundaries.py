from scripts.check_platform_boundaries import find_forbidden_checks


def test_ui_domain_and_application_have_no_direct_platform_checks():
    assert find_forbidden_checks() == []
