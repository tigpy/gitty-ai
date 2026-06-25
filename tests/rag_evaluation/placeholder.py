from pydantic import BaseModel
from typing import List, Dict, Any

class RAGEvalItem(BaseModel):
    question: str
    expected_files: List[str]
    expected_symbols: List[str]
    category: str

# Ground-truth evaluation dataset for Gitty AI Repository Reasoning Engine
EVALUATION_DATASET: List[RAGEvalItem] = [
    RAGEvalItem(
        category="Code Understanding",
        question="Where is JWT authentication implemented?",
        expected_files=["src/auth/auth_service.py", "libs/auth/jwt.py"],
        expected_symbols=["validate_jwt", "AuthenticationService"]
    ),
    RAGEvalItem(
        category="Architecture",
        question="How does repository indexing work?",
        expected_files=["services/scanner_service/application/services/repository_scan_service.py"],
        expected_symbols=["scan_repository", "RepositoryScanner"]
    ),
    RAGEvalItem(
        category="Security",
        question="What hardcoded secrets were found?",
        expected_files=["tests/fixtures/secrets.py"],
        expected_symbols=["AWS_SECRET_ACCESS_KEY", "DATABASE_PASSWORD"]
    ),
    RAGEvalItem(
        category="Cross-Repository Knowledge",
        question="How does the worker communicate with the API gateway?",
        expected_files=["libs/core/message_bus/rabbitmq/publisher.py"],
        expected_symbols=["RabbitMQPublisher", "publish"]
    ),
    RAGEvalItem(
        category="Dead Code",
        question="Why was this function marked as dead code?",
        expected_files=["services/dead_code_service/application/services/dead_code_service.py"],
        expected_symbols=["detect_dead_functions", "DeadCodeService"]
    )
]
