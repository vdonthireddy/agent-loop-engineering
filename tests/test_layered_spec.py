import pytest
from pathlib import Path

from agent_loop_engineering.layered_spec import load_project, compose, LayeredSpecError

def test_layered_spec_full(tmp_path):
    # 1. stack.yaml
    (tmp_path / "stack.yaml").write_text("name: Test Stack\nlanguage: python\n")
    
    # 2. features
    feat_dir = tmp_path / "features"
    feat_dir.mkdir()
    (feat_dir / "login.md").write_text("---\nid: login\nname: Login\n---\nLogin logic")
    (feat_dir / "reports.md").write_text("Reports logic") # id/name defaults to stem
    
    # 3. customers
    cust_dir = tmp_path / "customers"
    cust_dir.mkdir()
    (cust_dir / "cust1.yaml").write_text("""
tenant_id: c1
overrides:
  - feature: login
    directive: extend
    rules: Require CAPTCHA
  - feature: reports
    directive: disable
    rules: Not available
""")
    (cust_dir / "cust2.yaml").write_text("""
tenant_id: c2
overrides:
  - feature: new_feature
    directive: add
    rules: Some added feature
""")

    project = load_project(tmp_path)
    composed = compose(project)
    
    assert "Test Stack" in composed.title
    assert "Multi-Tenant" in composed.title
    
    text = composed.text
    assert "Login logic" in text
    assert "Require CAPTCHA" in text
    assert "disable" in text.lower()
    assert "Some added feature" in text

def test_unknown_feature_error(tmp_path):
    (tmp_path / "stack.yaml").write_text("name: Test Stack\n")
    feat_dir = tmp_path / "features"
    feat_dir.mkdir()
    (feat_dir / "login.md").write_text("Login logic")
    
    cust_dir = tmp_path / "customers"
    cust_dir.mkdir()
    (cust_dir / "cust1.yaml").write_text("""
overrides:
  - feature: does_not_exist
    directive: extend
    rules: something
""")

    project = load_project(tmp_path)
    with pytest.raises(LayeredSpecError):
        compose(project)

def test_invalid_directive_error(tmp_path):
    (tmp_path / "stack.yaml").write_text("name: Test Stack\n")
    feat_dir = tmp_path / "features"
    feat_dir.mkdir()
    (feat_dir / "login.md").write_text("Login logic")
    
    cust_dir = tmp_path / "customers"
    cust_dir.mkdir()
    (cust_dir / "cust1.yaml").write_text("""
overrides:
  - feature: login
    directive: invalid_directive
    rules: something
""")

    with pytest.raises(LayeredSpecError):
        load_project(tmp_path)

def test_single_tenant(tmp_path):
    (tmp_path / "stack.yaml").write_text("name: Test Stack\n")
    feat_dir = tmp_path / "features"
    feat_dir.mkdir()
    (feat_dir / "login.md").write_text("Login logic")
    
    project = load_project(tmp_path)
    composed = compose(project)
    
    assert "Multi-Tenant" not in composed.title
    assert "Tenancy" not in composed.text

def test_missing_stack(tmp_path):
    with pytest.raises(LayeredSpecError):
        load_project(tmp_path)
