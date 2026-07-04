from pathlib import Path

from agent_loop_engineering.spec import SpecDocument

def test_spec_from_text():
    spec = SpecDocument.from_text("# My App\n\nThis is a test app.\nlanguage: python")
    assert spec.title == "My App"
    assert spec.language_hint() == "python"
    assert spec.text.startswith("# My App")

def test_spec_from_text_no_title():
    spec = SpecDocument.from_text("Just some text here.")
    assert spec.title == "composed-spec"
    assert spec.language_hint() is None
