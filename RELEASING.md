# 跨平台发布指南

发布分为 `preview` 和 `stable` 两个通道。所有平台使用同一套应用代码和
PyInstaller 配置，只在原生 runner 上套薄平台安装层。

## 发布目标

| Target ID | Runner | 产物 |
|---|---|---|
| `windows-x86_64-windows-installer` | Windows x64 | Inno Setup `.exe` |
| `macos-universal2-macos-dmg` | macOS Universal 2 | 公证 `.dmg` |
| `linux-x86_64-appimage` | Linux x64 | `.AppImage` |
| `linux-x86_64-flatpak` | Linux x64 | `.flatpak` |
| `linux-x86_64-deb` | Linux x64 | Debian `.deb` |

`--variant main/noWinIME/mac` 仅保留一个发布周期的兼容映射，新脚本必须使用
`--target`。WinRT 是 Windows 上的可选注音增强，不是独立产品。

## 受保护凭据

在 GitHub `stable-release` environment 中配置：

- Windows：`WINDOWS_CERTIFICATE_PFX_BASE64`、`WINDOWS_CERTIFICATE_PASSWORD`
- Apple：`APPLE_CERTIFICATE_P12_BASE64`、`APPLE_CERTIFICATE_PASSWORD`、
  `APPLE_SIGNING_IDENTITY`、`APPLE_ID`、`APPLE_TEAM_ID`、`APPLE_APP_PASSWORD`
- 更新清单：`UPDATE_ED25519_PRIVATE_KEY_B64`
- Linux：`LINUX_GPG_PRIVATE_KEY_B64`

`src/strange_uta_game/config/update-public-key.pem` 必须是受保护 Ed25519 私钥对应
的公钥。私钥不得提交到仓库；生成清单时会校验密钥是否匹配。

## Preview

从 Actions 手动运行 `Cross-platform preview`，输入版本号。五个原生任务构建应用、
套安装包并发布 `preview-<version>` prerelease。Preview 可以用于安装兼容性验证，
不能写入 stable 更新通道。

对每个已安装产物运行：

```bash
StrangeUtaGame --smoke-test smoke-<target-id>.json
```

报告必须为 schema 1，且 `started`、`opened_legacy_project`、`exported_srt`、
`clean_exit` 均为 `true`。该检查不播放音频，也不修改测试项目。

## Stable

1. 从同一提交生成五个最终产物及各平台验签报告。
2. 收集五份安装包冒烟报告，以及 Windows x64、macOS Universal 2、Linux x64
   三份真实设备音频延迟报告。每份报告必须通过，校准后最大误差不得超过 `10 ms`。
3. 生成 schema-2 清单并签名：

```bash
python3 scripts/release.py manifest --help
python3 scripts/verify_release_gate.py release-gate-input --channel stable
```

4. 把五个产物、Linux GPG 签名、各平台验签报告、五份冒烟报告、三份音频报告和
   stable manifest 上传到同一个 candidate Release。
5. 运行 `Stable cross-platform release`，输入目标版本和该 candidate tag。受保护
   environment 审批通过后，workflow 会下载候选证据、重新执行门禁，并只把通过的
   输入发布为 `SUGv<version>` draft。
6. 人工核对版本、CHANGELOG、目标集合和签名后再发布 draft。更新器的 stable 清单
   只能在 GitHub Release 公开后切换。

音频报告使用真实输出到输入的回环连接生成：

```bash
python3 scripts/audio_loopback_probe.py --list-devices
python3 scripts/audio_loopback_probe.py --input DEVICE --output DEVICE --runs 20 \
  --calibration-ms 0 --report audio-<platform>.json
```

## 平台验签

Windows（PowerShell）：

```powershell
Get-AuthenticodeSignature .\StrangeUtaGame-*-windows-x86_64.exe | Format-List
packaging\windows\verify.ps1 .\StrangeUtaGame-*-windows-x86_64.exe
```

macOS：

```bash
codesign --verify --deep --strict --verbose=2 StrangeUtaGame.app
xcrun stapler validate StrangeUtaGame-*-macos-universal2.dmg
spctl --assess --type open --context context:primary-signature --verbose=2 StrangeUtaGame-*-macos-universal2.dmg
```

Linux：

```bash
gpg --verify StrangeUtaGame-*-linux-x86_64.AppImage.asc StrangeUtaGame-*-linux-x86_64.AppImage
gpg --verify StrangeUtaGame-*-linux-x86_64.flatpak.asc StrangeUtaGame-*-linux-x86_64.flatpak
gpg --verify strangeutagame_*_amd64.deb.asc strangeutagame_*_amd64.deb
```

## Linux 支持边界

官方构建边界是 x86_64：AppImage 面向通用桌面发行版，Flatpak 使用 Freedesktop
24.08 runtime，Debian 包面向当前 Debian/Ubuntu 系。支持 Wayland，并保留 X11
fallback；音频使用 PipeWire 的 PulseAudio 兼容层或 PulseAudio。其他架构、发行版
私有包格式和源码自行构建属于社区支持范围。

## 回滚

1. 在 GitHub Releases 将问题版本标记为 draft 或删除公开资产。
2. 把 stable schema-2 清单恢复为上一个已签名版本；不要复用或伪造旧签名。
3. 重新运行清单验签和 release gate，再发布恢复后的清单。
4. 在问题版本 CHANGELOG 和 Release 正文中写明回滚原因；修复版使用新版本号，禁止
   覆盖已分发的安装包。
