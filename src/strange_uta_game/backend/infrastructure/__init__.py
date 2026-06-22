"""Infrastructure layer."""

from .parsers.text_splitter import TextSplitter
from .parsers.lyric_parser import LyricParser
from .parsers.ruby_analyzer import RubyAnalyzer
from .persistence.sug_io import SugProjectParser
from .audio import bass_available

if bass_available:  # BASS 不可用（mac 等）时不触发 bass_engine 导入
    from .audio.bass_engine import BassEngine
else:
    BassEngine = None  # type: ignore[assignment,misc]

__all__ = [
    "TextSplitter",
    "LyricParser",
    "RubyAnalyzer",
    "SugProjectParser",
    "bass_available",
    "BassEngine",
]
