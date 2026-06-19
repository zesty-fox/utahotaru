"""Cross-platform audio package import contracts."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(sys.platform == "win32", reason="non-Windows regression")
def test_audio_package_imports_without_loading_windows_bass_backend():
    project_root = Path(__file__).resolve().parents[3]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root / "src")
    code = """
import sys

from strange_uta_game.backend.infrastructure import BassEngine
from strange_uta_game.backend.infrastructure.audio import AudioPlaybackError, create_audio_engine
from strange_uta_game.backend.infrastructure.audio.keysound_player import KeySoundPlayer

assert "strange_uta_game.backend.infrastructure.audio.bass_engine" not in sys.modules
assert KeySoundPlayer.__name__ == "KeySoundPlayer"
create_audio_engine()
assert "strange_uta_game.backend.infrastructure.audio.bass_engine" not in sys.modules

try:
    BassEngine()
except AudioPlaybackError as error:
    assert "Windows" in str(error)
else:
    raise AssertionError("unsupported BASS backend was constructed")
"""

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
