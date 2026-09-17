import pytest
from unittest.mock import patch, MagicMock
import subprocess
from libs.shared_kernel.validation import validate_repository_url
from services.scanner_service.infrastructure.github_repository_scanner import GithubRepositoryScanner

def test_valid_repository_urls():
    valid_urls = [
        "https://github.com/torvalds/linux",
        "https://github.com/tiangolo/fastapi.git",
        "https://gitlab.com/org/repo-name",
        "https://bitbucket.org/user/repo"
    ]
    for url in valid_urls:
        assert validate_repository_url(url) == url

def test_argument_injection_rejected():
    malicious_inputs = [
        "--upload-pack=touch /tmp/pwned",
        "-u`touch /tmp/pwned`",
        "--config=protocol.ext.allow=always",
        "-oProxyCommand=sh",
        "--depth=0",
        "-c core.symlinks=true"
    ]
    for url in malicious_inputs:
        with pytest.raises(ValueError, match="cannot start with a hyphen or command flag"):
            validate_repository_url(url)

def test_ssrf_and_private_ip_rejected():
    ssrf_urls = [
        "https://127.0.0.1/repo.git",
        "https://localhost/repo.git",
        "https://169.254.169.254/latest/meta-data",
        "https://10.0.0.1/repo.git",
        "https://192.168.1.100/repo.git",
        "https://172.16.0.5/repo.git",
        "https://0.0.0.0/repo.git",
        "http://127.0.0.1/repo.git",
        "file:///etc/passwd",
        "ftp://internal.vault/secret.git"
    ]
    for url in ssrf_urls:
        with pytest.raises(ValueError):
            validate_repository_url(url)

def test_scanner_executes_git_with_security_flags(tmp_path):
    scanner = GithubRepositoryScanner()
    test_url = "https://github.com/test-org/test-repo"
    dest_dir = str(tmp_path / "cloned_repo")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        scanner.clone_or_fetch(test_url, dest_dir)
        
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        
        # Verify git clone security arguments
        assert cmd[0] == "git"
        assert cmd[1] == "clone"
        assert "-c" in cmd
        assert "core.symlinks=false" in cmd
        assert "--" in cmd
        # Ensure -- occurs before the URL argument to prevent argument injection
        dash_idx = cmd.index("--")
        url_idx = cmd.index(test_url)
        assert dash_idx < url_idx

def test_scanner_rejects_ssrf_before_subprocess(tmp_path):
    scanner = GithubRepositoryScanner()
    ssrf_url = "https://127.0.0.1/exploit.git"
    dest_dir = str(tmp_path / "cloned_repo")

    with patch("subprocess.run") as mock_run:
        with pytest.raises(ValueError):
            scanner.clone_or_fetch(ssrf_url, dest_dir)
        mock_run.assert_not_called()
