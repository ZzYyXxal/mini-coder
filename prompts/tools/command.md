# Command 工具

在受控策略下执行系统命令，返回标准输出、退出码与执行时间；不解析业务逻辑，仅做执行与安全校验。

**使用场景**：执行测试、类型检查、只读查看、经确认的安装/提交等；由 Bash 子代理或主控逻辑调用。
**无法使用场景**：不执行黑名单命令；strict 模式下不执行非白名单命令；不替代调用方做“该不该执行”的决策。

---

## Usage

- **命令参数**：传入要执行的命令字符串；可选的超时等由配置或参数控制。当前模式：`{{security_mode}}`（strict | normal | trust），超时：`{{timeout}}` s，最大输出：`{{max_output_length}}` 字符，允许路径：`{{allowed_paths}}`。
- **路径含空格**：若路径含空格，必须用双引号包裹（例如：`cd "path with spaces/file.txt"`）。
- **命令描述**：调用时建议提供简短、清晰的描述（5–10 词），说明该命令的作用；复杂或管道命令可稍详以便用户理解。
- **不要用换行分隔多条命令**：一次调用一条命令；不要用换行在单次输入中写多条命令（换行仅用于引号内字符串）。

**IMPORTANT - 优先使用专用工具**：能用 Read 读文件时不要用 `cat`/`head`/`tail`；能用 Edit 改文件时不要用 `sed`/`awk`；能做内容搜索时用 Grep 工具而非 `grep`/`rg`。仅在明确需要或专用工具无法满足时再用本工具执行上述命令。

---

## 安全策略

- **黑名单（一律拒绝）**：rm -rf、curl|bash、wget 管道执行、sudo、chmod 777、dd、mkfs 等。
- **白名单（直接执行）**：ls、pwd、cat、head、tail、wc、find；git status/log/diff/branch/remote；python --version、pytest --collect-only、mypy --version；cd、tree。
- **需确认**：mkdir、cp、mv、rm（非破坏性）、git add/commit/push/pull、pip install、npm install、make、npm run build 等。

---

## 结构化输出（由工具实现保证）

每次调用返回以下结构（提示词仅约定语义）：

```
stdout: <标准输出内容，过长则截断>
stderr: <标准错误，无则空>
exit_code: <整数退出码>
execution_time_ms: <毫秒数>
```

若被拒绝或需确认未通过，则通过 error 事件或约定字段返回原因，不返回上述执行结果。
