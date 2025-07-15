import pytest
import os

if __name__ == "__main__":
    test_files = [
        "tests/test_server.py",
        "tests/test_pauschale_logic.py",
        "tests/test_pauschale_selection.py",
    ]
    for test_file in test_files:
        if os.path.exists(test_file):
            print(f"Running tests for {test_file}")
            pytest.main([test_file])
        else:
            print(f"Test file not found: {test_file}")
