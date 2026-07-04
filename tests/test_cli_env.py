import os
from agent_loop_engineering.cli import _load_dotenv

def test_load_dotenv_sets_unset(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("MY_TEST_KEY=my_test_value\n")
    
    _load_dotenv(str(env_file))
    
    assert os.environ.get("MY_TEST_KEY") == "my_test_value"
    # cleanup
    del os.environ["MY_TEST_KEY"]

def test_load_dotenv_respects_quotes(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text('MY_TEST_KEY="my_test_value"\nMY_TEST_KEY2=\'other_val\'\n')
    
    _load_dotenv(str(env_file))
    
    assert os.environ.get("MY_TEST_KEY") == "my_test_value"
    assert os.environ.get("MY_TEST_KEY2") == "other_val"
    del os.environ["MY_TEST_KEY"]
    del os.environ["MY_TEST_KEY2"]

def test_load_dotenv_never_overrides(tmp_path):
    os.environ["MY_TEST_KEY"] = "original_value"
    
    env_file = tmp_path / ".env"
    env_file.write_text("MY_TEST_KEY=new_value\n")
    
    _load_dotenv(str(env_file))
    
    assert os.environ.get("MY_TEST_KEY") == "original_value"
    del os.environ["MY_TEST_KEY"]

def test_load_dotenv_missing_noop():
    # Should not raise any exception
    _load_dotenv("does_not_exist.env")
