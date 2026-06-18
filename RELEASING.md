# 发布指南（Releasing）

本项目用 **GitHub Actions 自动打包 + draft 草稿发布**。你只需要：改版本号 → 填
CHANGELOG → 提交 → 打 tag 推送，CI 会构建三个变体、生成增量更新 manifest、把全部
资产传到一个 **draft Release**；你核对无误后手动点 **Publish**。

> 本地手动流程（`python scripts/release.py build` + 手动上传）仍然可用，见文末。

---

## TL;DR

```bash
# 1) 改版本号 + 注入 CHANGELOG 占位段落
python scripts/release.py prepare 1.2.2

# 2) 编辑 CHANGELOG.md，把 [1.2.2] 段落写完整（不能留“（待补充）”）

# 3) 提交（版本号、CHANGELOG、以及 build 后更新的 runtime 缓存都要进 git）
git add -A
git commit -m "release v1.2.2"

# 4) 打 tag 并推送 —— 这一步触发 CI
git tag SUGv1.2.2
git push origin main --tags

# 5) 等 CI 跑完 → 打开仓库的 Releases → 找到 draft SUGv1.2.2 → 核对资产/正文 → Publish
```

---

## 三条铁律（违反任意一条都会出问题）

### 1. `__version__` 必须等于 tag 去掉 `SUGv` 后的版本号
tag `SUGv1.2.2` ⇒ `src/strange_uta_game/__version__.py` 里 `__version__ = "1.2.2"`。
CI 第一步就会校验，不一致直接失败。`prepare` 会帮你写好，别再手动改回去。

### 2. 每个发布的 tag 都要有对应的、**填好的** CHANGELOG 段落
- Release 正文由 CI 从 `CHANGELOG.md` 的 `## [X.Y.Z]` 段落**自动抽取**——
  你不需要、也不应该手动往 Release 正文里粘贴。这样就杜绝了“正文和 CHANGELOG
  对不上 / 粘错版本 / 忘了填”这一类操作失误。
- 段落里若还留着模板占位符 `（待补充）`，CI 会**直接失败**，逼你补全。
- 更新器在跨版本升级时会聚合**中间每一个版本**的 changelog（`fetch_releases_since`）。
  所以哪怕某个版本只是小修，也要给它留一个 CHANGELOG 段落，否则用户在更新弹窗里
  会看到那一版“空白无说明”。

### 3. runtime 缓存文件要随版本一起提交
`scripts/.runtime-hash-cache*.json` 记录了上次 runtime 的内容哈希与依赖指纹，
**必须提交进 git**。CI 靠它判断“依赖有没有变、该不该复用上一版 runtime”。
本地跑过 `release.py build` 后，这些文件可能被更新，记得 `git add`。

---

## 增量更新是怎么在 CI 里保持有效的（原理，排障时看）

更新器把每个发布拆成两个增量分包：
- **app**（`*-app.zip`）：主程序 EXE + Updater + `_internal/strange_uta_game`，每版都变，必下。
- **runtime**（`*-runtime.zip`）：第三方库 + Python 运行时，约 80 MB，**依赖不变就不该重下**。

是否需要下载某个分包，取决于 manifest 里该分包的 `sha256`（**内容哈希**）与用户本地
`_internal/.installed_manifest.json` 是否一致。

**陷阱**：干净环境（CI runner、新克隆）重新打包 runtime，即使依赖完全相同，算出的
内容哈希也会变（`base_library.zip`、`.pyc` 里有时间戳），于是所有老用户的 runtime
哈希对不上 → 被迫重新全量下载 80 MB → 增量更新形同虚设。

**对策**（已写进 `.github/workflows/release.yml`）：build 之前，CI 用
`scripts/.runtime-hash-cache*.json` 里记录的版本号，从**上一个 Release** 下载它的
`*-runtime.zip` 放到 `dist/`。`release.py` 检测到依赖未变时会**直接复制这份旧 zip 的
字节**作为本次 runtime，于是哈希原样保留，老用户的 runtime 命中、跳过下载。
此时 build 带 `--require-runtime-reuse`：万一复用基准没到位却又本应复用，直接报错，
绝不静默重打。

什么时候会“合理地”重打一次 runtime（老用户一次性全量，之后恢复稳定）：
- **首次用 CI 发布**：上一版的 Release 里没有 `*-runtime.zip` 可供下载（比如之前停过
  增量），CI 拿不到复用基准 → 重打、重建基线。下一版起就稳了。
