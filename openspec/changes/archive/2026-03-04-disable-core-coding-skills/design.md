## Context

项目正在从基于 skills 的架构迁移到基于 agents 的架构。在迁移期间，两套系统共存可能导致冲突。

## Goals / Non-Goals

**Goals:**
- Disable 5 个核心 coding agent skills
- 保持文件内容完整
- 记录变更历史

**Non-Goals:**
- 删除 skill 文件
- 修改其他 openspec skills

## Decisions

### Decision 1: 使用 name 前缀而非删除文件

选择添加 `disabled-` 前缀而非直接删除文件，原因：
- 保留历史记录
- 便于未来参考
- 可逆操作
