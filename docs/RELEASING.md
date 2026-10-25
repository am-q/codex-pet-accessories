# 分享到 GitHub

将 **本项目目录本身**作为仓库根目录。不要上传它的上级工作区；上级可能包含个人数据、旧版备份与开发截图。

首次发布前：

1. 确认 `VERSION`、`CHANGELOG.md` 和 MIT 署名符合你的发布安排。
2. 在 Windows 上安装依赖，运行 `python -m unittest discover -s tests -v`。
3. 运行 `python src/pet_base.py --demo` 与 `--smoke` 检查界面。
4. 在自己的 Codex 环境测试启动、退出、切换样式、靠边换侧和真实额度读取。
5. 创建 GitHub 仓库后上传本目录。提供的工作流会在 push / pull request 时执行检查。

生成源码压缩包：

```powershell
.\.venv\Scripts\python.exe .\scripts\package_release.py
```

产物位于 `dist/codex-pet-accessories-<版本>-source.zip`。这是源码包，不是免安装 EXE；使用者仍需 Python 和安装依赖。

脚本按明确的文件清单与源码目录打包，不包含 `.venv`、运行数据、日志、Git 元数据、旧版备份、角色图片或 `dist` 本身。请使用这一产物分享源码，不要直接压缩整台电脑的开发目录。

公开问题报告可包含版本号、Windows / Python 版本和脱敏后的报错。不要上传 `auth.json`、个人用量缓存、订阅日期或完整桌面截图。自动源码包无法替代对手动添加内容的检查。


## 缩放回归门槛（2026-10-05）

`python scripts/package_release.py` 会先强制执行 `scripts/verify_windows.py`，覆盖单元测试、原生菜单、七样式动态刷新和窗口层级；失败不生成新包。GUI 验证需要可创建窗口的 Windows 会话。不要绕过验证后手动压缩交付。独立检查可以只运行 `python scripts/verify_windows.py`，不打包。
