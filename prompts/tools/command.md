# Command Tool

Execute system commands under controlled policies, returning stdout, exit code, and execution time. Does not parse business logic—only handles execution and security validation.

**Use cases**: Run tests, type checks, read-only operations, confirmed installs/commits; called by Bash subagent or main control logic.
**Cannot use**: Blacklisted commands are blocked; in strict mode, non-whitelisted commands are blocked; does not make "should I execute" decisions on behalf of the caller.

---

## Usage

- **Command parameter**: The command string to execute; optional timeout controlled by config or parameters. Current mode: `{{security_mode}}` (strict | normal | trust), timeout: `{{timeout}}` s, max output: `{{max_output_length}}` chars, allowed paths: `{{allowed_paths}}`.
- **Paths with spaces**: Must be wrapped in double quotes (e.g., `cd "path with spaces/file.txt"`).
- **Command description**: Provide a short, clear description (5-10 words) explaining what the command does; complex or piped commands can be more detailed for user understanding.
- **No newlines to separate commands**: One command per call; do not write multiple commands separated by newlines in a single input (newlines only for quoted strings).

**IMPORTANT - Prefer dedicated tools**: Use Read tool instead of `cat`/`head`/`tail`; use Edit tool instead of `sed`/`awk`; use Grep tool for content search instead of `grep`/`rg`. Only use this tool when explicitly needed or when dedicated tools cannot satisfy the requirement.

---

## Security Policy

- **Blacklist (always denied)**: rm -rf, curl|bash, wget piped execution, sudo, chmod 777, dd, mkfs, etc.
- **Whitelist (direct execution)**: ls, pwd, cat, head, tail, wc, find; git status/log/diff/branch/remote; python --version, pytest --collect-only, mypy --version; cd, tree.
- **Requires confirmation**: mkdir, cp, mv, rm (non-destructive), git add/commit/push/pull, pip install, npm install, make, npm run build, etc.

---

## Structured Output (guaranteed by tool implementation)

Each call returns the following structure (prompt only defines semantics):

```
stdout: <standard output content, truncated if too long>
stderr: <standard error, empty if none>
exit_code: <integer exit code>
execution_time_ms: <milliseconds>
```

If denied or confirmation not passed, the reason is returned via error event or designated field, not the above execution result.