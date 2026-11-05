# Doc Knowledge Router

面向 Codex、Claude Code、Cursor 等 agent 的文档知识路由 skill。它把项目文档当成图书馆来整理：入口、目录、索引、查找路径、权威归属和归档位置，而不是替业务文档写正文结论。

仓库也提供独立的变更工作流、Roguelike 机制／技能设计顾问与游戏界面素材工作流，可按需单独安装。

## Installing

安装整个仓库：

```bash
npx skills add https://github.com/hxg2050/doc-knowledge-router
```

只安装指定 skill：

```bash
npx skills add https://github.com/hxg2050/doc-knowledge-router --skill "doc-knowledge-router"
npx skills add https://github.com/hxg2050/doc-knowledge-router --skill "change-workflow"
npx skills add https://github.com/hxg2050/doc-knowledge-router --skill "roguelike-design-advisor"
npx skills add https://github.com/hxg2050/doc-knowledge-router --skill "game-ui-asset-workflow"
```

也可以手动复制：

```bash
mkdir -p ~/.codex/skills
cp -R skills/doc-knowledge-router ~/.codex/skills/
```

## Skills

| Folder | Install name | Description | Status |
| --- | --- | --- | --- |
| `doc-knowledge-router` | `doc-knowledge-router` | 管理项目文档的位置、分类、入口、索引、查找路径和权威归属 | stable |
| `change-workflow` | `change-workflow` | 按风险推进变更，选择合适的计划与验证，保护已有工作和续作上下文 | draft |
| `roguelike-design-advisor` | `roguelike-design-advisor` | 参考 48 个机制与 24 个技能草案，提供游戏设计方向、组合建议与触发方式变体 | draft |
| `game-ui-asset-workflow` | `game-ui-asset-workflow` | 优先复用游戏界面素材，按需拆材、补绘、拼装和预览，支持局部修改与严格验收 | draft |

## Usage

在 Codex 中可以直接说：

```text
Use $doc-knowledge-router to organize the docs directory and create a clear docs/index.md entry point.
```

中文示例：

```text
使用 $doc-knowledge-router 整理 docs 目录，建立总入口、工作流入口和归档规则。
```

变更工作流示例：

```text
使用 $change-workflow 修复这个 bug，先补复现测试，再实现并运行相关验证。
```

游戏设计示例：

```text
使用 $roguelike-design-advisor，为全被动攻击的 Roguelike 设计三个玩法不同的技能方向。
参考核心机制即可，触发方式可以改，不需要详细数值。
```

游戏界面素材示例：

```text
使用 $game-ui-asset-workflow，把这张游戏主页效果图拆成独立素材。
优先复用项目已有资源，补齐缺少的图层，提供可浏览的拼装预览，先交付可用首版。
```

更多示例见 [文档路由](examples/doc-knowledge-router.md)、[变更工作流](examples/change-workflow.md)、[Roguelike 设计](examples/roguelike-design-advisor.md) 和 [游戏界面素材](examples/game-ui-asset-workflow.md)。

## Repository Layout

```text
skills/
  change-workflow/
    SKILL.md
    agents/openai.yaml
    references/plan-template.md
  doc-knowledge-router/
    SKILL.md
    agents/openai.yaml
  roguelike-design-advisor/
    SKILL.md
    agents/openai.yaml
    references/index.md
    references/design-guidance.md
    references/library.json
    scripts/query_library.py
  game-ui-asset-workflow/
    SKILL.md
    agents/openai.yaml
    references/
    scripts/
    assets/preview/
  llms.txt
examples/
scripts/
  validate-skills.mjs
.github/workflows/
  validate.yml
```

`skills/` 是 agent skill 的安装入口。根目录文档服务于人类读者和开源协作，不应该替代 `SKILL.md`。

## Quality Rules

- 每个 skill 必须位于 `skills/<skill-name>/`。
- 每个 skill 必须包含 `SKILL.md`。
- `SKILL.md` frontmatter 只允许 `name` 和 `description`。
- `name` 使用 lowercase-hyphen 命名，并且与目录名一致。
- 每个 skill 应包含 `agents/openai.yaml`。
- `skills/llms.txt` 必须列出每个 skill。
- skill 目录内不要放面向人的 `README.md`、`CHANGELOG.md` 或安装说明。

运行校验：

```bash
node scripts/validate-skills.mjs
python skills/roguelike-design-advisor/scripts/query_library.py --check
python -B -m unittest discover -s skills/game-ui-asset-workflow/scripts
```

游戏界面素材脚本需要 Python 3.10+ 和 Pillow 9.1+（可用 `python -m pip install "Pillow>=9.1"` 安装）。测试使用本地合成素材，不调用生图服务；实际生图需要宿主提供相应工具。

## Contributing

贡献新 skill 前先读 [CONTRIBUTING.md](CONTRIBUTING.md)。新增或修改 skill 后必须运行：

```bash
node scripts/validate-skills.mjs
```

## License

[MIT](LICENSE)
