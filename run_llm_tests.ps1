.\venv\Scripts\pytest.exe tests/test_local_llm_provider.py tests/test_llm_providers.py -v --tb=short > llm_test_out.txt 2>&1; Get-Content llm_test_out.txt
