# 清单与像素契约

工具使用 Python 3.10+、Pillow 9.1+；不调用模型、API 或网络。优先用宿主已有运行环境。命令中的 `SKILL_DIR`、`RUN_DIR` 替换为实际绝对路径，路径含空格时加引号。

典型工作目录：

```text
RUN_DIR/
  plan.json
  reference/mockup.png
  annotations/all.png, r02.png
  prompts/r02.md
  generated/r02.png, r02-registered.png
  recipes/r02.json
  masks/background.png
  assets/*.png
  provenance/registration.json, extraction.json
  assembly/reconstructed.png
  qa/alpha/*.png
  qa/alpha-inspection.json, asset-audit.json, comparison.json
  qa/side-by-side.png, overlay.png, difference.png, region-*.png
  qa/review-draft.json, review.json, acceptance.json  # 仅明确要求严格评分验收时
  preview/                       # 按需
  delivery/assets.zip            # 按需
  history/                       # 替换前自动归档
```

新任务使用 `schema_version: 2`，版本号约束结构与来源，不代表启用严格评分。快速模式可省略下例的 `regions` 和可选细节；进入严格评分前补齐区域并重新生成比较证据。以下示例的所有轮次均使用原图分辨率，并展示严格区域：

```json
{
  "schema_version": 2,
  "reference": "reference/mockup.png",
  "canvas": [1280, 720],
  "rounds": [
    {"id": "r01", "raw_image": "generated/r01.png", "image": "generated/r01.png"},
    {"id": "r02", "raw_image": "generated/r02.png", "image": "generated/r02-registered.png", "recipe": "recipes/r02.json", "canvas": [1280, 720]}
  ],
  "assets": [
    {"id": "background", "kind": "background", "strategy": "complete-occlusion",
     "required": true, "critical": true, "alpha": "opaque", "size": [1280, 720],
     "round": "r01", "sheet_box": [0, 0, 1280, 720], "file": "assets/background.png"},
    {"id": "start-plate", "kind": "button", "strategy": "remove-text",
     "required": true, "critical": true, "alpha": "transparent", "size": [240, 72],
     "round": "r02", "sheet_box": [520, 600, 240, 72], "visible_box": [520, 600, 240, 60],
     "pivot": [120, 36], "padding": [4, 4, 4, 4], "file": "assets/start-plate.png"},
    {"id": "start-label", "kind": "text", "strategy": "local",
     "required": true, "critical": true, "alpha": "transparent", "size": [120, 40],
     "round": null, "file": "assets/start-label.png", "text": "开始游戏",
     "text_style": {"font": "fonts/ui.ttf", "size": 28, "baseline": 31, "color": "#eee8dc", "align": "center"},
     "source_files": ["build_text.py", "fonts/ui.ttf"], "source_note": "用声明的字体与参数排版为独立透明文字层"}
  ],
  "instances": [
    {"id": "background-main", "asset": "background", "xy": [0, 0], "z": 0},
    {"id": "start-main", "asset": "start-plate", "xy": [520, 600], "z": 10},
    {"id": "start-label-main", "asset": "start-label", "xy": [580, 616], "z": 11}
  ],
  "regions": [
    {"id": "environment", "box": [0, 0, 1280, 720], "instances": ["background-main"], "critical": true},
    {"id": "main-action", "box": [510, 590, 260, 92], "instances": ["start-main", "start-label-main"], "critical": true}
  ]
}
```

## 字段约定

- 所有路径均相对任务目录，外部图片、字体和处理脚本先复制进来，保证可搬移。ID 用小写英文、数字、连字符或下划线，且各自列表内唯一。
- 所有矩形是 `[x, y, width, height]`，不是 Pillow 的左右边界格式。最终布局坐标属于 `plan.canvas`；`sheet_box` 和 recipe 的目标坐标属于对应轮次画布。两者均使用原图分辨率和左上角原点；轮次排布与最终实例位置分别记录。
- `rounds[].canvas` 可选，为正整数 `[width, height]`，省略时继承 `plan.canvas`，显式填写必须与之完全相等。所有大小素材都使用原图同尺寸的标准化画布和标注图，不使用局部或扩大画布。生成时请求同样分辨率；模型实际返回尺寸不一致时，保留原始结果并校正到原图尺寸，不修改此契约。
- `sheet_box` 是完整素材在**标准化轮次画布**中的裁切框，必须在画布内，含留边；`size` 必须等于其宽高。同轮框不得重叠，复用素材只生成一次。
- `visible_box` 可选，描述原稿可见部分；不能代替补全后的完整框。`padding` 可选，顺序为左、上、右、下。
- `instances[].xy` 永远是导出矩形的左上角，按 1:1 尺寸和 `z` 升序绘制；相同 `z` 保持清单顺序。实例可部分超出画布，不能完全不可见。
- `pivot` 可选，是引擎集成用的素材内像素锚点。静态拼装仍按 `xy`；引擎使用 pivot 时自行换算节点位置，不要重复扣除锚点。
- 每个必需素材必须有实例。快速模式可不填 `regions`；一旦填写，区域必须覆盖其声明实例在最终画布内的完整范围。严格评分要求所有必需实例至少属于一个区域，所有关键实例至少属于一个关键区域；进入严格流程时由 review-template / verify 检查。区域按完整组件划分，不要只用全屏区域掩盖局部问题。
- `text_style` 的字体、字号、素材内基线为 v2 文字层必填；颜色、对齐、字距、阴影等按原稿实际记录。区分静态文案与运行时动态值，文字不能重复烘焙在底板里。

