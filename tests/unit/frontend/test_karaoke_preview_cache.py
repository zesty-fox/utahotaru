from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

from strange_uta_game.backend.domain import Character, Project, Ruby, RubyPart, Sentence, Singer
from strange_uta_game.frontend.editor.timing import karaoke_preview as preview_module


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _char(text: str, ruby: str, *, linked: bool = False) -> Character:
    ch = Character(
        char=text,
        check_count=1,
        timestamps=[1000],
        linked_to_next=linked,
    )
    ch.set_ruby(Ruby(parts=[RubyPart(text=ruby)]))
    ch.push_to_ruby()
    return ch


def _project_with_linked_word() -> Project:
    singer = Singer(name="default", is_default=True)
    return Project(
        singers=[singer],
        sentences=[
            Sentence(
                singer_id=singer.id,
                characters=[
                    _char("長", "なが", linked=True),
                    _char("連", "れん", linked=True),
                    _char("詞", "し"),
                ],
            )
        ],
    )


class _DummySignal:
    def connect(self, callback):
        pass


class _DummyTheme:
    changed = _DummySignal()


def test_position_and_focus_changes_do_not_invalidate_render_cache(qapp, monkeypatch):
    monkeypatch.setattr(preview_module, "theme", _DummyTheme())

    preview = preview_module.KaraokePreview()
    preview.set_project(_project_with_linked_word())

    assert preview._sentence_cache
    cached_entry = preview._sentence_cache[0]
    global_version = preview._global_version

    preview.set_current_position(0, 1)
    preview.set_focus_position(0, 2)
    preview.scroll_current_line_to_center()
    preview.request_repaint()

    assert preview._global_version == global_version
    assert preview._sentence_cache[0] is cached_entry

    preview._update_display()

    assert preview._global_version == global_version + 1


def test_line_invalidation_advances_uncached_line_version(qapp, monkeypatch):
    monkeypatch.setattr(preview_module, "theme", _DummyTheme())

    preview = preview_module.KaraokePreview()
    preview.set_project(_project_with_linked_word())

    assert preview._sentence_cache
    assert preview._line_versions.get(0, 0) == 0

    preview._invalidate_line(0)

    assert preview._line_versions[0] == 1
