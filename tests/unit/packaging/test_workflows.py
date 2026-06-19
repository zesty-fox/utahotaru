from pathlib import Path


def test_stable_workflow_downloads_candidate_before_gate():
    workflow = Path(".github/workflows/release.yml").read_text(encoding="utf-8")

    assert "candidate_tag:" in workflow
    download = workflow.index("gh release download")
    gate = workflow.index("scripts/verify_release_gate.py")
    assert download < gate
    assert "release-gate-input" in workflow[download:gate]
