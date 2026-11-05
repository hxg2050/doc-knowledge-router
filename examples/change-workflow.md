# Change Workflow Examples

## Keep A Small Change Lightweight

```text
使用 $change-workflow，把设置页两个按钮的文案改清楚，并同步对应说明。
这是小改动，不需要专门写计划文档。
```

预期：查看相关文件和已有差异，修改文案并检查显示或相关格式。不会仅因涉及多个文件而创建计划，也不会为文字替换新增测试。

## Fix A Bug With A Reproduction Test

```text
使用 $change-workflow 修复登录状态丢失的问题。先阅读项目规则和相关测试，补一个能复现问题的失败测试，再实现修复并运行最小相关验证。
```

预期：用户明确要求复现测试时执行该要求；验证对应行为，必要时检查相关边界。不能用“保持轻量”跳过真实行为缺陷的验证。

## Continue An Existing Plan

```text
Use $change-workflow to continue docs/plans/search-index.md. Check the latest requirements and working-tree changes, then continue from the existing progress and Resume Notes. Reuse verification results that still apply.
```

预期：能够继续读取旧计划的章节格式；先核对变化，不从头重做。代码或环境有变化、旧结果不清楚时再执行相关检查。

## Plan A Multi-Stage Feature

```text
使用 $change-workflow 增加导出 CSV 功能。请创建或更新 docs/plans/export-csv.md，记录决策、非目标、测试计划、验证命令和续作记录。
```

预期：用户明确要求计划文件时按指定位置和内容记录；复用已有计划，不机械生成第二份。

## Revise A Stale Plan

```text
使用 $change-workflow 继续导出功能。计划里原本只支持 CSV，现在我需要 CSV 和 JSON，
其他已确定行为继续保留。先完成共享导出逻辑，再分别验证两种格式。
```

预期：把最新用户要求纳入目标与决策，再推进实施，不让旧 `Decisions` 阻止已授权的范围调整。

## Preserve Existing Work

```text
使用 $change-workflow 修复搜索空结果的问题。工作区已有我修改的筛选样式，
可能和这次改动在同一个文件里，请保留；这次不用提交。
```

预期：按差异区分双方改动，保留样式和原有暂存状态，不清空工作区或无差别暂存。用户要求不提交时，交付可审阅的修改与验证结果。

## Report A Real Validation Limit

```text
使用 $change-workflow 修改数据库超时处理。当前没有集成测试数据库，
先完成能独立验证的部分，记录剩下需要的验证条件。
```

预期：完成能够进行的实现和检查，明确区分通过、未执行与环境阻塞。环境没有变化时，不反复重试同一条失败连接，也不声称集成测试通过。
