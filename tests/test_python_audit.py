import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


def load_auditor():
    spec = importlib.util.spec_from_file_location(
        "qsou_python_audit", Path(__file__).resolve().parents[1] / "scripts/audit_python_dependencies.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.audit_dependencies


def test_unpublished_dependency_is_audited_at_its_actual_version():
    audit = load_auditor()
    dependency = SimpleNamespace(name="Twisted", version="26.4.0.post0", is_skipped=lambda: False)
    unavailable = SimpleNamespace(is_skipped=lambda: True)
    seen = []
    primary = SimpleNamespace(query=lambda item: (unavailable, []))
    fallback = SimpleNamespace(query=lambda item: (seen.append(item) or item, []))
    assert audit([dependency], primary, fallback) == 0
    assert seen == [dependency]


def test_fallback_and_primary_vulnerabilities_both_fail_the_audit():
    audit = load_auditor()
    dependency = SimpleNamespace(name="package", version="1.0", is_skipped=lambda: False)
    vulnerable = SimpleNamespace(id="CVE-regression")
    for primary_skips in (False, True):
        result = SimpleNamespace(is_skipped=lambda: primary_skips)
        primary = SimpleNamespace(query=lambda item: (result, [] if primary_skips else [vulnerable]))
        fallback = SimpleNamespace(query=lambda item: (item, [vulnerable]))
        assert audit([dependency], primary, fallback) == 1


def test_unresolved_dependencies_and_unavailable_fallback_cannot_be_silently_skipped():
    audit = load_auditor()
    unresolved = SimpleNamespace(name="package", is_skipped=lambda: True)
    resolved = SimpleNamespace(name="package", version="1.0", is_skipped=lambda: False)
    unavailable = SimpleNamespace(query=lambda item: (unresolved, []))
    for dependencies in ([unresolved], [resolved], []):
        with pytest.raises(RuntimeError):
            audit(dependencies, unavailable, unavailable)
