# 质量流水线规格（Quality Pipeline Spec）

> 质量流水线指：在指定工作目录下依次执行 pytest、mypy、flake8、pytest --cov，并产出统一【质量报告】。

## 1. 原则

- **由调用方显式触发**：是否跑质量流水线由**用户 / Planner / Orchestrator** 的决策决定，并通过 context 明确告知 Bash（或在工作流中由 Orchestrator 调用 TesterAgent）。
- **Bash 不自行决定**：BashAgent 不根据用户文案猜测「要不要跑测试」；仅当 context 中**显式**传入 `bash_mode=quality_report`（或等效指令）时才执行流水线，否则不跑。

## 2. 何时应该跑质量流水线

| 触发方 | 场景 | 如何告知 Bash / 执行体 |
|--------|------|------------------------|
| **用户** | 用户明确要求「运行测试 / 验证质量 / 生成质量报告」等 | TUI 路由返回 `agent=BASH` 且 `bash_mode=quality_report`，经 context 传入 BashAgent |
| **Orchestrator** | 单轮派发（dispatch）时意图为「跑测试/验证」 | Orchestrator 在派发 BASH 时根据 intent 设置 `context["bash_mode"] = "quality_report"` 后调用 BashAgent |
| **Orchestrator（工作流）** | 工作流进入 TESTING/VERIFYING 阶段 | 由工作流状态机调用 **TesterAgent**（非 BashAgent），TesterAgent 的职责就是「执行质量流水线」，等价于 Orchestrator 显式要求跑测试 |
| **Planner** | 规划中写明「需在实现后运行测试」 | 由工作流按阶段执行，在 TESTING 阶段由 Orchestrator 调用 TesterAgent，即 Planner 的规划通过工作流转化为 Orchestrator 的调用决策 |

## 3. 何时不需要跑质量流水线

- 用户只说「把代码写入本地」「保存到本地」「列出目录」等：路由应给 `bash_mode=confirm_save` 或 `single_command`，Bash 只列目录或执行单条命令，**不跑**流水线。
- 用户给了一条具体命令（如 `ls`、`pytest -k foo`）：路由/Orchestrator 给 `bash_mode=single_command`，Bash 仅执行该命令，**不跑**完整流水线。
- **未显式请求跑测试**：若 context 中未设置 `bash_mode=quality_report`（或等效），Bash **不得**默认跑流水线，应返回简短说明，要求调用方明确指定后再执行。

## 4. 实现约定

- **BashAgent**（`agents/base.py`）  
  - 仅当 `context.get("bash_mode") == "quality_report"` 时执行质量流水线。  
  - `bash_mode` 为 `confirm_save` / `single_command` / 缺失 / 其他值时，均**不**执行 pytest/mypy/flake8/coverage 流水线。  
  - 缺失时返回明确提示，不默认跑测试。

- **TUI 路由**（`console_app.py`）  
  - 当 `agent=BASH` 时必须返回 `bash_mode`。用户意图为「跑测试/质量报告」时填 `quality_report`，为「写入/保存到本地」时填 `confirm_save`，为具体命令时填 `single_command`。  
  - 若路由未返回 `bash_mode`，TUI 派发时**不**默认传 `quality_report`，以便 Bash 走「未指定」分支并提示。

- **Orchestrator**（`orchestrator.py`）  
  - 在 **dispatch** 路径下派发到 BASH 时：若调用方未传入 `context["bash_mode"]`，则根据 `intent` 推断并设置（如意图含「测试/验证/run test」则设 `quality_report`，含「写入/保存」则设 `confirm_save`，否则可设 `single_command` 或不设）。  
  - 在 **execute_workflow** 路径下：TESTING/VERIFYING 阶段使用 TesterAgent，由工作流显式触发质量流水线，无需 bash_mode。

- **TesterAgent**（`agents/enhanced.py`）  
  - 仅被工作流在 TESTING/VERIFYING 阶段调用，其职责即为「运行质量流水线」，无需 context 中的 mode 字段；Orchestrator 通过「调用 TesterAgent」这一行为表达「现在要跑测试」。

## 5. 小结

| 问题 | 答案 |
|------|------|
| 什么时候应该跑？ | 仅当用户、Planner 或 Orchestrator **显式**要求跑测试/质量报告时（用户通过路由、Orchestrator 通过 context 或工作流阶段）。 |
| 什么时候不需要跑？ | 未显式要求时；或明确为「确认写入」「单条命令」等非测试意图时。 |
| 谁做决定？ | 用户（通过路由结果）、Orchestrator（通过 dispatch 的 context 或工作流阶段）、Planner（通过工作流阶段转化）。Bash/Tester 只执行指令，不做「要不要跑」的决策。 |
