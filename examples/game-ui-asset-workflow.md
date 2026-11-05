# Game UI Asset Workflow Examples

## 从效果图拆材并生成预览

```text
使用 $game-ui-asset-workflow，把我提供的游戏主页效果图拆成独立素材。
先检索项目已有的背景、人物、按钮和图标，只为缺少或不适用的部分补图。
提供独立 PNG、位置层级清单和素材浏览预览页，先交付可用首版。
```

默认使用快速模式，保留来源并检查素材结构与最终拼装，不自动填写评分报告。已有候选不适用时记录原因；生成图的轮次画布可独立于最终界面尺寸。

## 只修改一个素材

```text
使用 $game-ui-asset-workflow，把现有开始按钮的底板改成石质风格，保留文字和位置。
沿用现有任务目录，更新这个素材及相关拼装和预览。
```

局部修改只处理指定素材和受影响产物，复用仍有效的来源与检查结果。

## 只设计整体效果图

```text
使用 $game-ui-asset-workflow，设计一个水墨风 Roguelike 的主菜单效果图。
包含继续游戏、新游戏和设置，这次只需要整体效果图。
```

到效果图交付为止，无需建立拆材清单、预览网页或接入游戏。

## 明确要求严格验收

```text
使用 $game-ui-asset-workflow，严格验收已有拆材结果，按 90 分视觉标准检查。
重点查看完整人物和主按钮区域，提供当前对照证据，并修复阻塞验收的问题。
```

严格流程补齐完整组件区域，查看真实图像证据后评分。总分、外观维度与各关键区域分别达到门槛；结构检查不会增加视觉分数。分数是视觉判断，不是客观相似百分比。

## 本地脚本入口

在仓库根目录运行，替换 `RUN_DIR` 为实际任务目录：

```bash
python skills/game-ui-asset-workflow/scripts/ui_assets.py status --run RUN_DIR
python skills/game-ui-asset-workflow/scripts/ui_assets.py preview --run RUN_DIR
python skills/game-ui-asset-workflow/scripts/ui_assets.py status --run RUN_DIR --mode strict
python skills/game-ui-asset-workflow/scripts/ui_assets.py preview --run RUN_DIR --mode strict --replace
```

`status` 和 `preview` 默认只检查素材；严格审核须显式选择 `--mode strict`。`verify` 和 `pack` 始终要求严格证据。预览是快照，更新素材后需刷新；整个任务目录需由 HTTP 服务提供访问。

脚本需要 Python 3.10+ 和 Pillow 9.1+。清单、取材与校正格式见技能内的 `references/`。仓库中的技能是可安装副本，与个人本地技能目录不会自动同步。
