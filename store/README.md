# store · 上架素材与流程

这个目录是 Edge Add-ons 提交用到的全部素材，源码在上一层。

| 文件 | 用途 | 规格 |
|---|---|---|
| `video-speed-1.0.x.zip` | 提交的程序包（`tools/build_zip.py` 生成，manifest 在根层） | 16 个文件 |
| `screenshot-1..4.png` | 商店截图（1 B站 / 2 YouTube / 3·4 设置页） | 精确 1280×800 |
| `logo-300.png` | 扩展徽标 | 300×300 |
| `tile-440x280.png` / `tile-1400x560.png` | 小 / 大促销磁贴 | 官方尺寸 |
| `icon-1024.png` / `icon-preview.png` | 图标源图与预览 | — |
| `screenshots-grid.png` | 四张截图的拼版预览（自用，不上传） | — |
| `listing-zh-CN.md` / `listing-en-US.md` | 两种语言的名称/简介/详细描述/搜索词 | — |
| `build/skeleton-page.html` | 截图用的本地骨架页（不拿真实站点当素材的替代品） | — |

## 提交要点（Edge Add-ons / Partner Center）

- 注册与提交免费，需要**微软个人账号**（outlook/hotmail/live 等 MSA，工作账号不行）+ Partner Center 的 Edge program。
- 素材要求：截图 640×480 **或** 1280×800、最多 6 张；徽标 300×300；小磁贴 440×280；大磁贴 1400×560（可选）。
- 隐私问卷：**不收集数据**、**不使用远程代码**，权限理由＝`storage`（保存设置）与 `activeTab`（点扩展图标时读取当前标签页域名，用于「本网站隐藏/记忆」）。
- 审核通常 1–7 个工作日；更新提交时各 section 会继承上次的值，但**认证说明（certification notes）每次都要重新填**。
- 包内 `_locales/{zh_CN,en}` + manifest `default_locale` 决定「语言」行：要中英双语就必须把 `_locales` 打进包（`tools/build_zip.py` 已包含）。

## 改版本号时别忘了

1. `manifest.json` 的 `version` 递增（商店不接受版本回退）。
2. **重拍设置页截图**（`tests/shots_options.py`，设置页头部会显示版本号，脚本会核对版本再拍）。
3. `python3 tools/build_zip.py` 重打 zip（改任何扩展文件都要重打）。
4. 更新 `README.md` 与两份 `listing-*.md` 里描述到的行为。
