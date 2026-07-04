import json
from pathlib import Path

from ..workspace import Workspace, WorkspaceError
from .base import AgentResult, ToolCall

_MAX_TURNS = 60

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_bash",
            "description": "Run a bash command in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read content from a file in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "str_replace",
            "description": "Replace exactly one instance of a string in a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_str": {"type": "string"},
                    "new_str": {"type": "string"},
                },
                "required": ["path", "old_str", "new_str"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List all files in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
]


def _dispatch(ws: Workspace, tool_call: dict, files_touched: list[str]) -> tuple[str, bool]:
    name = tool_call["function"]["name"]
    try:
        args = json.loads(tool_call["function"]["arguments"])
    except Exception as e:
        return f"error: invalid JSON arguments - {e}", False

    try:
        if name == "run_bash":
            cmd = args["command"]
            res = ws.run_command(cmd)
            return res.combined_output, res.ok
        elif name == "write_file":
            path = args["path"]
            ws.write_file(path, args["content"])
            files_touched.append(ws.relpath(path))
            return f"wrote {path}", True
        elif name == "read_file":
            return ws.read_file(args["path"]), True
        elif name == "str_replace":
            path = args["path"]
            old_str = args["old_str"]
            new_str = args["new_str"]
            content = ws.read_file(path)
            count = content.count(old_str)
            if count == 0:
                return "error: old_str not found in file", False
            if count > 1:
                return "error: old_str matches multiple times, be more specific", False
            ws.write_file(path, content.replace(old_str, new_str))
            files_touched.append(ws.relpath(path))
            return f"replaced text in {path}", True
        elif name == "list_files":
            return "\n".join(ws.list_files()), True
        else:
            return f"error: unknown tool {name}", False
    except WorkspaceError as e:
        return f"error: sandbox violation - {e}", False
    except KeyError as e:
        return f"error: missing argument {e}", False
    except Exception as e:
        return f"error: {e}", False


async def run_openai_tool_loop(
    client, *, model: str, system_prompt: str, task: str, workspace: Path
) -> AgentResult:
    ws = Workspace(workspace)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": task},
    ]

    files_touched = []
    tool_calls_log = []
    stop_reason = "end_turn"
    text = ""

    for _ in range(_MAX_TURNS):
        try:
            resp = await client.chat.completions.create(
                model=model,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
            )
        except Exception as e:
            text = f"API error: {e}"
            stop_reason = "error"
            break

        msg = resp.choices[0].message
        if not msg.tool_calls:
            text = msg.content or ""
            stop_reason = resp.choices[0].finish_reason or "end_turn"
            break

        messages.append(msg)
        text = msg.content or ""
        
        for tc in msg.tool_calls:
            fn_name = tc.function.name
            out_text, ok = _dispatch(ws, tc.model_dump(), files_touched)
            tool_calls_log.append(ToolCall(name=fn_name, summary=f"called {fn_name}", ok=ok))
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": out_text,
                }
            )

    else:
        stop_reason = "max_iterations"

    return AgentResult(
        text=text,
        files_touched=sorted(list(set(files_touched))),
        tool_calls=tool_calls_log,
        stop_reason=stop_reason,
    )
