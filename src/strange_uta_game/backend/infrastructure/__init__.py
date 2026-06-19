"""Infrastructure layer with lazy compatibility exports."""

from importlib import import_module


_EXPORTS = {
    "BassEngine": (".audio", "BassEngine"),
    "LyricParser": (".parsers.lyric_parser", "LyricParser"),
    "RubyAnalyzer": (".parsers.ruby_analyzer", "RubyAnalyzer"),
    "TextSplitter": (".parsers.text_splitter", "TextSplitter"),
    "SugProjectParser": (".persistence.sug_io", "SugProjectParser"),
}


def __getattr__(name: str):
    try:
        module_name, attribute = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    value = getattr(import_module(module_name, __name__), attribute)
    globals()[name] = value
    return value

__all__ = [
    "TextSplitter",
    "LyricParser",
    "RubyAnalyzer",
    "SugProjectParser",
    "BassEngine",
]
