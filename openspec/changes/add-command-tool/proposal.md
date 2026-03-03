# Proposal: Add Command Tool

## Summary

实现安全的命令执行工具，集成参考自 OpenCode、 Hello-Agents、 HelloAgents 的安全机制
支持黑名单/白名单/权限确认三层防护
以及 ToolFilter 机制控制子代理工具访问权限。

## Motivation

mini-coder 需要执行系统命令来查看目录、修改文件等但但这些操作有一定风险
需要实现多层安全防护机制：
参考 `docs/command-execution-security-design.md` 中的详细设计方案。

## Goals

1. 宛成安全的命令执行能力
2. 宛成黑名单/白名单/权限确认机制
3. 宛成 ToolFilter 机制与支持子代理隔离
4. 保障向后兼容性

## Approach

参考四个项目的最佳实践，- **OpenCode**: 三层防护 + 权限系统 + 持久 Shell
- **Hello-Agents**: 严格白名单 + 路径检查
- **HelloAgents**: ToolFilter 机制 + @tool_action 装饰器

## Scope

- 娡块范围: `src/mini_coder/tools/command.py`
- 工具类: `CommandTool`
- 过滤器: `ToolFilter`, `ReadOnlyFilter`, `FullAccessFilter`
- 配置: `config/tools.yaml`

## Dependencies

- 现有 LLMService
- 现有 ProjectNotesManager (笔记系统集成)

## Risisks

1. 建命令注入攻击
2. 危险命令执行导致系统损坏
3. 权限确认机制可能影响用户体验

## Success Criteria

- 所有测试通过
- 黑名单命令 100% 拒绝
- 白名单命令无需确认执行
- 危险命令需要用户确认
