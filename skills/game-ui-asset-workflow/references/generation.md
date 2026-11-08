# 原图尺寸画布与分轮生图

默认快速模式：只完成首版必需的取材轮次，生成返回后及时校正、切图和拼装；不为墨色、纹理或轻微形状差异追加精修轮。首版可用后的修改由用户提出。

先核对 `reuse-check.json`：本轮每项都应需要新制作：缺少独立层、已有候选无法合理适配，或用户已授权重设计／替换。已有可复用项不随缺失项重复生成，未确认项先继续检索；没有需生成项就跳过此阶段。

再查看基准图、标注图和必要局部，明确各自角色；提示词保存到 `prompts/ROUND.md`，同时记录输入文件、生成工具、实际返回尺寸与返修目的。使用内置生图，透明轮次设置 `transparent_background: true`，原始结果复制为 `generated/ROUND.png`。不虚构尺寸等工具参数。

完整原稿可直接裁切的素材先保留，不为统一走生图而重绘。去文字与补遮挡轮明确只修指定部分；复杂素材仍由生图取得，不能用脚本重画风格化美术冒充提取。

读取原图实际尺寸 W×H，所有轮次标准画布和标注图统一使用 W×H，无论素材大小；`rounds[].canvas` 如填写必须等于 `plan.canvas`。整体图约束外观和原稿像素比例，轮次标注图标出要提取素材的完整裁框与留边。不要为小图标缩小画布，也不要为大人物扩大画布或改变素材比例；最终位置仍来自 instances。

按实际清单改写提示词：

```text
Task: separate the specified game UI assets from the selected screen reference.
Image 1 is the visual reference: preserve style, shapes, materials, colors,
perspective, proportions and visible detail. Image 2 is a coordinate guide on
one W by H asset-sheet canvas with exactly the same pixel dimensions as Image 1.
Its rectangles and labels are annotations only; final screen positions are recorded separately.

Output a W by H RGBA canvas with a truly transparent background, regardless of asset size.
Include ONLY these complete assets at their planned pixel bounds:
- ASSET_ID: x=X, y=Y, width=WIDTH, height=HEIGHT; appearance; hidden parts to restore.

Use the planned asset-sheet scale and positions, including padding. Do not center,
enlarge, repack, duplicate, merge or overlap assets. Complete occluded parts
consistently with the visible reference. Leave other areas transparent.
Exclude occluders, unrelated scenery, coordinate guides, labels, dimensions,
dynamic text, color swatches, white backdrops and painted checkerboards.
This is a reusable asset pass. Preserve the chosen design.
```

同轮有接触或叠加就拆轮；人物、背景、UI 底板和文字分离。去文字不移除按钮本体或顶部栏；“删游戏名”之类的局部要求必须写出保留区域，避免顺带丢失整块界面。

## 背景轮

先检查项目是否已有可用的干净背景；确需补绘时才单独生成背景轮，移除已拆出的 UI、人物和前景并补齐环境，保持建筑、地平线、透视和墨色。不要在背景和人物层重复保留人物。

尽量只补被遮挡区。先生成补全候选，再用灰度蒙版与原稿可见区域融合（见 [processing.md](processing.md)），保留已确认的可见细节。视角/环境完全漂移以致无法使用时才补生成；可用的细节差异留待反馈。底图本身可以不透明；前景/远景分层的空隙需要真实 Alpha。

## 生成后必查

1. 检查实际尺寸、Alpha 和数量。完全不透明的白底/棋盘格不是透明输出；不能靠文件扩展名推断。
2. 测量每个物体实际范围。模型可能返回差 1px 的画布、把人物放大或把按钮移位，不直接按固定网格硬切。
3. 原始结果保持不动；需要时建立 recipe，本地等比校正到原图 W×H 标准画布。不能按模型返回尺寸改小或扩大轮次画布。人物和图标不做非等比缩放；九宫格仅限适用的 UI 底板。
4. 轮廓/比例偏差记录为已知差异，不靠改清单或粗阈值掩饰；隐藏部分缺失、多个对象粘连或 Alpha 错误等导致无法独立使用时，才重做相关素材。
5. 查看深浅底上的细线、墨迹、发丝与半透明边缘。发现意外截断先扩大来源裁切，再调整注册；留边变化须同步坐标和审核区域。

棋盘格只作查看器背景，不写进素材。生成与校正细节见 [processing.md](processing.md)。
