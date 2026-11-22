"""Render only non-secret deployment identifiers; fail on missing variables."""
import os
import re
from pathlib import Path
import yaml


def render(source=Path("k8s"), destination=Path(".rendered")):
    for path in source.rglob("*.yaml"):
        def replace(match):
            name = match.group(1)
            value = os.environ.get(name)
            if not value:
                raise ValueError(f"Missing manifest variable: {name}")
            return value
        content = re.sub(r"\$\{([A-Z_]+)\}", replace, path.read_text())
        list(yaml.safe_load_all(content))
        target = destination / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)


if __name__ == "__main__":
    render()
