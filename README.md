# Doc Knowledge Router

面向 Codex、Claude Code、Cursor 等 agent 的文档知识路由 skill。它把项目文档当成图书馆来整理：入口、目录、索引、查找路径、权威归属和归档位置，而不是替业务文档写正文结论。

## Installing

安装整个仓库：

```bash
npx skills add https://github.com/hxg2050/doc-knowledge-router
```

只安装指定 skill：

```bash
npx skills add https://github.com/hxg2050/doc-knowledge-router --skill "doc-knowledge-router"
npx skills add https://github.com/hxg2050/doc-knowledge-router --skill "change-workflow"
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
| `change-workflow` | `change-workflow` | 执行仓库变更时保持计划、测试、验证、续作记录和提交边界 | draft |

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

更多示例见 [examples/doc-knowledge-router.md](examples/doc-knowledge-router.md) 和 [examples/change-workflow.md](examples/change-workflow.md)。

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
```

## Contributing

贡献新 skill 前先读 [CONTRIBUTING.md](CONTRIBUTING.md)。新增或修改 skill 后必须运行：

```bash
node scripts/validate-skills.mjs
```

## License

[MIT](LICENSE)
