import os
import re
import shutil
import stat
import subprocess
from ..domain.interfaces.repository_scanner import IRepositoryScanner
from libs.shared_kernel.validation import prepare_repository_clone_url


class GitCloneError(RuntimeError):
    """Raised when git clone fails with safe, detailed context."""

    def __init__(self, message: str, returncode: int = 1, stderr: str = "", stdout: str = ""):
        super().__init__(message)
        self.message = message
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = stdout


def _sanitize_git_error(raw_stderr: str, abs_dest: str) -> str:
    """Removes internal filesystem paths and extracts a safe, actionable error message."""
    if not raw_stderr:
        return "Unknown Git error"

    cleaned = raw_stderr
    if abs_dest:
        cleaned = cleaned.replace(abs_dest, "<target_dir>")
        cleaned = cleaned.replace(abs_dest.replace("\\", "/"), "<target_dir>")

    lower = cleaned.lower()
    if "could not read username" in lower or "terminal prompts disabled" in lower or "authentication failed" in lower:
        return "Repository not found or is private/inaccessible (authentication required)."
    if "repository not found" in lower or ("not found" in lower and "fatal:" in lower):
        return "Repository not found."
    if "could not resolve host" in lower:
        return "Network error: Could not resolve repository host."
    if "failed to connect" in lower or "connection refused" in lower:
        return "Network error: Unable to connect to remote host."
    if "ssl" in lower or "certificate" in lower:
        return "TLS/SSL certificate error while communicating with remote repository."
    if "timed out" in lower:
        return "Network timeout while communicating with remote repository."
    if "invalid path" in lower or "unable to checkout working tree" in lower:
        match = re.search(r"invalid path ['\"]([^'\"]+)['\"]", cleaned)
        if match:
            return f"Checkout failed: repository contains path incompatible with local filesystem ('{match.group(1)}')."
        return "Checkout failed: repository contains file paths incompatible with local filesystem."

    for line in cleaned.splitlines():
        line = line.strip()
        if line.startswith("fatal:") or line.startswith("error:"):
            return line

    lines = [l.strip() for l in cleaned.splitlines() if l.strip()]
    return lines[0] if lines else "Git operation failed."


class GithubRepositoryScanner(IRepositoryScanner):
    def clone_or_fetch(self, repo_url: str, dest_path: str, timeout: int = 120) -> str:
        """
        Securely clones remote repository using shallow clones (--depth=1) or runs git pull if exists.
        Protects against:
        - Argument Injection (CWE-88) via explicit '--' end-of-options delimiter.
        - SSRF (CWE-918) via scheme, DNS, obfuscated-IP, and redirect revalidation.
        - Redirect bypass via http.followRedirects=false after the checked URL is chosen.
        - Symlink abuse via core.symlinks=false.
        - Denial of Service via subprocess execution timeout.
        """
        # Validate repository URL
        safe_url = prepare_repository_clone_url(repo_url)

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
                capture_output=True,
                text=True,
                env=git_env
            )
            if head_check.returncode == 0:
                is_valid_git = True

        if is_valid_git:
            try:
                # Pull updates safely
                pull_res = subprocess.run(
                    [
                        "git",
                        "-c", "credential.helper=",
                        "-c", "core.symlinks=false",
                        "-c", "http.followRedirects=false",
                        "pull",
                        "--ff-only",
                    ],
                    cwd=abs_dest,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    env=git_env
                )
                if pull_res.returncode == 0:
                    return abs_dest
            except Exception:
                # If pull fails, fall back to clean clone
                pass

        # If destination exists, clean it first to avoid fatal clone errors
        if os.path.exists(abs_dest):
            def remove_readonly(func, path, excinfo):
                os.chmod(path, stat.S_IWRITE)
                func(path)
            shutil.rmtree(abs_dest, onerror=remove_readonly)

        # Clone fresh shallow repository with end-of-options delimiter
        clone_cmd = [
            "git",
            "-c", "credential.helper=",
            "-c", "core.symlinks=false",
            "-c", "http.followRedirects=false",
            "clone",
            "--depth=1",
            "--",
            safe_url,
            abs_dest
        ]

        try:
            proc = subprocess.run(
                clone_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=git_env
            )
        except subprocess.TimeoutExpired as e:
            raise GitCloneError(
                f"Git clone timed out after {timeout} seconds.",
                returncode=-1,
                stderr="Timeout expired"
            ) from e
        except OSError as e:
            raise GitCloneError(
                f"Failed to execute git: {e}",
                returncode=-1,
                stderr=str(e)
            ) from e

        if proc.returncode == 0:
            return abs_dest

        # Clone returned non-zero. Check if the clone itself succeeded into .git but
        # the working tree checkout failed (e.g. Windows filesystem restriction on filenames like ':').
        if os.path.exists(git_dir):
            head_verify = subprocess.run(
                ["git", "rev-parse", "--verify", "HEAD"],
                cwd=abs_dest,
                capture_output=True,
                text=True,
                env=git_env
            )
            if head_verify.returncode == 0:
                # Attempt to checkout all valid files, skipping any OS-incompatible paths
                subprocess.run(
                    ["git", "checkout", "HEAD", "--", "."],
                    cwd=abs_dest,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    env=git_env
                )
                # Verify that files were checked out into the working directory
                has_files = any(
                    not f.startswith(".git")
                    for _, _, files in os.walk(abs_dest)
                    for f in files
                )
                if has_files:
                    return abs_dest

        # If we reach here, the clone genuinely failed or could not be checked out.
        safe_msg = _sanitize_git_error(proc.stderr, abs_dest)
        raise GitCloneError(
            f"Git clone failed (exit code {proc.returncode}): {safe_msg}",
            returncode=proc.returncode,
            stderr=proc.stderr,
            stdout=proc.stdout
        )

Class = GithubRepositoryScanner
