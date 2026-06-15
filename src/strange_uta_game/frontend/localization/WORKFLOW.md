# 本地化工作流（i18n workflow）

新增/改动 UI 时按本文档操作，三种语言（zh_CN / ja_JP / en_US）保持同步。

---

## 一、约束（写代码时遵守）

### 1. 用 `tr` 包裹所有用户可见字符串

| 场景 | 写法 |
| --- | --- |
| QWidget 子类（`self.tr` 可用） | `self.tr("中文源串")` |
| 别名（频繁调用） | 函数顶部 `tr = self.tr` 然后 `tr("...")` |
| 模块函数 / 非 QObject | `QCoreApplication.translate("Ctx", "...")` |
| 一组工具函数共用同一上下文 | 定义 `def _tr(s): return QCoreApplication.translate("Ctx", s)`，后续 `_tr("...")` |

**只有字符串字面量被自动抽取**。`self.tr(variable)` / `self.tr(some_dict[key])` 抽取器拿不到。
解决：在同类同 scope 内显式哑调用每个字面量（参见 `ShortcutSubInterface._register_action_strings_for_extractor`、`SettingsInterface._tab_display_text`）。

### 2. format-string 时把变量换成 `{name}`

UI 文案禁止用 f-string 拼接。否则不同语言无法重排词序。

```python
# ❌
self.tr(f"已删除 {n} 条")
# ✅
self.tr("已删除 {n} 条").format(n=n)
```

### 3. 持久化 key 不要 tr

config.json 中的 key、格式枚举值（如 `"Nicokara (带注音)"` 用作 `_FMT_TO_IDX` key）保持源串；仅在 UI **显示**那一刻 tr 翻译。模式：

```python
items=[tr("LRC (增强型)"), tr("LRC (逐行)"), ...]   # 显示
# 保存读取仍按索引 ↔ 原 key 映射
```

### 4. 多语言下的 UI 大小

英文/日文长度可能比中文长 1.5~2 倍。对窗口/按钮：

- `setMinimumWidth(N)`：保证不被裁断（参考 timing/toolbar.py 的 `setMinimumWidth(110)`）
- 避免 `setFixedWidth`，用 `setMaximumWidth` 设上限即可
- 长 ComboBox 选项 → `combo.setMinimumWidth(180)`

---

## 二、SettingCard 子类的热更新

`SubSettingInterface` 提供两套登记 API（见 `sub_interfaces/base.py`）：

```python
self._tr_register(card, title_source="…", content_source="…", suffix_source="…")
self._tr_register_text(widget, "setText" | "setToolTip" | "setPlaceholderText", "源串")
```

登记后 base 类的 `_rebuild_for_language_change()` 自动遍历刷新——子页面通常不需要再写 changeEvent。

**特殊场景**：

- `ComboSettingCard` items 热更新：构造后调用 `card.set_item_sources(["源1","源2",...])`。
- 自定义 SettingCard（如 updater 模块 `_ProxyModeCard`）：自己写 `changeEvent`，按 `_tr(源)` 重设 titleLabel/contentLabel + 内部控件。

---

## 三、新增字符串后的发布步骤

```bash
# 1. 抽取最新源串到 .ts
python scripts/extract_ts.py

# 2. 看 (差异 / 是否有未匹配)
python scripts/apply_translations.py --show-unmatched

# 3. 编辑 scripts/translations_ja_JP.json / translations_en_US.json，把
#    unmatched 列出来的源串逐一补译

# 4. 应用 → .ts 写回
python scripts/apply_translations.py            # 默认 ja_JP
python scripts/apply_translations.py --lang en_US

# 5. zh_CN 走恒等映射（不用手写）
python scripts/build_zh_CN.py

# 6. 编译 .qm（需要 pyside6-lrelease；仅开发期）
pip install pyside6
pyside6-lrelease src/strange_uta_game/frontend/localization/translations/app.ja_JP.ts \
    -qm src/strange_uta_game/frontend/localization/translations/app.ja_JP.qm
pyside6-lrelease src/strange_uta_game/frontend/localization/translations/app.zh_CN.ts \
    -qm src/strange_uta_game/frontend/localization/translations/app.zh_CN.qm
pyside6-lrelease src/strange_uta_game/frontend/localization/translations/app.en_US.ts \
    -qm src/strange_uta_game/frontend/localization/translations/app.en_US.qm
pip uninstall pyside6 PySide6_Essentials PySide6_Addons shiboken6 -y    # 运行时不需要
```

