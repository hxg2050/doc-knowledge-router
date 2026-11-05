# 本地校正与切图

固定最终界面和素材尺寸，标准化画布使用 `rounds[].canvas`（省略则继承 `plan.canvas`），分别保存原始返回图、标准化画布和独立 PNG。先测量再处理，不相信提示词会精确约束像素。所有矩形都是 `[x,y,width,height]`。

```text
python SKILL_DIR/scripts/ui_assets.py inspect --run RUN_DIR --image generated/r02.png
python SKILL_DIR/scripts/ui_assets.py register --run RUN_DIR --round r02
python SKILL_DIR/scripts/ui_assets.py extract --run RUN_DIR --round r02
```

`rounds[].raw_image` 指向未修改的原始生图，`image` 指向标准化画布，`recipe` 指向以下 JSON。每个活跃轮次素材恰好一个 operation；来源裁切不得越界，注册后可见内容必须留在计划的 `sheet_box` 内。

## 等比缩放与平移

测量物体的完整来源框，包含细节和透明留边。默认 `place` 将来源框等比缩放、居中放进 `target_box`（省略时使用素材的 `sheet_box`），不拉伸比例：

```json
{"operations":[
  {"asset":"hero","type":"place","source":"generated/r02.png",
   "source_box":[120,60,600,650],"target_box":[160,100,480,520]}
]}
```

比例偏差是物体自身的问题时，不用 `contain` 留出的空白隐藏错误造型。快速模式下不影响独立使用的偏差先记录，阻断使用或用户要求修改时才补生成。需要按可识别特征定位时，用至少两对实际测量点替换 `target_box`；推荐 3–5 对，覆盖不同方向：

```json
{"asset":"hero","type":"place","source":"generated/r02.png",
 "source_box":[120,60,600,650],"max_error_px":2,
 "landmarks":[
   {"source":[200,100],"target":[224,132]},
   {"source":[700,650],"target":[624,572]},
   {"source":[300,600],"target":[304,532]}
 ]}
```

来源点坐标相对于原始输入图，目标点坐标相对于轮次标准画布；不能混用最终界面坐标。工具只拟合一个等比缩放与平移；不能在误差超标时改用非等比缩放。画布差 1px 但物体尺寸正确时，可按实测来源框原比例平移入标准画布，无需拉伸整张图。

## 九宫格 UI 底板

仅适合允许伸缩的按钮、面板与简单几何；人物、图标、文字和不可拉伸装饰禁止使用。`borders` 是来源裁片的左、上、右、下边距，先按 `uniform_scale` 等比缩放，再延展中心与边段；角保持该比例。目标不能挤坏边角。

```json
{"operations":[
  {"asset":"start-plate","type":"nine-slice","source":"generated/r06.png",
   "source_box":[400,300,340,100],"target_box":[520,600,240,72],
   "borders":[24,16,24,16],"uniform_scale":0.72}
]}
```

图案重心、纹理或边框不适合延展时不用九宫格掩盖；导致无法使用才补生成，否则记录差异随首版交付。九宫格是尺寸适配方法，不代表外观已通过严格审核。

## 背景蒙版补绘

原稿可见区域是 `base`，模型生成的补全图是 `source`，真实灰度蒙版 `mask` 中白色取补全图、黑色保留原稿；三者均与本轮标准画布同尺寸。整屏背景轮通常继承最终画布；使用局部背景轮时，base 和 mask 也必须先明确裁到该轮坐标空间。覆盖所有已提取物体及其阴影，避免残影与重复人物。

```json
{"operations":[
  {"asset":"background","type":"inpaint","source":"generated/r01.png",
   "base":"reference/mockup.png","mask":"masks/background.png","feather":2}
]}
```

`feather` 为模糊半径（默认 0），会扩展混合范围，需实际看边界。不把透明 PNG 当灰度蒙版。模型补绘图尺寸不同则先保存一份经检查的等比校正版，作为 operation 的 source；保留 raw_image 原文件。不能偷偷拉伸。

## 切图、Alpha 与失效处理

`extract --round` 从标准画布切整轮素材；`extract --asset ID` 按 `source.box` 直接裁原稿。默认不改输出尺寸、留白和锚点。v1 已确认同宽高比的整张素材图可以显式 `--normalize-size`，结果记录在切图来源里；v2 要求输入匹配轮次标准画布；只有尺寸或布局不匹配时才用 recipe 注册后再切图。原始结果已匹配时可直接切。

```text
python SKILL_DIR/scripts/ui_assets.py inspect --run RUN_DIR
python SKILL_DIR/scripts/ui_assets.py audit --run RUN_DIR
```

`inspect` 保存 `qa/alpha/ID.png`：左浅底、右深底，保留素材原始 Alpha。统计只能发现空图、近乎不透明矩形、可疑裁边等，不能自动证明没有假棋盘格、杂点和白边。Alpha 阈值仅用于测量，不用于修改图片。

`register` 记录输入哈希、实际变换、残差及最终画布；`extract` 记录裁框和完整来源链。局部变化仅重跑受影响项必要的 register / extract，更新当前最终拼装或已生成的 preview。尺寸、Alpha 等已有有效检查结果直接复用；需要重新 inspect 或 compare 时并入首版的一轮最小检查，不每改一项就重跑整条检查链。位置或布局变化应更新对应产物，仅在需要定位差异时重新生成比较图。

只有用户明确要求严格评分验收时，才追加 review → verify，或使用 `status --mode strict` 查看严格审核状态；快速首版不受这些命令的 90 分门槛限制。

默认拒绝覆盖已有输出。`--replace` 将旧输出与来源记录归档到 `history/`，不会覆盖原始生成输入；也可使用新轮次/文件名。不要为一个失败项重做全套已合格素材。
