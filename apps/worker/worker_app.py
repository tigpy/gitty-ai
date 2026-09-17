import os
import sys

# Ensure project root is in sys.path to find libs and services
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# If a partial namespace 'libs' was loaded from system/win32 before project_root,
# delete it from sys.modules so it resolves from project_root/libs/__init__.py
if 'libs' in sys.modules and getattr(sys.modules['libs'], '__file__', None) is None:
    del sys.modules['libs']

import libs
from libs.common.progress import publish_progress
from celery import Celery
from libs.config import get_settings
from libs.logging import configure_logging, get_logger
from libs.core.message_bus.rabbitmq.publisher import RabbitMQPublisher
from services.scanner_service.infrastructure.github_repository_scanner import GithubRepositoryScanner
from services.scanner_service.infrastructure.local_file_walker import LocalFileWalker
from services.scanner_service.infrastructure.language_detector import LanguageDetector
from services.scanner_service.application.file_discovery_service import FileDiscoveryService
from services.scanner_service.application.language_detection_service import LanguageDetectionService
from services.scanner_service.application.repository_scan_service import RepositoryScanService
from services.parser_service.application.parser_factory import ParserFactory
from services.parser_service.application.symbol_table import SymbolTable
from services.graph_service.infrastructure.repositories.graph_repository_factory import get_graph_repository
from services.graph_service.infrastructure.repositories.sqlite_graph_repository import SQLiteGraphRepository
from services.graph_service.application.graph_builder import GraphBuilder
from services.dead_code_service.application.dead_code_detector import DeadCodeDetectionService
from services.security_service.application.security_analysis_service import SecurityAnalysisService
from libs.models.ir import IRModule, IRImport, IRClass, IRFunction, IRCall

settings = get_settings()
configure_logging(settings.ENV)
logger = get_logger("worker")

# Configure Celery
broker_url = f"amqp://guest:guest@{settings.RABBITMQ_HOST}:{settings.RABBITMQ_PORT}//"
result_backend = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0"

