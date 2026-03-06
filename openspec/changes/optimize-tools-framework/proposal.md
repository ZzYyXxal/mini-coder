# Change Proposal: Optimize Tools Framework

## Change Information

- **Change ID**: `optimize-tools-framework`
- **Created**: 2026-03-06
- **Status**: Proposed
- **Priority**: High
- **Estimated Complexity**: Medium

## Summary

优化 mini-coder 的 Tools 框架，参考 Agent 架构实现"代码框架 + 动态提示词"方法，将工具的配置与代码分离，提升可维护性和可扩展性。

## Motivation

当前 Tools 架构存在以下问题：

1. **提示词硬编码** - Tool 的描述和使用说明硬编码在代码中，修改需要重新编译
2. **缺少事件回调** - TUI 无法实时显示工具执行进度
3. **配置不灵活** - 工具行为配置分散，缺乏统一管理
4. **架构不一致** - 与 Agent 的"代码框架 + 动态提示词"模式不统一

通过分析发现：
- **Memory 系统应该保持独立** - 它是基础设施，不是 LLM 调用的工具
- **Command Tool 需要优化** - 添加动态提示词和事件回调支持
- **需要统一的 BaseTool 框架** - 参考 Agent 架构，支持 prompt_loader

## Goals

1. ✅ **保留 Memory 作为独立子系统** - 不是 Tool，是基础设施
2. ✅ **保留并优化 Command Tool** - 添加动态提示词、事件回调
3. ✅ **创建新的 BaseTool 框架** - 参考 Agent 架构，支持 prompt_loader
4. ✅ **配置与代码分离** - tools.yaml 存储配置，prompts/*.md 存储提示词

## Non-Goals

- 不改变 Memory 系统的架构定位
- 不破坏现有 Tool 接口的向后兼容性
- 不修改 Agent 调用 Tool 的基本流程

## Scope

### In Scope

- `src/mini_coder/tools/base.py` - 创建 BaseTool 2.0
- `src/mini_coder/tools/command.py` - 迁移到 BaseTool 2.0
- `prompts/tools/command.md` - 创建 Command Tool 提示词模板
- `config/tools.yaml` - 更新工具配置
- `src/mini_coder/tools/prompt_loader.py` - PromptLoader 实现

### Out of Scope

- Memory 系统重构（保持独立）
- 其他内置工具的迁移（后续迭代）
- ToolFilter 架构变更（保持兼容）

## Success Criteria

1. **功能完整性**
   - [ ] BaseTool 2.0 框架正常工作
   - [ ] CommandTool 成功迁移到新架构
   - [ ] 动态提示词加载正常
   - [ ] 事件回调触发正确

2. **向后兼容性**
   - [ ] 现有 Tool 接口保持兼容
   - [ ] 现有 Agent 调用代码无需修改
   - [ ] 单元测试全部通过

3. **文档完整性**
   - [ ] 架构设计文档完成
   - [ ] 迁移指南完成
   - [ ] API 文档更新

## Dependencies

- 无外部依赖
- 依赖现有 PromptLoader（Agent 架构已有）
- 依赖现有 ToolFilter 架构

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| 向后兼容性破坏 | High | Low | 保留旧接口，逐步迁移 |
| 提示词文件缺失 | Medium | Medium | 提供内置兜底提示词 |
| 事件回调性能开销 | Low | Low | 异步回调，可选启用 |

## References

- [Tools Architecture Design](../../docs/tools-architecture-design.md)
- [Multi-Agent Architecture Design](../../docs/multi-agent-architecture-design.md)
- [Command Execution Security Design](../../docs/command-execution-security-design.md)
