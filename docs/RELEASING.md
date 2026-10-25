# 分享到 GitHub

将 **本项目目录本身**作为仓库根目录。不要上传它的上级工作区；上级可能包含个人数据、旧版备份与开发截图。

发布前：

1. 确认 `VERSION`、`CHANGELOG.md` 和 MIT 署名符合你的发布安排。
2. 在 Windows 上安装依赖，运行 `python -m unittest discover -s tests -v`。
3. 运行 `python src/pet_base.py --demo` 与 `--smoke` 检查界面。
4. 在自己的 Codex 环境测试启动、退出、切换样式、靠边换侧和真实额度读取。
5. 创建 GitHub 仓库后上传本目录。提供的工作流会在 push / pull request 时执行检查。

生成源码压缩包：

```powershell
.\.venv\Scripts\python.exe .\scripts\package_release.py
```

产物位于 `dist/codex-pet-accessories-<版本>-source.zip`。这是提供给开发者的源码包；普通使用者下载下述 Windows 便携包。

脚本按明确的文件清单与源码目录打包，不包含 `.venv`、运行数据、日志、Git 元数据、旧版备份、原宠物精灵图或 `dist` 本身。源码包包含两张署名的公开宠物演示图，参见 `docs/SCREENSHOT_SOURCES.md`。请使用这一产物分享源码，不要直接压缩整台电脑的开发目录。

## Windows x64 便携包

在 64 位 Windows、Python 3.12 桌面环境中运行：

```powershell
python -m pip install -r requirements-build.txt
python scripts/build_windows.py
```

构建先执行全部源码检查，再用 PyInstaller 生成无控制台单文件 EXE，加入计划任务脚本和版本资源。产物 `dist/codex-pet-accessories-<版本>-windows-x64.zip` 包含 EXE、中英文简明说明、项目及依赖许可；不包含个人数据或宠物素材。

`verify_portable.py` 会把实际 ZIP 解压到带空格及中文的临时目录，移除 Python/Tcl 环境变量，只保留系统 PATH，启动 EXE 的隔离 smoke 模式，验证七种样式、内置资源、便携自动启动入口及无个人数据写入。通过后生成 `dist/SHA256SUMS.txt`，覆盖便携与源码两个 ZIP。

## GitHub Releases

更新 `VERSION`、`CHANGELOG.md`、`docs/RELEASE_NOTES.md` 与两版 README 中的版本下载链接。主分支推送版本或发布工作流变更后，`.github/workflows/release.yml` 自动在干净的 Windows runner 构建并检查；也可从 Actions 手动运行。

发布作业仅使用当前仓库的短期 `GITHUB_TOKEN`，先创建对应版本的草稿，上传两个已验证 ZIP 和校验文件，全部成功后才公开 Release。它不读取个人令牌。已公开版本不覆盖；已有不完整草稿会明确失败，需要维护者检查后处理，或改用新版本。

本地生成演示图时，仅提供从公开上游取得的参考精灵图：

```powershell
python scripts/capture_demo_screenshots.py --pet-sheet C:\public-reference\spritesheet.webp
```

生成脚本只捕获自己创建的演示窗口，虚拟数据固定，真实账户、配置、宠物状态访问被阻止。原精灵图不加入发布清单。

公开问题报告可包含版本号、Windows / Python 版本和脱敏后的报错。不要上传 `auth.json`、个人用量缓存、订阅日期或完整桌面截图。自动源码包无法替代对手动添加内容的检查。


## 缩放回归门槛（2026-10-05）

`python scripts/package_release.py` 会先强制执行 `scripts/verify_windows.py`，覆盖单元测试、原生菜单、七样式动态刷新和窗口层级；失败不生成新包。GUI 验证需要可创建窗口的 Windows 会话。不要绕过验证后手动压缩交付。独立检查可以只运行 `python scripts/verify_windows.py`，不打包。
