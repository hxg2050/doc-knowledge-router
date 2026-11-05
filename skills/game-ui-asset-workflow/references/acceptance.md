# 交付检查

## 默认：快速首版交付

完成当前范围的必要生成轮次、独立素材与首次拼装后，只做基础检查：文件可读、尺寸与 Alpha 可用、核心内容齐全、无妨碍使用的明显错误；需要网页时确认页面和关键图片能加载、主要操作可用。发现非阻断的外观与细节差异，简短告知后交付，不自动返修。

无需评分、逐区审核、`review.json`、`acceptance.json` 或 90 分结论。快速交付使用 `audit / inspect / compose / compare` 的结果，按需运行 `preview`。默认 preview / status 不调用严格审核，只显示素材状态与“未进行严格视觉验收”。

## 可选：用户明确要求的精修与严格评分

**以下评分与门槛仅在用户明确要求时启用，不适用于默认快速交付。**

90 分是附图像证据的视觉判断门槛，不能描述成客观测得的 90% 相似率。像素差异仅辅助定位；大面积背景相近不能替代按钮和文字的逐区检查。

## 先通过结构硬门槛

v2 的所有必需实例须属于完整视觉区域，关键实例须属于关键区域；快速任务升级为严格验收时先补齐 regions，再重做 compare 和审核。

必需素材与实际使用的素材全部通过文件、尺寸、Alpha、来源链和实例检查；所有必需项可重建，覆盖率为 100%。**结构完整不贡献视觉分**。数量分别报告美术、文字、简单几何和实例，避免用许多文字切片制造美术完成度。

v2 必须有当前透明素材的深浅底检查图，文件哈希和比较证据均未过期。逐项确认无假棋盘格、意外裁边或烘焙在背景里的重复物体。

## 视觉分与局部门槛

| 维度 | 权重 | 检查内容 |
|---|---:|---|
| `layout` | 35% | 位置、实际大小、间距、层级、锚点、文字基线和排版 |
| `appearance` | 45% | 人物身份、轮廓、形状、材质、颜色、风格和细节 |
| `edges` | 10% | 真透明、无白边/色边、细线与墨迹保留、无意外截断 |
| `assembly` | 10% | 可重建、补全与遮挡正确、无重复/缝隙，交付范围对应真实产物 |

各项用 0–100 **整数**，说明具体扣分与证据；总分加权后保守向下取整。v2 的四项与完整区域均须审核，关键区域各自 ≥90。外观维度独立 ≥90；不能用正确布局抵消明显错误的人物或按钮。

评分锚点：100＝已检查范围内无可见差异；90＝主要效果一致，仅少量不影响识别和使用的细节差异；75＝结构可辨但有显眼外观/尺寸偏差；50＝主要区域缺失或风格明显不符。不要未看图就统一填写 90。

完整区域例子：主按钮底板＋图标＋文字、整个顶部栏、完整人物与可见饰品。不要把一个错误组件拆成若干小素材平均计分。v1 继续审核关键素材的每个实例，新任务使用 v2 完整区域。

无未解决的 `critical` / `major` 问题才可通过。主按钮缺失、主角换人、顶部误删、面板错位、假透明、遮挡未补全、背景残留人物均属严重问题。

## 填审核与验证

```text
python SKILL_DIR/scripts/ui_assets.py inspect --run RUN_DIR
python SKILL_DIR/scripts/ui_assets.py compose --run RUN_DIR
python SKILL_DIR/scripts/ui_assets.py compare --run RUN_DIR
python SKILL_DIR/scripts/ui_assets.py review-template --run RUN_DIR
```

实际查看 `qa/side-by-side.png`、`overlay.png`、`difference.png`、`region-*.png` 和 `alpha/*.png`，再编辑 `qa/review-draft.json`，保存为 `qa/review.json`。草稿的分数为 null、检查项为 false，绝不会自动通过。

审核字段：

- `scoring_policy: "visual-v2"`。v1 旧评分也要重新审核，覆盖率不再获得旧版的 20 分。
- 保留草稿中当前 `reference_sha256`、`actual_sha256`、`state_sha256`、`evidence_sha256`。不要复制不对应当前文件的哈希，任意输入变化后重跑 compare 和审核。
- `criteria`：layout/appearance/edges/assembly，每项有 `score`、具体 `notes`、可查看的 `evidence` 图片列表。
- v2 `regions` 与清单区域一一对应，每项同样给分、说明和图片证据。`checks` 的四项仅在实际看图确认后置 true：`alpha_on_light_and_dark`、`no_baked_checkerboard`、`no_unintended_clipping`、`background_without_extracted_objects`。
- `issues` 记录问题、严重程度与状态，例如 `{"asset":"start-plate","severity":"major","status":"open","detail":"底板缺角，需返修补全"}`。已修复的项须实际复核后标 resolved。
- `delivery_scope`：`assets-preview` 或 `game-implementation`。后者必须比较真实运行截图，另填 `runtime_evidence` 的 `scene`、`capture_source`、`interactions`（已验证的交互列表）。脚本只能核对记录，不能证明截图来自运行中的游戏。

```text
python SKILL_DIR/scripts/ui_assets.py verify --run RUN_DIR
python SKILL_DIR/scripts/ui_assets.py status --run RUN_DIR --mode strict
```

`verify` 生成 `qa/acceptance.json`，失败返回非零并列出阻塞项；`status --mode strict` 复用同一次调用内的素材检查并核对当前证据，仅在当前审核通过时显示分数，否则显示 `assets-needed` 或 `review-needed`。它不能代替人或视觉模型看图。

返修后重跑受影响步骤，审核当前结果。已无新证据或可行改法、达到用户预算或工具不可用时保留中间成果、失败项与下一步，明确未达标；不虚报完成。
