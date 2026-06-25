import re
from fastapi import HTTPException

REPO_ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]+$")

def validate_repository_id(repository_id: str) -> str:
    """
    Validates repository_id format to prevent directory traversal attacks.
    Enforces alphanumeric, dash, and underscore character constraints.
    """
    if not repository_id or not REPO_ID_REGEX.match(repository_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid repository_id format. Only alphanumeric characters, dashes, and underscores are allowed."
        )
    return repository_id
