---
name: game-ui-asset-workflow
description: 游戏主页、菜单与 HUD 的效果图设计、独立素材拆分和界面还原。用于从效果图提取或补全素材、修改局部素材、制作素材对比网页，或按请求接入游戏；优先复用已有资源，默认交付可用首版，支持按需精修与严格视觉验收。
---

# 游戏界面生图与素材还原

## 按请求选择入口

| 当前请求 | 从哪里开始、交付到哪里 |
|---|---|
| 只要效果图 | 依据风格和布局生成整体图，到效果图交付为止 |
| 已有效果图，需要拆材 | 使用选定原图，检索已有资源，再补齐独立层并拼装 |
| 只改一个素材或局部 | 沿用现有清单与来源，更新指定项及受影响的拼装/预览 |
| 需要预览网页 | 在素材任务基础上使用现成模板，见 [preview.md](references/preview.md) |
| 接入游戏 | 使用项目既有资源与引擎约定，完成真实运行界面和必要交互检查 |
| 明确要求精修或严格验收 | 直接进入指定范围；精修不自动要求打分，明确要求评分时才用 [acceptance.md](references/acceptance.md) |

默认快速首版，不强迫已有成果或明确要求精修的任务重走首版流程。沿用用户已有风格、保留项和授权；已获授权的拆材连续完成，不逐轮确认。素材和预览任务本身不授权修改游戏源码。

## 工作原则

- **可用即交付。** 常规检查集中做一轮，复用仍有效的结果。默认不逐区评分、不生成审核草稿、不为了达到 90 分追加精修。
- **修复有边界。** 核心素材缺失、空图、假透明、严重裁断、网页打不开等影响使用的问题，修复后只复查受影响部分。有新证据且有进展就继续；可用即停止。达到用户预算、外部条件不可用，或相同方法连续失败且无新证据时，保留成果并说明未完成项，不盲目重试或扩成环境排障。
- **差异不自动变成返工。** 不影响使用的纹理、墨色或轻微位置差异随首版说明；用户指定修改范围时按范围处理。严格验收另按其门槛判断。
- **来源真实、边界完整。** 保留原图、提示词和必要处理参数。不能把完整效果图冒充独立背景，也不能用阈值抠图替代真实 Alpha。复杂美术使用生图或补绘，脚本用于测量、校正、切图和拼装。
- **按产物检查。** 素材看最终拼装，网页看预览，游戏实装看真实运行页面与代表性交互；不重复做无新信息的静态/实机截图和全量回归。项目要求的检查照常完成。

生图优先使用内置 `image_gen`，需要时读取可用的 `imagegen` 技能；透明输出设置 `transparent_background: true`。不因批量或像素控制改用外部 API，也不向内置工具用户索要 API Key。维护本技能、评审流程时无需生图。

任务文件放在项目的独立任务目录，不写进技能目录。替换输出用新版本名或受支持命令的 `--replace`，后者将旧产物归档到任务内 `history/`；原始输入保持不动。

## 1. 检索与获取决策

先查已有资源索引、图集帧名和目标页面引用，再按用途、别名和相关目录缩小候选。只查看本次候选，确认外观、尺寸、Alpha 和完整性；不默认全量解码、哈希或制作全库缩略图。文件名未命中不能单独证明缺失。

每项选择：**直接复用 / 处理已有 / 需要新制作 / 未确认**。已有候选不等于可用素材：合理裁切、等比缩放或九宫格仍无法满足已授权目标时，记录具体原因，转入新制作。保留候选记录，不能把“不适用”写成“不存在”。已有授权足够时直接执行；只有真正缺少设计决策或超出范围才询问。

整体图里可见的对象不等于已存在独立透明层。仅为缺少或不适用的层生成；全部能复用时跳过生图。获取方式、简短复用记录和清单字段见 [plan-format.md](references/plan-format.md)。

## 2. 清单与原图尺寸画布

拆材前读取 [plan-format.md](references/plan-format.md)。保存选定图为 `reference/mockup.png`，读取实际尺寸作为最终 `plan.canvas`。逐区列出背景、人物、底板、图标、文字和装饰，区分唯一素材与实例。

快速清单保留素材 ID、获取方式/来源、文件、尺寸、Alpha，以及实例位置和层级；生成项另有轮次与裁框。留边、锚点等按需记录，哈希由脚本生成。快速模式可省略 `regions`；严格评分前再补齐完整组件区域。

- `plan.canvas` 固定最终界面尺寸，`instances[].xy` 是素材在界面中的位置。
- 无论大素材还是小素材，所有轮次画布和标注图都必须与原图实际像素宽高完全一致。`rounds[].canvas` 可省略；显式填写时必须等于 `plan.canvas`，不得改用局部小画布或更大画布。
- `sheet_box` 位于原图同尺寸的轮次画布内，宽高等于裁切后导出素材的尺寸。独立 PNG 按裁框导出，不要求保留整屏透明空白；素材保持原稿像素比例，拼装按 1:1 绘制。
- 同轮裁框不得重叠；背景和互相遮挡的对象分轮。单轮局部坐标不能当作最终界面位置。

```text
python SKILL_DIR/scripts/ui_assets.py annotate --run RUN_DIR --all
python SKILL_DIR/scripts/ui_assets.py annotate --run RUN_DIR --round r02
```

`--all` 在原图上标注最终布局；`--round` 标注本轮要提取的素材裁框，指南也必须与原图同分辨率。实际查看标注，确保位置、完整范围与留边正确。

## 3. 取材与必要校正

需生成时读取 [generation.md](references/generation.md)，保存提示词和原始结果。整体图约束外观，轮次标注约束排布；不假定模型严格遵守像素尺寸。需要本地校正时读取 [processing.md](references/processing.md)。

```text
python SKILL_DIR/scripts/ui_assets.py register --run RUN_DIR --round r02
python SKILL_DIR/scripts/ui_assets.py extract --run RUN_DIR --round r02
```

原始结果已满足轮次尺寸和布局时跳过 register；直接复用用 `extract --asset ID`。人物/图标仅等比缩放和平移，可伸缩底板可用九宫格，补背景保留可见原稿。原始生图、标准化画布、独立 PNG 分开保存。

## 4. 拼装与交付

按产物选命令，不把命令表当固定流水线。`compose` 已包含素材结构检查，无需紧接着重复 `audit`；`inspect` 用于需要查看的透明素材，`compare` 用于需要定位的差异。

```text
python SKILL_DIR/scripts/ui_assets.py compose --run RUN_DIR
python SKILL_DIR/scripts/ui_assets.py inspect --run RUN_DIR --asset hero
python SKILL_DIR/scripts/ui_assets.py status --run RUN_DIR
python SKILL_DIR/scripts/ui_assets.py preview --run RUN_DIR
```

`status` 和 `preview` 默认 quick，仅核对素材结构与来源，不调用严格评分，也不写 `acceptance.json`。结构通过不证明外观一致，仍须看当前最终产物；Alpha 数值不能证明没有棋盘格、白边或裁断。完成必要检查后交付独立素材、位置层级清单和当前拼装/预览，简短说明已知差异。

明确要求严格评分时读取 [acceptance.md](references/acceptance.md)，使用 `verify` 或 `status --mode strict`；严格预览用 `preview --mode strict`。`pack` 保持严格门槛。普通首版打包方式见 [preview.md](references/preview.md)。

游戏实装还需按授权范围接入资源与交互，并完成必要编译和运行检查。运行环境不可用时明确哪些环节未验证，静态拼装不能冒充游戏实现。