## 复用检索记录

在任务目录保存 `reuse-check.json`，逐项关联 `plan.json` 的素材 ID。每项至少记录 `asset`、`decision`、`selected_source`（没有则 null）和简短 `reason`。按实际检索补充 `searched_scopes`、`queries`、`candidates`，复用已有记录即可。decision 取 `reuse`、`process-existing`、`new-production` 或 `unresolved`；新制作再标 `reason_kind` 为 `missing-layer`、`unsuitable-source` 或 `requested-redesign`。候选保留路径和实际查看结论；缺失记录搜索范围，不用“文件名无匹配”作为唯一依据。旧记录的 `missing` 按 `new-production` + `missing-layer` 理解，无需批量改写。

直接复用仍使用 `strategy: "crop"`，把源图复制到任务目录后填写 `source.file`、`source.box`，在 `source_note` 保留原项目路径和选用理由。需要等比校正等本地处理时保留原文件、参数和处理脚本，通过 `source_files` 追踪，再以实际处理产物作为裁切来源；不要伪造生图轮次。文字与简单几何继续使用 `local`。

生成轮只包含需要新制作的项；`unresolved` 先补查，`process-existing` 先评估合理处理。已有素材即使尺寸可调，也可能因风格、轮廓、分辨率或缺少完整层而不适用：记录具体原因，按已授权的设计目标转入 `new-production`，无需再次请求已有授权。不把不适用候选伪称为缺失。这个记录辅助执行判断，脚本不自动核验其语义。

## 获取方式与 Alpha

| `strategy` | 使用条件 | 来源要求 |
|---|---|---|
| `generate` | 取得缺少或无法适配的独立美术层，或执行已授权重设计／替换 | round、提示词、原始生图 |
| `remove-text` | 取得无字底板或图标 | 同上，保留结构和细节 |
| `complete-occlusion` | 补出遮挡下的物体/环境 | 同上，说明遮挡和要补全的范围 |
| `crop` | 已有项目素材或原稿已完整、可直接使用，无需去背景/补绘 | round 为 null，source.file、source.box、source_note |
| `local` | 文字或简单几何 | round 为 null，kind 为 text/geometry，source_note；source_files 记录可用的字体/构建脚本 |

直接裁切示例：

```json
{"id":"isolated-icon","kind":"icon","strategy":"crop","required":true,
 "alpha":"transparent","size":[48,48],"round":null,"file":"assets/isolated-icon.png",
 "source":{"file":"reference/isolated-original.png","box":[12,20,48,48]},
 "source_note":"来源本身已有透明背景，图标完整且没有文字和遮挡"}
```

裁切不会自动去背景。Alpha 取值：`opaque` 必须全不透明；`transparent` 用于有透明周边的独立物体；`translucent` 用于有意覆盖整块区域的半透明矩形层。后两种不能用来掩盖假棋盘格或错误底色。

默认有效内容统计阈值为 Alpha ≥16，仅用于测量，**不修改像素**。极淡但有意保留的素材可设 `alpha_analysis.visible_threshold`，须在 `source_note` 中说明；不要为了通过检查压低阈值。`allow_edge_touch: true` 仅用于有意贴边的素材，仍需查看截断情况。

## 版本与兼容

原始结果满足尺寸与布局时 `raw_image`、`image` 可相同；校正后必须分开并声明 `recipe`。各轮保存 `prompts/ROUND.md`。代码会追踪原图、提示词、recipe、蒙版、独立图和 `source_files` 的哈希；`status` 定位受影响素材，不能继续显示旧版已验收分数。

快速模式保留结构与来源字段，哈希由 register / extract 自动记录；不要求评分审核文件。`status` / `preview` 默认 quick，严格状态须显式 `--mode strict`；`verify` / `pack` 始终严格。旧命令若依赖 status 的评分字段，需追加 `--mode strict`。

v1 清单仍可读取、切图、拼装。所有版本的轮次画布均须等于原图尺寸；旧清单若使用其他尺寸，先更新画布、裁框和对应素材图。其来源规则维持兼容；仅在用户明确要求严格评分验收时，关键项沿用实例审核，原评分需按 `visual-v2` 重审。新任务不要继续产生 v1 清单。