**en_US 例外**：在线 .ts 是从 ja_JP 复制改的，所以 `apply_translations --lang en_US` 之前要确认 `app.en_US.ts` 不为空；如缺失：

```bash
cp src/strange_uta_game/frontend/localization/translations/app.ja_JP.ts \
   src/strange_uta_game/frontend/localization/translations/app.en_US.ts
# 然后跑 apply_translations 即可（脚本会把 ja_JP 翻译重置为 unfinished
# 再按 en_US JSON 重灌）
```

---

## 四、新增一门语言（如 en_US 之后加 ko_KR）

1. `manager.py` `AVAILABLE_LANGUAGES` 加：
   ```python
   Language(code="ko_KR", native_name="한국어", qlocale_name="ko_KR"),
   ```
2. 复制 `app.ja_JP.ts` → `app.ko_KR.ts`，把 `language="ja_JP"` 改成 `ko_KR`，所有 translation 元素改 `type="unfinished"`。
3. 新建 `scripts/translations_ko_KR.json`，逐条翻译。
4. 执行三步：apply_translations.py --lang ko_KR → lrelease → 完成。

---

## 五、自检（pseudo 模式）

切到「⟦pseudo⟧」可一眼看出哪些字符串没 tr 包裹（普通文字被 `⟦⟧` 包起，未包裹的中文保持原样）。

```bash
# 跑一次未包裹中文扫描（自动启发式）
python scripts/find_unwrapped.py
```

结果中可能有 logging / config sentinel 等非 UI 字符串，是预期的；要看的是 UI 控件构造期的字面量。

---

## 六、典型陷阱

| 现象 | 根因 | 解决 |
| --- | --- | --- |
| 切语言后某文字没刷 | 用 `self.tr(变量)` 或类常量字面量 | 加显式 `self.tr("字面")` 哑调用，或重写 changeEvent 主动 setText |
| 切语言后某下拉项没刷 | ComboBox items 仅在构造时填一次 | `set_item_sources([源串...])` 或 changeEvent 内 clear+addItems |
| en_US 翻译后某条仍是中文 | translations_en_US.json 缺这条 | apply_translations 输出会列出，补 JSON 即可 |
| 按钮文字被裁断 | 翻译变长 | `setMinimumWidth` 或缩短英文标签 |
| pseudo 模式 ⟦字符⟧ 没出现 | 字面量没走 tr | grep 源码定位、补 tr |
| 状态/动态文本切语言后停在旧语种 | 文本由事件回调设置（如 lbl_status / lbl_audio_name），自然没在 changeEvent 中复跑 | 用**状态码**（如 `_status_state = "playing"`）+ `_tr_xxx(state)` 渲染；changeEvent 时按当前状态重渲染 |
| 自定义 SettingCard 子类（带内部按钮 / LineEdit / 多选）切语言不刷 | 内部子控件没在父类的 _tr_register 注册表里 | 在该 SettingCard 子类自己写 changeEvent，主动 setText/setPlaceholderText |
| InfoBar 显示 ctx 与抽取 ctx 错位（如 FileLoader 用 self._editor.tr） | Qt 按 self._editor.class 查上下文，抽取器按 enclosing class 归类 | 已由 `_FallbackTranslator` 处理（source-only 兜底）；无需额外动作 |

---

## 七、文件清单

| 路径 | 角色 |
| --- | --- |
| `scripts/extract_ts.py` | UTF-8 安全 AST 抽取器（自识别 `def _tr / lambda` 别名上下文） |
| `scripts/apply_translations.py` | JSON → .ts 灌入（`--lang` 切换语言） |
| `scripts/build_zh_CN.py` | 由 ja_JP.ts 派生恒等 zh_CN.ts |
| `scripts/find_unwrapped.py` | 启发式扫描未包裹中文，限 UI 上下文 |
| `scripts/translations_*.json` | 各语言的 source → translation 字典 |
| `src/strange_uta_game/frontend/localization/translations/app.<lang>.ts` | Qt Linguist 源文件（提交，便于审阅 diff） |
| `src/strange_uta_game/frontend/localization/translations/app.<lang>.qm` | 运行时加载的二进制（提交，避免发布时再编译） |
| `src/strange_uta_game/frontend/localization/manager.py` | `install_translators` / `apply_language` / `AVAILABLE_LANGUAGES` |
| `src/strange_uta_game/frontend/settings/sub_interfaces/base.py` | `_tr_register` 注册中心 + `_rebuild_for_language_change` |
