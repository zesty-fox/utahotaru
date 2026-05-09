"""快捷键设置测试。"""

from types import SimpleNamespace

from strange_uta_game.frontend.settings.settings_interface import InfoBar
from strange_uta_game.frontend.settings.settings_interface import SettingsInterface


class _FakeButton:
    """模拟按键按钮。

    入参：key_name 初始按键（支持 "F5:short" / "F5:long" / "F5" 格式）。
    出参：无。
    """

    def __init__(self, key_with_trigger: str):
        if ":" in key_with_trigger:
            key_part, trigger_part = key_with_trigger.rsplit(":", 1)
            self._captured_key = key_part.strip()
            self._trigger_type = trigger_part.strip().lower() or "short"
        else:
            self._captured_key = key_with_trigger
            self._trigger_type = "short"
        self._original_key = self._captured_key
        self._original_trigger = self._trigger_type

    def get_key(self) -> str:
        return self._captured_key

    def get_trigger_type(self) -> str:
        return self._trigger_type

    def restore_original_key(self):
        self._captured_key = self._original_key
        self._trigger_type = self._original_trigger

    def set_captured_key(self, key_name: str):
        self._captured_key = key_name

    def set_trigger_type(self, trigger_type: str):
        self._trigger_type = trigger_type


class _FakeCard:
    """模拟快捷键卡片。

    入参：primary 第一按键，secondary 第二按键。
    出参：无。
    """

    def __init__(self, primary: str = "", secondary: str = ""):
        self.btn_key1 = _FakeButton(primary)
        self.btn_key2 = _FakeButton(secondary)

    def value(self) -> str:
        first_key = self.btn_key1.get_key().strip()
        first_trigger = self.btn_key1.get_trigger_type()
        second_key = self.btn_key2.get_key().strip()
        second_trigger = self.btn_key2.get_trigger_type()
        k1 = f"{first_key}:{first_trigger}" if first_key else ""
        k2 = f"{second_key}:{second_trigger}" if second_key else ""
        if k1 and k2:
            return f"{k1},{k2}"
        return k1 or k2

    def all_keys(self) -> list[str]:
        keys: list[str] = []
        for button in (self.btn_key1, self.btn_key2):
            key_name = button.get_key().strip()
            if key_name:
                keys.append(key_name.upper())
        return keys

    def all_keys_with_trigger(self) -> list[tuple[str, str]]:
        keys: list[tuple[str, str]] = []
        for button in (self.btn_key1, self.btn_key2):
            key_name = button.get_key().strip()
            trigger = button.get_trigger_type()
            if key_name:
                keys.append((key_name.upper(), trigger))
        return keys

    def clear_key_by_name(self, key_name: str):
        upper_key = key_name.upper()
        for button in (self.btn_key1, self.btn_key2):
            if button.get_key().strip().upper() == upper_key:
                button.set_captured_key("")


class _SignalRecorder:
    """模拟信号对象。

    入参：无。
    出参：无。
    """

    def __init__(self):
        self.emit_count = 0

    def emit(self):
        self.emit_count += 1


class _SettingsRecorder:
    """模拟设置对象。

    入参：无。
    出参：无。
    """

    def __init__(self):
        self.save_count = 0

    def save(self):
        self.save_count += 1


def _build_interface_double(
    changed_card: _FakeCard,
    other_card: _FakeCard,
    changed_action: str = "play_pause",
    other_action: str = "stop",
):
    """构造最小化设置界面替身。

    入参：changed_card 当前修改卡片，other_card 同模式另一卡片。
    出参：可调用 SettingsInterface 方法的替身对象。
    """

    interface = SimpleNamespace()
    interface._loading_settings = False
    interface._shortcut_cards = {
        "timing_mode": {
            changed_action: changed_card,
            other_action: other_card,
        },
        "edit_mode": {},
    }
    interface._SHORTCUT_MODES = SettingsInterface._SHORTCUT_MODES
    interface._SHORTCUT_ACTIONS = SettingsInterface._SHORTCUT_ACTIONS
    interface._get_all_shortcut_cards = lambda: []
    interface._schedule_auto_save_calls = 0
    interface._schedule_auto_save = lambda *_args: setattr(
        interface,
        "_schedule_auto_save_calls",
        interface._schedule_auto_save_calls + 1,
    )
    return interface


def test_conflict_on_empty_preserves_others(monkeypatch):
    warning_calls: list[dict[str, str]] = []
    monkeypatch.setattr(InfoBar, "warning", lambda **kwargs: warning_calls.append(kwargs))

    card_a = _FakeCard("")
    card_b = _FakeCard("Ctrl+S:short")
    card_a.btn_key1._original_key = ""
    card_a.btn_key1.set_captured_key("Ctrl+S")
    interface = _build_interface_double(card_a, card_b)

    SettingsInterface._on_shortcut_changed(interface, card_a, "Ctrl+S")

    assert card_a.value() == ""
    assert card_b.value() == "Ctrl+S:short"
    assert len(warning_calls) == 1
    assert interface._schedule_auto_save_calls == 0


