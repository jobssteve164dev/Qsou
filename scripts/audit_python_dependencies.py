"""Audit resolved graphs without skipping unpublished, hash-pinned source builds."""

import argparse
from pathlib import Path


def audit_dependencies(dependencies, primary, fallback):
    count = 0
    vulnerable = False
    for dependency in dependencies:
        if dependency.is_skipped():
            raise RuntimeError(f"Unresolved dependency: {dependency.name}")
        result, findings = primary.query(dependency)
        source = "PyPI"
        if result.is_skipped():
            # pip-audit's PyPI service returns this only for an absent release (404).
            # Retain the resolver's actual version when querying the source build.
            result, findings = fallback.query(dependency)
            source = "OSV"
        if result.is_skipped():
            raise RuntimeError(f"Dependency could not be audited: {dependency.name}")
        count += 1
        if findings:
            vulnerable = True
            for finding in findings:
                print(f"{dependency.name} {dependency.version}: {finding.id} ({source})")
        elif source == "OSV":
            print(f"{dependency.name} {dependency.version}: audited through OSV")
    if not count:
        raise RuntimeError("The dependency graph is empty")
    print(f"Audited {count} dependencies; zero skipped")
    return int(vulnerable)


def main():
    # These APIs are bound to the exact pip-audit version installed by Security CI.
    from pip_audit._dependency_source.requirement import RequirementSource
    from pip_audit._service.osv import OsvService
    from pip_audit._service.pypi import PyPIService

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("requirements", type=Path)
    args = parser.parse_args()
    source = RequirementSource([args.requirements])
    return audit_dependencies(source.collect(), PyPIService(), OsvService())


if __name__ == "__main__":
    raise SystemExit(main())
