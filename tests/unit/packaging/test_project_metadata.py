import tomllib
from pathlib import Path


def test_project_metadata_matches_supported_python_runtime():
    metadata = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]

    assert metadata["requires-python"] == ">=3.13,<3.14"
    python_classifiers = [
        value
        for value in metadata["classifiers"]
        if value.startswith("Programming Language :: Python :: 3.")
    ]
    assert python_classifiers == ["Programming Language :: Python :: 3.13"]
