import pytest
from pathlib import Path
from agent_loop_engineering.workspace import Workspace, WorkspaceError

def test_workspace_isolation(tmp_path):
    ws = Workspace(tmp_path / "sandbox")
    
    # Writing inside works
    p = ws.write_file("test.txt", "hello")
    assert p.is_file()
    assert ws.read_file("test.txt") == "hello"
    
    # Path traversal fails
    with pytest.raises(WorkspaceError):
        ws.resolve("../outside.txt")
        
    with pytest.raises(WorkspaceError):
        ws.write_file("../outside.txt", "hacked")

def test_workspace_list_files(tmp_path):
    ws = Workspace(tmp_path / "sandbox")
    ws.write_file("a.txt", "a")
    ws.write_file("dir/b.txt", "b")
    
    files = ws.list_files()
    assert len(files) == 2
    assert "a.txt" in files
    # Depending on OS, path separator might differ, but in unix it's dir/b.txt
    assert any(f.endswith("b.txt") for f in files)
