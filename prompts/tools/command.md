# Command 工具

**职责**：在受控策略下执行系统命令，返回标准输出、退出码与执行时间；不解析业务逻辑，仅做执行与安全校验。

**使用场景**：需要执行测试、类型检查、只读查看、经确认的安装/提交等命令时；由 Bash 子代理或主控逻辑调用。
**无法使用场景**：不执行黑名单命令（如 rm -rf、sudo、curl|bash、dd、mkfs、chmod 777 等）；在 strict 模式下不执行非白名单命令；不替代业务逻辑做“该不该执行”的决策（由调用方决定）。

---

## 安全策略

- **黑名单（一律拒绝）**：rm -rf、curl|bash、wget 管道执行、sudo、chmod 777、dd、mkfs 等。
- **白名单（直接执行）**：ls、pwd、cat、head、tail、wc、find；git status/log/diff/branch/remote；python --version、pytest --collect-only、mypy --version；cd、tree。
- **需确认**：mkdir、cp、mv、rm（非破坏性）、git add/commit/push/pull、pip install、npm install、make、npm run build 等。

当前模式：`{{security_mode}}`（strict | normal | trust）。超时：`{{timeout}}` s，最大输出：`{{max_output_length}}` 字符，允许路径：`{{allowed_paths}}`。

---

## 结构化输出（必须遵守）

每次调用仅返回以下结构（由工具实现保证，提示词仅约定语义）：

```
stdout: <标准输出内容，过长则截断>
stderr: <标准错误，无则空>
exit_code: <整数退出码>
execution_time_ms: <毫秒数>
```

若被拒绝或需确认未通过，则通过 error 事件或约定字段返回原因，不返回上述执行结果。
