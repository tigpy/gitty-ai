import os
import subprocess
from ..domain.interfaces.repository_scanner import IRepositoryScanner
from libs.shared_kernel.validation import validate_repository_url

class GithubRepositoryScanner(IRepositoryScanner):
    def clone_or_fetch(self, repo_url: str, dest_path: str, timeout: int = 120) -> str:
        """
        Securely clones remote repository using shallow clones (--depth=1) or runs git pull if exists.
        Protects against:
        - Argument Injection (CWE-88) via explicit '--' end-of-options delimiter.
        - SSRF (CWE-918) via URL scheme & private IP validation.
        - Symlink abuse via core.symlinks=false.
        - Denial of Service via subprocess execution timeout.
        """
        # Validate repository URL
        safe_url = validate_repository_url(repo_url)

        # Ensure destination path
        abs_dest = os.path.abspath(dest_path)
        git_dir = os.path.join(abs_dest, ".git")
        git_env = {
            **os.environ,
            "GIT_TERMINAL_PROMPT": "0",
            "GCM_INTERACTIVE": "never",
            "GIT_ASKPASS": "echo"
        }

        is_valid_git = False
        if os.path.exists(git_dir):
            head_check = subprocess.run(
                ["git", "rev-parse", "--verify", "HEAD"],
                cwd=abs_dest,
                capture_output=True
            )
            if head_check.returncode == 0:
                is_valid_git = True

        if is_valid_git:
            try:
                # Pull updates safely
                subprocess.run(
                    ["git", "-c", "credential.helper=", "pull", "--ff-only"],
                    cwd=abs_dest,
                    capture_output=True,
                    check=True,
                    timeout=timeout,
                    env=git_env
                )
                return abs_dest
            except Exception:
                # If pull fails, fall back to clean clone
                pass

        # If destination exists, clean it first to avoid fatal clone errors
        if os.path.exists(abs_dest):
            import shutil
            import stat
            def remove_readonly(func, path, excinfo):
                os.chmod(path, stat.S_IWRITE)
                func(path)
            shutil.rmtree(abs_dest, onerror=remove_readonly)

        # Clone fresh shallow repository with end-of-options delimiter
        subprocess.run(
            [
                "git",
                "-c", "credential.helper=",
                "-c", "core.symlinks=false",
                "clone",
                "--depth=1",
                "--",
                safe_url,
                abs_dest
            ],
            capture_output=True,
            check=True,
            timeout=timeout,
            env=git_env
        )
        return abs_dest

Class = GithubRepositoryScanner