def test_conflict_on_set_preserves_others(monkeypatch):
    monkeypatch.setattr(InfoBar, "warning", lambda **kwargs: None)

    card_a = _FakeCard("F5:short")
    card_b = _FakeCard("Ctrl+S:short")
    card_a.btn_key1._original_key = "F5"
    card_a.btn_key1._original_trigger = "short"
    card_a.btn_key1.set_captured_key("Ctrl+S")
    interface = _build_interface_double(card_a, card_b)

    SettingsInterface._on_shortcut_changed(interface, card_a, "Ctrl+S")

    assert card_a.value() == "F5:short"
    assert card_b.value() == "Ctrl+S:short"
    assert interface._schedule_auto_save_calls == 0


def test_save_path_does_not_clear_other_cards(monkeypatch):
    clear_calls: list[tuple[str, str]] = []
    card_a = _FakeCard("F5:short")
    card_b = _FakeCard("Ctrl+S:short")

    def _record_clear(self, key_name: str):
        clear_calls.append((self.value(), key_name))

    monkeypatch.setattr(_FakeCard, "clear_key_by_name", _record_clear)

    interface = SimpleNamespace()
    interface._collect_settings_calls = 0
    interface._collect_settings = lambda: setattr(
        interface,
        "_collect_settings_calls",
        interface._collect_settings_calls + 1,
    )
    interface._settings = _SettingsRecorder()
    interface.settings_changed = _SignalRecorder()
    interface._store = None
    interface._shortcut_cards = {
        "timing_mode": {
            "add_checkpoint": card_a,
            "play_pause": card_b,
        },
        "edit_mode": {},
    }

    SettingsInterface._do_auto_save(interface)

    assert card_a.value() == "F5:short"
    assert card_b.value() == "Ctrl+S:short"
    assert clear_calls == []
    assert interface._collect_settings_calls == 1
    assert interface._settings.save_count == 1
    assert interface.settings_changed.emit_count == 1


def test_same_key_different_trigger_no_conflict(monkeypatch):
    """同按键不同触发类型不应冲突。"""
    warning_calls: list[dict[str, str]] = []
    monkeypatch.setattr(InfoBar, "warning", lambda **kwargs: warning_calls.append(kwargs))

    card_a = _FakeCard("F5:short")
    card_b = _FakeCard("F5:long")
    interface = _build_interface_double(card_a, card_b)

    SettingsInterface._on_shortcut_changed(interface, card_a, "F5:short")

    # 同键不同触发类型，不应冲突
    assert card_a.value() == "F5:short"
    assert card_b.value() == "F5:long"
    assert len(warning_calls) == 0
    assert interface._schedule_auto_save_calls == 1


def test_same_key_same_trigger_conflict(monkeypatch):
    """同按键同触发类型应冲突。"""
    warning_calls: list[dict[str, str]] = []
    monkeypatch.setattr(InfoBar, "warning", lambda **kwargs: warning_calls.append(kwargs))

    card_a = _FakeCard("F5:short")
    card_b = _FakeCard("F5:short")
    # 设置原始值用于冲突恢复
    card_a.btn_key1._original_key = "F5"
    card_a.btn_key1._original_trigger = "short"
    interface = _build_interface_double(card_a, card_b)

    SettingsInterface._on_shortcut_changed(interface, card_a, "F5:short")

    # 同键同触发类型，应冲突
    assert len(warning_calls) == 1
    assert interface._schedule_auto_save_calls == 0


def test_tag_now_conflicts_with_long_press(monkeypatch):
    """tag_now（打轴键）应与同键的长按动作冲突。"""
    warning_calls: list[dict[str, str]] = []
    monkeypatch.setattr(InfoBar, "warning", lambda **kwargs: warning_calls.append(kwargs))

    # tag_now 绑定 Space:short，另一动作绑 Space:long
    card_tag = _FakeCard("Space:short")
    card_other = _FakeCard("Space:long")
    card_other.btn_key1._original_key = "Space"
    card_other.btn_key1._original_trigger = "long"
    interface = _build_interface_double(
        card_other, card_tag,
        changed_action="add_checkpoint", other_action="tag_now",
    )

    SettingsInterface._on_shortcut_changed(interface, card_other, "Space:long")

    # tag_now 占用短按和长按，应冲突
    assert len(warning_calls) == 1
    assert interface._schedule_auto_save_calls == 0


def test_tag_now_conflicts_with_short_press(monkeypatch):
    """tag_now（打轴键）应与同键的短按动作冲突。"""
    warning_calls: list[dict[str, str]] = []
    monkeypatch.setattr(InfoBar, "warning", lambda **kwargs: warning_calls.append(kwargs))

    # tag_now 绑定 Space:short，另一动作也绑 Space:short
    card_tag = _FakeCard("Space:short")
    card_other = _FakeCard("Space:short")
    card_other.btn_key1._original_key = "Space"
    card_other.btn_key1._original_trigger = "short"
    interface = _build_interface_double(
        card_other, card_tag,
        changed_action="add_checkpoint", other_action="tag_now",
    )

    SettingsInterface._on_shortcut_changed(interface, card_other, "Space:short")

    # tag_now 占用短按和长按，应冲突
    assert len(warning_calls) == 1
    assert interface._schedule_auto_save_calls == 0
