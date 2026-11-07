# 肥鱼跑酷 · 海滨算力站

独立的 Three.js 网页 3D 试玩。蓝发鲸鱼娘沿三条轨道向前跑，玩家用键盘换道、跳跃和翻滚。首段按顺序介绍列车、橙色低路障和黄色横杆。跑到 320 米进入深海算力舱，之后海滨与深海每 320 米交替。

从 [GitHub Releases](https://github.com/upinking/fish-run-web/releases) 下载 ZIP，解压后双击「肥鱼跑酷.html」即可离线试玩。建议用支持 WebGL 2 的桌面浏览器。

## 本地开发

首次安装依赖和启动时，在项目目录运行下列命令。安装后，macOS 用户也可以在 Finder 中双击「启动网页版.command」。

```sh
npm ci
npm run dev -- --port 5176
```

用浏览器打开终端给出的本地地址。空格开始和跳跃，左右方向键或 A/D 换道，↓ 或 S 向前翻滚，Q 消耗满格算力冲刺，Esc 暂停，R 重跑。

- `npm test` 检查障碍、护盾、赛道续接和固定步长。
- `npm run build` 生成可静态托管的 `dist/`。
- `npm run build:offline` 生成可双击运行的单文件版 `dist/肥鱼跑酷.html`。
- `blender/build_station.py` 和 `blender/build_deepsea.py` 分别导出海滨站和深海隧道。游戏从 `public/models/` 加载 GLB。

开发时的参考视频、分镜和角色四视图保存在本地 `reference/`。关卡采用统一的前进方向，跟拍镜头始终位于人物后方。

深海场景参照 `reference/scenes/deepsea-compute-tunnel.png` 的 GPT Image 概念图建模。主菜单沿用原版的站台、人物与眨眼图层，人物在右侧缓慢上下漂浮。

当前的鲸鱼娘由 `reference/character/` 中的 GPT Image 四视图经混元生成，再在 Blender 里减面、绑定和制作动作。`runner-hunyuan.glb` 带有贴图以及跑、跳、翻滚和算力冲刺动画。用原始混元导出的 GLB 可以重新生成游戏模型。

裙摆腰线固定，八个裙边区段用弹簧模拟惯性和回弹。大腿和鲸尾的简化碰撞体限制额外摆幅，翻滚过杆时收住摆动。

算力充满后按 Q，「嘘」的人物抠图短暂放大到屏幕中央，鲸鱼娘进入五秒滑翔冲刺。人物、能量波和尾迹跟随技能进度。

```sh
blender --background --python blender/build_hunyuan_runner.py -- /path/to/hunyuan.glb
```
