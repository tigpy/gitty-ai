import uuid
import os
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from ..domain.interfaces.repository_scanner import IRepositoryScanner
from .file_discovery_service import FileDiscoveryService
from .language_detection_service import LanguageDetectionService
from libs.core.message_bus.interfaces.event_bus import IEventBus
from libs.events.schemas import RepositoryDiscoveredV1, RepositoryIndexedV1

class RepositoryScanService:
    def __init__(
        self,
        scanner: IRepositoryScanner,
        discovery_service: FileDiscoveryService,
        language_service: LanguageDetectionService,
        publisher: Optional[IEventBus] = None
    ):
        self.scanner = scanner
        self.discovery_service = discovery_service
        self.language_service = language_service
        self.publisher = publisher

    def scan_remote_repository(
        self,
        repo_url: str,
        working_dir: str,
        repo_id: Optional[str] = None
    ) -> Dict[str, Any]:
        if not repo_id:
            repo_id = str(uuid.uuid4())

        from libs.common.progress import publish_progress
        publish_progress(repo_id, "processing", "Cloning repository...")

        root_path = self.scanner.clone_or_fetch(repo_url, working_dir)
        publish_progress(repo_id, "processing", "✓ Cloned repository")

        # Publish RepositoryDiscoveredV1 event
        if self.publisher:
            repo_name = os.path.basename(repo_url.rstrip("/")).replace(".git", "")
            discovered_event = RepositoryDiscoveredV1(
                event_id=str(uuid.uuid4()),
                timestamp=datetime.now(timezone.utc),
                repository_id=repo_id,
                name=repo_name,
                root_path=root_path,
                url=repo_url
            )
            self.publisher.publish("repository.discovered", discovered_event)

        publish_progress(repo_id, "processing", "Scanning files...")
        files = self.discovery_service.discover_files(root_path)
        
        # Enrich discovered files with language mapping
        for file_info in files:
            file_info["language"] = self.language_service.detect(file_info["path"])

        # Publish RepositoryIndexedV1 event
        if self.publisher:
            indexed_event = RepositoryIndexedV1(
                event_id=str(uuid.uuid4()),
                timestamp=datetime.now(timezone.utc),
                repository_id=repo_id,
                repository_url=repo_url,
                indexed_files_count=len(files),
                status="success"
            )
            self.publisher.publish("repository.indexed", indexed_event)

        return {
            "repository_id": repo_id,
            "root_path": root_path,
            "files": files
        }