- **依赖真的变了**：改了 `requirements.txt` / `requirements-winrt.txt` / `requirements-variants.txt` 里打进包的库，
  dist-info 指纹变化 → runtime 内容确实变了，本就该让用户更新。

---

## 依赖变化 / 清理后：刷新 runtime 基线（重要）

CI 拿提交在 git 里的 `scripts/.runtime-hash-cache*.json` 当“依赖指纹基线”，比对本次
干净构建的 `dist-info`，一致才复用上一版 runtime。**只要你动了会打进包的依赖**——
改 `requirements.txt` / `requirements-winrt.txt` / `requirements-variants.txt`、增删 `build.py` 的 `--exclude-module`
等——这份基线就过期了，必须刷新一次，否则 CI 会每版都判定“依赖变了”而重打 runtime，
增量更新形同虚设。

一次性刷新步骤：

```bash
# 1) 本地各打一次（build.py 的排除已生效，产出的就是干净 runtime）
python scripts/release.py build --variant main
python scripts/release.py build --variant noWinIME
# → 这会重写 scripts/.runtime-hash-cache.json 与 -noWinIME.json

# 2) 把刷新后的缓存连同其它改动一起提交
git add scripts/.runtime-hash-cache*.json
git commit -m "chore: 刷新 runtime 依赖基线"
```

刷新后发布的**那一版**，CI 仍会重打一次 runtime（上一版没有“干净 runtime”可复用），
用户一次性全量下载；CI 把这版的干净 `*-runtime.zip` 发出去后，**从下一版起就稳定复用**。

> ⚠ 别删除“当前基线版本”的 `*-runtime.zip` 资产——CI 靠它当复用源。老版本的全量 zip
> 可以清，但基线那版的 runtime 分包要留着。

> 注：CI 不会把构建中更新的缓存提交回仓库（它只发 draft，不 push 代码）。所以
> “依赖没变”的普通版本里，基线一直冻结在你上次提交的那版——这没问题：依赖一致，
> 比对就一致，CI 会一路复用同一份 runtime。只有依赖真的变了，才需要按上面重刷一次。

## 变体与依赖

| 变体 | runner | 注音引擎 | 额外依赖 |
|------|--------|---------|---------|
| `main` | windows-latest | WinRT IME | `requirements.txt` + `requirements-winrt.txt`（WinRT 单独文件，mac/noWinIME 不装） |
| `noWinIME` | windows-latest | sudachi-mini | `requirements.txt` + `requirements-variants.txt` |
| `mac` | macos-latest | sudachi-mini | 同上；**CI 中允许失败**，不阻断 Windows 发布 |

`requirements-variants.txt` 里的 `sudachipy` **锁定了版本**——因为它会打进 noWinIME/mac
的 runtime，版本一漂就会改变 runtime 哈希、破坏增量。改它等同于改 runtime 基线。

---

## 手动触发与重跑

- 正常路径：`git push --tags` 推 `SUGv*` tag 自动触发。
- 补救/重跑：仓库 Actions 页 → `Release (draft)` → `Run workflow`，填入已存在的 tag
  （如 `SUGv1.2.2`）。CI 会复用已有 draft Release 并 `--clobber` 覆盖资产。

---

## 本地手动流程（备用）

不走 CI 时仍可本地出包：

```bash
python scripts/release.py prepare 1.2.2
# 编辑 CHANGELOG.md
python scripts/release.py build --variant main
python scripts/release.py build --variant noWinIME
# （可选）python scripts/release.py build --variant mac   # 需在 macOS 上
```

产物在 `dist/`：全量 zip、`*-app.zip`、`*-runtime.zip`、各自 `.sha256`、
`manifest-*.json`、`release_notes-*.md`。手动到 GitHub 新建 Release（tag `SUGvX.Y.Z`），
**把上面所有资产都传上去**（尤其 `manifest-*.json` 和两个 part zip，缺了增量更新就不工作），
正文粘 `release_notes-*.md` 全文。

> ⚠ 本地 build 后**不要**再单独跑 `python build.py`——`--noconfirm` 会清空
> `dist/<app>/`，把刚写好的 `.installed_manifest.json` 一并删掉。
