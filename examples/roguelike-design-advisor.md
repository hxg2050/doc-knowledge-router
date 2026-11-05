# Roguelike Design Advisor Examples

## 全被动游戏也能参考主动技能

```text
使用 $roguelike-design-advisor。我在做一个全被动攻击的 Roguelike，玩家只控制移动。
参考资料里的区域、位移或持续伤害机制，给我三个玩法不同的技能方向。
不要因为原始示例是主动释放就排除它。每个方向简单写核心效果、组成机制和可选触发方式即可。
```

合适的输出会保留可复用效果，提供自动触发思路，并解释走位等仍可产生的决策。不会新增主动按键，也不会直接展开大量数值字段。

## 从一个机制开始

```text
使用 $roguelike-design-advisor，基于“周期伤害”设计一个最简单的单机制技能，
再给一个改变玩法的组合变体。名字和元素主题可以换，不需要完整数值。
```

## 修改原有技能

```text
使用 $roguelike-design-advisor，把“霜蚀领域”改成适合自动战斗的版本。
保留区域、减速和周期伤害，触发方式只用一句话记录。
```

## 检查组合风险

```text
使用 $roguelike-design-advisor，检查“投射物命中后分裂，子弹命中又触发分裂”的设计。
指出最关键的问题，给两种保留连锁乐趣的限制方案，不要做完整系统审计。
```

## 在一般游戏中设计技能

```text
使用 $roguelike-design-advisor，为我的回合制小队游戏设计一个保护队友的技能。
参考机制即可，不需要把游戏改成 Roguelike；给一个基础版本和一个有代价的变体。
```

## 直接检索资料

在仓库根目录执行：

```bash
python skills/roguelike-design-advisor/scripts/query_library.py --query "位移" --limit 6
python skills/roguelike-design-advisor/scripts/query_library.py --tag "防御反应" --type 机制
python skills/roguelike-design-advisor/scripts/query_library.py --id atlas-s-frost-field --with-components --detail
python skills/roguelike-design-advisor/scripts/query_library.py --check
```

引用库含 48 个机制和 24 个技能草案。所有条目都未经游戏实测，原始参数不能当作已验证的平衡结果。资料是本 Skill 内的可移植副本，不会自动同步个人网页中的后续编辑。
