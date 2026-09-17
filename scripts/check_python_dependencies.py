"""Read the existing project declaration; exit 1 if optional Python setup is needed.

No network, environment/config output, imports of the product layer, or new
package manager. pip's vendored parser supports Python 3.9/3.10.
"""
from pathlib import Path
import importlib.metadata as metadata
import sys


def main():
    try:
        try:
            import tomllib
        except ImportError:
            from pip._vendor import tomli as tomllib
        from pip._vendor.packaging.requirements import Requirement
        from pip._vendor.packaging.version import Version

        root = Path(__file__).resolve().parent.parent
        project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
        if metadata.version(project["name"]) != project["version"]:
            return 1
        # A changed declaration must trigger editable reinstallation too.
        installed = set(metadata.requires(project["name"]) or [])
        for declared in project.get("dependencies", []):
            requirement = Requirement(declared)
            if requirement.marker and not requirement.marker.evaluate():
                continue
            if not any(str(Requirement(item)) == str(requirement) for item in installed):
                return 1
            if Version(metadata.version(requirement.name)) not in requirement.specifier:
                return 1
        return 0
    except Exception:
        # Do not print package configuration/URLs; pip reports installation errors
        # through the launcher's redaction pipeline if a repair is needed.
        return 1


if __name__ == "__main__":
    sys.exit(main())
