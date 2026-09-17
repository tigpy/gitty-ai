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

        # Ensure canonical destination directory path
        abs_dest = os.path.abspath(dest_path)
        if not os.path.exists(abs_dest):
            os.makedirs(abs_dest, exist_ok=True)

        git_dir = os.path.join(abs_dest, ".git")
        if os.path.exists(git_dir):
            # Pull updates safely
            subprocess.run(
                ["git", "pull", "--ff-only"],
                cwd=abs_dest,
                capture_output=True,
                check=True,
                timeout=timeout
            )
        else:
            # Clone fresh shallow repository with end-of-options delimiter
            subprocess.run(
                [
                    "git",
                    "clone",
                    "--depth=1",
                    "-c", "core.symlinks=false",
                    "--",
                    safe_url,
                    abs_dest
                ],
                capture_output=True,
                check=True,
                timeout=timeout
            )
        return abs_dest

Class = GithubRepositoryScanner

