# 演示图来源 / Demonstration sources

## 简体中文

`demo-pet-accessories.png` 展示宠物与轻羽配件；`demo-settings.png` 展示相同宠物和应用实际的「样式与位置」设置面板。

两张图片由 `scripts/capture_demo_screenshots.py` 创建独立演示窗口后生成。配件使用应用自身绘制函数，面板来自应用实际菜单。截图仅通过 PrintWindow 读取该演示进程自己的窗口，校验窗口进程编号；不截取桌面或其他应用。

- 短周期剩余 **72%**，重置倒计时 **1 小时 42 分钟**。
- 周额度剩余 **54%**，重置倒计时 **3 天 6 小时**。
- 套餐为 `Demo`，示例续费日期为 `2030-01-01`。
- 使用空的临时数据目录。读取个人设置、账户额度、真实宠物状态或位置时会立即报错；完成后验证目录仍为空。

宠物来自公开项目 [Remielle Codex Pet / 小蕾米](https://github.com/HanaAyane/remielle-codex-pet)，作者 **HanaAyane / 小蕾米**，固定版本 [`35be534c1e48fb37e58e71da8d83511eada164af`](https://github.com/HanaAyane/remielle-codex-pet/tree/35be534c1e48fb37e58e71da8d83511eada164af)。演示从该版本 `output/xiaolemi/spritesheet.webp` 的左上角裁取第一帧（192 × 208）。原精灵图 SHA256：

```text
f049d67093d250f389045f4387a4baceae0e187d02603f98047acf40dfec543e
```

公开素材只用于这两张非商业演示图，不随便携程序分发。原始素材来源及使用范围见上游 [ASSET-USAGE.md](https://github.com/HanaAyane/remielle-codex-pet/blob/35be534c1e48fb37e58e71da8d83511eada164af/ASSET-USAGE.md) 和 [NOTICE.md](https://github.com/HanaAyane/remielle-codex-pet/blob/35be534c1e48fb37e58e71da8d83511eada164af/NOTICE.md)。NOTICE 将部分视觉来源归于米哈游 / HoYoverse 的[《绝区零》官方活动](https://act.mihoyo.com/zzz/event/e20260717reserve-pvy5cf/index.html)。第三方角色与素材不适用本项目 MIT 许可。

## English

`demo-pet-accessories.png` shows the pet with feather accessories; `demo-settings.png` also shows the application's actual appearance settings panel.

`scripts/capture_demo_screenshots.py` opens isolated demonstration windows, uses the real accessory renderer and menu, and captures only HWNDs owned by its own process through PrintWindow. It never captures the desktop or other applications.

All values are synthetic: **72%** remaining for the short period with **1 hour 42 minutes** until reset; **54%** for the weekly period with **3 days 6 hours** until reset; plan `Demo`; renewal date `2030-01-01`. A fresh temporary data directory is used. Any personal settings, account, real pet state, or position access raises an error. The directory must remain empty afterwards.

The public reference pet is [Remielle Codex Pet / 小蕾米](https://github.com/HanaAyane/remielle-codex-pet), by **HanaAyane / 小蕾米**, pinned to commit `35be534c1e48fb37e58e71da8d83511eada164af`. Only the first 192 × 208 frame of `output/xiaolemi/spritesheet.webp` is used. Its SHA256 is recorded above.

The source sprite sheet is not bundled with the application. These two noncommercial demonstration images contain third-party pet artwork excluded from the project's MIT license. Follow the pinned upstream [ASSET-USAGE.md](https://github.com/HanaAyane/remielle-codex-pet/blob/35be534c1e48fb37e58e71da8d83511eada164af/ASSET-USAGE.md) and [NOTICE.md](https://github.com/HanaAyane/remielle-codex-pet/blob/35be534c1e48fb37e58e71da8d83511eada164af/NOTICE.md), including attribution to miHoYo / HoYoverse's [Zenless Zone Zero official event](https://act.mihoyo.com/zzz/event/e20260717reserve-pvy5cf/index.html).
