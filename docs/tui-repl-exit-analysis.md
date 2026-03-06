# TUI REPL 退出原因分析

## 退出路径汇总

当前 mini-coder TUI 会退出的情况只有以下几种：

| 路径 | 触发条件 | 表现 |
|------|----------|------|
| **1. 主循环 `user_input is None` 且连续两次** | `_get_user_input()` 或 `_get_user_input_simple()` 返回 `None`，且上一轮也是 `None` | 打印「输入结束 (EOF) 或中断。再次输入以继续…」一次后，再次得到 `None` 则 `break` → `return 0` |
| **2. 主循环收到 quit** | 用户输入 `q` / `quit` / `exit` | 直接 `break` → `return 0` |
| **3. SIGINT 信号处理** | 用户按 Ctrl+C 且内核发送 SIGINT（非 cbreak 时） | `_handle_sigint` 执行 → 打印「Interrupted by user」→ `sys.exit(130)` |
| **4. KeyboardInterrupt 未捕获** | 在 `_handle_special_commands` 或其它主循环内代码中抛出 `KeyboardInterrupt` | 只被 `__main__.main()` 的 `except KeyboardInterrupt` 捕获 → `return 130`，不打印「Interrupted by user」 |
| **5. 其它异常** | 主循环或 `run()` 内抛出 `Exception` | 被 `run()` 的 `except Exception` 捕获 → 打印「Error: …」→ `return 1` |

## 与 Ctrl+C 的混淆点

- **TTY cbreak 模式**（`is_tty=True`）：  
  Ctrl+C 通常被终端当作**普通字符 0x03** 送入 stdin，不会发 SIGINT。  
  - `_get_user_input()` 里对 `ord(char) == 3` 和 `ord(char) == 4` 统一返回 `None`。  
  - 因此「读到一个 0x03」和「用户主动按 Ctrl+C」在逻辑上**无法区分**，都变成「得到 None → 可能退出」。

- **非 cbreak / 简单输入模式**（`is_tty=False`）：  
  Ctrl+C 往往触发 **SIGINT**，由 `_handle_sigint` 直接 `sys.exit(130)`，不会走「返回 None → 两次 None 才退出」的逻辑。

- **可能的误判**：  
  大量输出（如 LLM 回复 + 耗时）后，终端或环境有时会往 stdin 写入控制字符或 0x03/0x04。下一轮 `read(1)` 或 `readline()` 立刻读到该字符，被当成「用户中断」返回 `None`；若紧接着再读到一次（或管道 EOF），就会满足「连续两次 None」而退出，看起来像「执行完命令/响应后直接退出」，容易和「用户按 Ctrl+C」混淆。

## 修复方向

1. **首次 None 时排空 stdin 中的 0x03/0x04**：在 TTY 模式下，第一次得到 `None` 时，先读掉并丢弃后续可能残留的 0x03/0x04（限制次数），再继续循环，避免一次「字符风暴」被当成两次中断。
2. **在命令处理中捕获 KeyboardInterrupt**：在调用 `_handle_special_commands` 时捕获 `KeyboardInterrupt`，打印「已取消」并 `continue`，避免一次误触或延迟送达的 Ctrl+C 直接让进程退出。
3. **保留「连续两次 None 才退出」**：继续要求两次 EOF/中断才退出，减少单次误报导致的退出。
