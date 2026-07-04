from collections.abc import Sequence
from pathlib import Path

from ..workspace import Workspace, WorkspaceError
from .base import AgentResult, ToolCall


_BASH_TOOL = {"type": "bash_20250124", "name": "bash"}
_EDITOR_TOOL = {"type": "text_editor_20250728", "name": "str_replace_based_edit_tool"}
_MAX_TURNS = 60


class ClaudeAPIEngine:
    name = "claude_api"

    def __init__(self):
        try:
            import anthropic
        except ImportError:
            raise RuntimeError("The 'anthropic' package is required. Run pip install anthropic.")

    async def run_agent(
        self,
        *,
        system_prompt: str,
        task: str,
        workspace: Path,
        tools: Sequence[str],
        model: str,
        effort: str,
    ) -> AgentResult:
        from anthropic import AsyncAnthropic
        
        client = AsyncAnthropic()
        ws = Workspace(workspace)
        
        messages = [{"role": "user", "content": task}]
        
        files_touched = []
        tool_calls_log = []
        stop_reason = "end_turn"
        
        for _ in range(_MAX_TURNS):
            try:
                # Based on Anthropic API spec, tools are passed as dicts
                stream = await client.messages.create(
                    model=model,
                    max_tokens=32000,
                    system=system_prompt,
                    thinking={"type": "adaptive"},
                    # anthropic SDK might not natively support output_config if it's too new,
                    # but following the LLD specification:
                    output_config={"effort": effort},
                    tools=[_BASH_TOOL, _EDITOR_TOOL],
                    messages=messages,
                    stream=True,
                )
                
                # Consume the stream to get the final message
                msg = await stream.get_final_message()
            except Exception as e:
                # If unsupported arguments (like output_config) cause crash, 
                # a more robust version could fallback. We follow the LLD here.
                # Just wrapping in error:
                return AgentResult(text=f"API error: {e}", stop_reason="error")

            if msg.stop_reason == "stop_sequence" or msg.stop_reason == "end_turn":
                stop_reason = "end_turn"
                break
            elif msg.stop_reason == "max_tokens":
                stop_reason = "max_tokens"
                break
            elif msg.stop_reason != "tool_use":
                stop_reason = msg.stop_reason or "unknown"
                break
                
            # If tool_use
            messages.append(msg)
            
            tool_results = []
            for block in msg.content:
                if block.type == "tool_use":
                    fn_name = block.name
                    out_text, ok = self._dispatch_tool(ws, block, files_touched)
                    
                    tool_calls_log.append(ToolCall(
                        name=fn_name, 
                        summary=self._summarize(block), 
                        ok=ok
                    ))
                    
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": out_text,
                        "is_error": not ok
                    })

            if tool_results:
                messages.append({
                    "role": "user",
                    "content": tool_results
                })
        else:
            stop_reason = "max_iterations"
            
        final_text = self._extract_text(messages)
        
        return AgentResult(
            text=final_text,
            files_touched=sorted(list(set(files_touched))),
            tool_calls=tool_calls_log,
            stop_reason=stop_reason
        )

    def _extract_text(self, messages) -> str:
        # Extract text from the last assistant message
        for msg in reversed(messages):
            if hasattr(msg, "role") and msg.role == "assistant":
                text_blocks = [b.text for b in msg.content if b.type == "text"]
                return "".join(text_blocks)
            elif isinstance(msg, dict) and msg.get("role") == "assistant":
                return str(msg.get("content", ""))
        return ""

    def _summarize(self, block) -> str:
        if block.name == "bash":
            cmd = block.input.get("command", "")
            return f"bash: {cmd[:40]}"
        elif block.name == "str_replace_based_edit_tool":
            cmd = block.input.get("command", "")
            path = block.input.get("path", "")
            return f"editor {cmd} on {path}"
        return f"called {block.name}"

    def _dispatch_tool(self, ws: Workspace, block, files_touched: list[str]) -> tuple[str, bool]:
        try:
            if block.name == "bash":
                return self._run_bash(ws, block.input)
            elif block.name == "str_replace_based_edit_tool":
                return self._run_editor(ws, block.input, files_touched)
            else:
                return f"error: unknown tool {block.name}", False
        except WorkspaceError as e:
            return f"error: sandbox violation - {e}", False
        except Exception as e:
            return f"error: {e}", False

    def _run_bash(self, ws: Workspace, args: dict) -> tuple[str, bool]:
        if args.get("command") == "restart":
            return "Restart not implemented", False
            
        cmd = args.get("command", "").strip()
        if not cmd:
            return "error: empty command", False
            
        res = ws.run_command(cmd)
        return res.combined_output, res.ok

    def _run_editor(self, ws: Workspace, args: dict, files_touched: list[str]) -> tuple[str, bool]:
        cmd = args.get("command")
        path = args.get("path")
        if not path:
            return "error: path required", False

        if cmd == "view":
            if not ws.exists(path):
                # If directory doesn't exist, this might fail, but let's assume it's file path
                pass
            target = ws.resolve(path)
            if target.is_dir():
                return "\n".join(ws.list_files()), True
            else:
                try:
                    content = ws.read_file(path)
                    # Handle view_range if provided (1-indexed)
                    view_range = args.get("view_range")
                    if view_range:
                        lines = content.splitlines()
                        start = max(1, view_range[0])
                        end = min(len(lines), view_range[1])
                        content = "\n".join(lines[start-1:end])
                    return content, True
                except Exception as e:
                    return f"error reading file: {e}", False

        elif cmd == "create":
            content = args.get("file_text", "")
            ws.write_file(path, content)
            files_touched.append(ws.relpath(path))
            return f"created {path}", True

        elif cmd == "str_replace":
            old_str = args.get("old_str", "")
            new_str = args.get("new_str", "")
            if not ws.exists(path):
                return f"error: file {path} not found", False
            content = ws.read_file(path)
            count = content.count(old_str)
            if count == 0:
                return "error: old_str not found in file", False
            if count > 1:
                return "error: old_str matches multiple times, be more specific", False
            
            ws.write_file(path, content.replace(old_str, new_str))
            files_touched.append(ws.relpath(path))
            return f"replaced text in {path}", True

        elif cmd == "insert":
            insert_line = args.get("insert_line")
            new_str = args.get("new_str", "")
            if not ws.exists(path):
                return f"error: file {path} not found", False
            content = ws.read_file(path)
            lines = content.splitlines()
            
            idx = max(0, min(len(lines), insert_line))
            lines.insert(idx, new_str)
            
            ws.write_file(path, "\n".join(lines))
            files_touched.append(ws.relpath(path))
            return f"inserted text into {path} at line {insert_line}", True

        else:
            return f"error: unknown command {cmd}", False
