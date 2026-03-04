## Why

项目中同时存在两套 agent 定义：`.claude/skills/` 目录下的 skills 和 `.claude/agents/` 目录下的 agents。为避免冲突并统一使用新的 agents 定义，需要 disable 旧的 skills。

## What Changes

- 修改 5 个 skill 文件的 `name` 字段，添加 `disabled-` 前缀
- 使其无法被 Claude Code 正常调用
- 保留文件内容以便未来参考

## Capabilities

### New Capabilities
- `skill-disabling`: 通过修改 name 字段 disable 不再使用的 skills

### Modified Capabilities
<!-- 无修改的现有 capabilities -->

## Impact

- `.claude/skills/orchestrator/SKILL.md`: name → `disabled-orchestrator`
- `.claude/skills/architectural-consultant/SKILL.md`: name → `disabled-architectural-consultant`
- `.claude/skills/planner/SKILL.md`: name → `disabled-planner`
- `.claude/skills/implementer/SKILL.md`: name → `disabled-implementer`
- `.claude/skills/tester/SKILL.md`: name → `disabled-tester`