app = Celery(
    "gitty-worker",
    broker=broker_url,
    backend=result_backend
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

from services.graph_service.application.repository_cleanup_service import RepositoryCleanupService

@app.task(name="gitty.tasks.health_check")
def worker_health_check():
    logger.info("Executing worker health check task")
    return {"status": "ok", "worker": "gitty-worker"}

@app.task(
    name="gitty.tasks.index_repository",
    bind=True,
    max_retries=2,
    default_retry_delay=15,
    time_limit=600
)
def index_repository(self, repository_id: str, repo_url: str):
    from libs.shared_kernel.validation import REPO_ID_REGEX
    if not repository_id or not REPO_ID_REGEX.match(repository_id):
        logger.error("Invalid repository_id format in Celery task", repository_id=repository_id)
        return {"status": "failed", "error": "Invalid repository_id format"}
        
    logger.info("Starting repository indexing task", repository_id=repository_id, url=repo_url)

    # Clean up previous partial or existing state to guarantee idempotency
    try:
        cleanup_service = RepositoryCleanupService(settings.SQLITE_DB_PATH)
        cleanup_service.cleanup(repository_id)
    except Exception as e:
        logger.warning("Pre-indexing cleanup encountered error (non-fatal)", error=str(e))
        
    # Setup paths
    working_dir = os.path.join("data", "repos", repository_id)
    
    # Setup scanner service
    scanner = GithubRepositoryScanner()
    walker = LocalFileWalker()
    detector = LanguageDetector()
    
    discovery = FileDiscoveryService(walker)
    lang_service = LanguageDetectionService(detector)
    
    scan_service = RepositoryScanService(
        scanner=scanner,
        discovery_service=discovery,
        language_service=lang_service
    )
    
    # Run scan
    try:
        scan_res = scan_service.scan_remote_repository(repo_url, working_dir, repo_id=repository_id)
    except Exception as e:
        logger.error("Scan failed", repository_id=repository_id, error=str(e))
        publish_progress(repository_id, "failed", f"Scan failed: {e}")
        return {"status": "failed", "repository_id": repository_id, "error": f"Scan failed: {e}"}
        
    root_path = scan_res["root_path"]
    files = scan_res["files"]
    
    # Parse files into IR Modules
    publish_progress(repository_id, "processing", "Parsing Python files...")
    parser_factory = ParserFactory()
    modules = []

    logger.info(
        "Scan completed",
        repository_id=repository_id,
        total_files=len(files)
    )

    unsupported_count = 0
    for f_info in files:
        language = str(f_info.get("language", "")).lower()

        if language not in parser_factory.supported_languages:
            unsupported_count += 1
            continue

        f_path = f_info["path"]
        abs_path = os.path.join(root_path, f_path)

        real_root = os.path.normcase(os.path.realpath(root_path))
        real_file = os.path.normcase(os.path.realpath(abs_path))

        if not (
            real_file == real_root
            or real_file.startswith(real_root + os.path.sep)
        ):
            logger.warning(
                "Skipping traversal file path during parsing",
                path=f_path
            )
            continue

        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            parser = parser_factory.get_parser(language)
            mod_data = parser.parse_file(content, file_path=f_path)

            imports = [
                IRImport(**imp)
                for imp in mod_data.get("imports", [])
            ]

            classes = []
            for c in mod_data.get("classes", []):
                methods = [
                    IRFunction(**m)
                    for m in c.get("methods", [])
                ]

                c_copy = c.copy()
                c_copy["methods"] = methods
                classes.append(IRClass(**c_copy))

            functions = [
                IRFunction(**func)
                for func in mod_data.get("functions", [])
            ]

            calls = [
                IRCall(**call)
                for call in mod_data.get("calls", [])
            ]

            mod = IRModule(
                file_path=f_path,
                language=language,
                imports=imports,
                classes=classes,
                functions=functions,
                calls=calls
            )
            modules.append(mod)

        except Exception as e:
            logger.warning(
                "Failed to parse file",
                file=f_path,
                error=str(e)
            )

    logger.info(
        "Parser summary",
        repository_id=repository_id,
        files_discovered=len(files),
        modules_created=len(modules),
        unsupported_skipped=unsupported_count
    )
    publish_progress(repository_id, "processing", f"✓ Parsed {len(modules)} code modules")

    # Build Graph in repository
    try:
        publish_progress(repository_id, "processing", "Building graph...")
        repo = get_graph_repository()
        symbol_table = SymbolTable()
        graph_builder = GraphBuilder(repo, symbol_table)
        
        repo_name = os.path.basename(repo_url.rstrip("/")).replace(".git", "")
        build_res = graph_builder.build_graph(
            repo_id=repository_id,
            repo_name=repo_name,
            repo_path=root_path,
            modules=modules
        )
        logger.info("Graph built successfully", repository_id=repository_id, build_result=build_res)
        publish_progress(repository_id, "processing", f"✓ Built {build_res.get('nodes_created', 0)} nodes")
        publish_progress(repository_id, "processing", f"✓ Generated {build_res.get('edges_created', 0)} relationships")
        
        # Trigger dead code detection asynchronously
        detect_dead_code.delay(repository_id)
        
    except Exception as e:
        logger.error("Graph build failed", repository_id=repository_id, error=str(e))
        publish_progress(repository_id, "failed", f"Graph build failed: {e}")
        return {"status": "failed", "repository_id": repository_id, "error": f"Graph build failed: {e}"}

    return {
        "status": "completed",
        "repository_id": repository_id,
        "nodes_created": build_res.get("nodes_created", 0),
        "edges_created": build_res.get("edges_created", 0)
    }

@app.task(
    name="gitty.tasks.detect_dead_code",
    bind=True,
    max_retries=2,
    default_retry_delay=15,
    time_limit=300
)
def detect_dead_code(self, repository_id: str):
    logger.info("Starting dead code detection task", repository_id=repository_id)
    publish_progress(repository_id, "processing", "Running dead code analysis...")
    
    try:
        repo = get_graph_repository()
        detector = DeadCodeDetectionService(repo)
        report = detector.run_analysis(repository_id)
        logger.info("Dead code detection completed", repository_id=repository_id, summary=report.summary, health=report.repository_health)
        publish_progress(repository_id, "processing", "✓ Dead code analysis complete")
        
        # Trigger security analysis task asynchronously
        analyze_repository_security.delay(repository_id)
        
        return {
            "status": "completed",
            "repository_id": repository_id,
            "summary": report.summary,
            "repository_health": report.repository_health
        }
    except Exception as e:
        logger.error("Dead code detection failed", repository_id=repository_id, error=str(e))
        publish_progress(repository_id, "failed", f"Dead code detection failed: {e}")
        return {"status": "failed", "repository_id": repository_id, "error": str(e)}

@app.task(
    name="gitty.tasks.analyze_repository_security",
    bind=True,
    max_retries=2,
    default_retry_delay=15,
    time_limit=300
)
def analyze_repository_security(self, repository_id: str):
    logger.info("Starting security analysis task", repository_id=repository_id)
    publish_progress(repository_id, "processing", "Running security analysis...")

    try:
        repo = get_graph_repository()
        service = SecurityAnalysisService(repo)
        report = service.run_security_scan(repository_id)
        logger.info("Security analysis completed", repository_id=repository_id, score=report.security_score)
        publish_progress(repository_id, "processing", "✓ Security analysis complete")
        
        # Trigger vector indexing asynchronously
        build_vector_index.delay(repository_id)

        return {
            "status": "completed",
            "repository_id": repository_id,
            "findings_count": len(report.findings),
            "security_score": report.security_score
        }
    except Exception as e:
        logger.error("Security analysis failed", repository_id=repository_id, error=str(e))
        publish_progress(repository_id, "failed", f"Security analysis failed: {e}")
        return {"status": "failed", "repository_id": repository_id, "error": str(e)}

@app.task(
    name="gitty.tasks.build_vector_index",
    bind=True,
    max_retries=2,
    default_retry_delay=15,
    time_limit=600
)
def build_vector_index(self, repository_id: str):
    logger.info("Starting vector indexing task", repository_id=repository_id)
    publish_progress(repository_id, "processing", "Building vector index...")

    try:
        from services.vector_service.infrastructure.vector_store.qdrant_repository import QdrantRepository
        from services.vector_service.infrastructure.embeddings.sentence_transformer_provider import SentenceTransformerProvider
        from services.vector_service.infrastructure.embeddings.sqlite_embedding_cache import SQLiteEmbeddingCache
        from services.vector_service.application.services.chunking_service import ChunkingService
        from services.vector_service.application.services.embedding_service import EmbeddingService
        from services.vector_service.application.services.indexing_service import IndexingService

        sqlite_repo = get_graph_repository()
        vector_repo = QdrantRepository()
        chunking_service = ChunkingService()
        
        provider = SentenceTransformerProvider()
        cache = SQLiteEmbeddingCache(db_path=settings.SQLITE_DB_PATH)
        embedding_service = EmbeddingService(provider, cache)

        indexing_service = IndexingService(
            sqlite_repo=sqlite_repo,
            vector_repo=vector_repo,
            chunking_service=chunking_service,
            embedding_service=embedding_service
        )

        res = indexing_service.index_repository(repository_id)
        logger.info("Vector indexing completed", repository_id=repository_id, stats=res)
        publish_progress(repository_id, "processing", "✓ Vector index complete")
        publish_progress(repository_id, "completed", "Completed.")
        return {
            "status": "completed",
            "repository_id": repository_id,
            "vector_count": res["vector_count"]
        }
    except Exception as e:
        logger.error("Vector indexing failed", repository_id=repository_id, error=str(e))
        publish_progress(repository_id, "failed", f"Vector indexing failed: {e}")
        return {"status": "failed", "repository_id": repository_id, "error": str(e)}

@app.task(name="gitty.tasks.worker_health_check")
def worker_health_check():
    return {"status": "ok", "worker": "gitty-worker"}

@app.task(name="gitty.tasks.generate_embeddings")
def generate_embeddings(repository_id: str):
    return {"status": "completed", "repository_id": repository_id}

