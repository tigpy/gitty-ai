import os
import pytest
import hashlib
from services.scanner_service.infrastructure.local_file_walker import LocalFileWalker

def test_local_file_walker_basic(tmp_path):
    # Setup test directories and files
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    
    # Create normal file
    f1 = repo_dir / "main.py"
    f1.write_text("print('hello')", encoding="utf-8")
    
    # Create ignored folder
    node_modules = repo_dir / "node_modules"
    node_modules.mkdir()
    f2 = node_modules / "index.js"
    f2.write_text("console.log()", encoding="utf-8")
    
    # Create gitignore file
    gitignore = repo_dir / ".gitignore"
    gitignore.write_text("*.log\n/ignored_dir/", encoding="utf-8")
    
    f3 = repo_dir / "debug.log"
    f3.write_text("error", encoding="utf-8")
    
    ignored_dir = repo_dir / "ignored_dir"
    ignored_dir.mkdir()
    f4 = ignored_dir / "secret.txt"
    f4.write_text("secret", encoding="utf-8")
    
    # Run walker
    walker = LocalFileWalker()
    files = walker.walk(str(repo_dir))
    
    # Verify results
    paths = {f["path"] for f in files}
    
    assert "main.py" in paths
    assert ".gitignore" in paths
    assert "node_modules/index.js" not in paths
    assert "debug.log" not in paths
    assert "ignored_dir/secret.txt" not in paths
    
    # Test file hashing
    main_file = [f for f in files if f["path"] == "main.py"][0]
    expected_hash = hashlib.sha256(b"print('hello')").hexdigest()
    assert main_file["checksum"] == expected_hash

def test_local_file_walker_empty_gitignore(tmp_path):
    repo_dir = tmp_path / "repo_empty"
    repo_dir.mkdir()
    f1 = repo_dir / "main.py"
    f1.write_text("hello", encoding="utf-8")
    
    # Create an empty .gitignore
    gitignore = repo_dir / ".gitignore"
    gitignore.write_text("", encoding="utf-8")
    
    walker = LocalFileWalker()
    files = walker.walk(str(repo_dir))
    paths = {f["path"] for f in files}
    assert "main.py" in paths
    assert ".gitignore" in paths

def test_local_file_walker_missing_file_handling(tmp_path):
    # This tests the exception handling inside walker
    walker = LocalFileWalker()
    # Walking a non-existent directory shouldn't crash, but return empty list
    files = walker.walk(str(tmp_path / "non_existent"))
    assert files == []

def test_local_file_walker_gitignore_subfolder_match(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    
    # Create gitignore rule matching folder name
    gitignore = repo_dir / ".gitignore"
    gitignore.write_text("build_logs", encoding="utf-8")
    
    # Create a file inside matching folder
    sub = repo_dir / "src" / "build_logs"
    sub.mkdir(parents=True)
    f = sub / "output.log"
    f.write_text("log contents", encoding="utf-8")
    
    walker = LocalFileWalker()
    files = walker.walk(str(repo_dir))
    paths = {f["path"] for f in files}
    assert "src/build_logs/output.log" not in paths

def test_local_file_walker_exceptions(tmp_path, monkeypatch):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    
    f1 = repo_dir / "main.py"
    f1.write_text("print('hello')", encoding="utf-8")
    
    walker = LocalFileWalker()
    
    # 1. Trigger exception in _compute_sha256
    assert walker._compute_sha256(str(repo_dir / "non_existent")) == ""
    
    # 2. Trigger exception in _parse_gitignore by making gitignore a directory
    gitignore_dir = repo_dir / ".gitignore"
    gitignore_dir.mkdir()
    # Walking should continue successfully and not crash
    files = walker.walk(str(repo_dir))
    assert "main.py" in {f["path"] for f in files}
    
    # Clean up gitignore directory
    gitignore_dir.rmdir()
    
    # 3. Trigger exception in walk (getsize failure)
    # We can mock os.path.getsize to raise an OSError
    def mock_getsize(path):
        raise OSError("Permission denied")
    
    monkeypatch.setattr(os.path, "getsize", mock_getsize)
    files = walker.walk(str(repo_dir))
    # It should skip the file that raised an exception and return empty list
    assert files == []


def test_local_file_walker_cross_platform_patterns(tmp_path):
    r"""
    Regression test for:
    - directory ignore patterns (trailing slash, e.g. 'build/')
    - Windows path separators (\)
    - Unix-style gitignore patterns (/root_only/, *.tmp, dir/*)
    - nested ignored directories
    """
    repo = tmp_path / "repo_patterns"
    repo.mkdir()

    gitignore = repo / ".gitignore"
    gitignore.write_text(
        "*.tmp\n"
        "/anchored_dir/\n"
        "nested/ignore_me/\n"
        "build/\n"
        "windows\\slash\\dir/\n",
        encoding="utf-8"
    )

    (repo / "index.ts").write_text("code", encoding="utf-8")
    (repo / "temp.tmp").write_text("temp", encoding="utf-8")

    anchored = repo / "anchored_dir"
    anchored.mkdir()
    (anchored / "file1.txt").write_text("f1", encoding="utf-8")

    sub_anchored = repo / "sub" / "anchored_dir"
    sub_anchored.mkdir(parents=True)
    (sub_anchored / "file2.txt").write_text("f2", encoding="utf-8")

    nested = repo / "nested" / "ignore_me"
    nested.mkdir(parents=True)
    (nested / "nested_file.txt").write_text("nf", encoding="utf-8")

    build = repo / "build"
    build.mkdir()
    (build / "bundle.js").write_text("bundle", encoding="utf-8")

    walker = LocalFileWalker()
    files = walker.walk(str(repo))
    paths = {f["path"] for f in files}

    assert "index.ts" in paths
    assert ".gitignore" in paths
    assert "sub/anchored_dir/file2.txt" in paths  # Not anchored at root, so kept
    assert "temp.tmp" not in paths
    assert "anchored_dir/file1.txt" not in paths
    assert "nested/ignore_me/nested_file.txt" not in paths
    assert "build/bundle.js" not in paths

