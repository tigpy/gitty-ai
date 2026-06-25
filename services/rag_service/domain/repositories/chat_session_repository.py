from abc import ABC, abstractmethod
from typing import List, Optional
from ..entities.chat_session import ChatSession, ChatMessage

class IChatSessionRepository(ABC):
    @abstractmethod
    def create_session(self, session: ChatSession) -> None:
        pass

    @abstractmethod
    def get_session(self, session_id: str) -> Optional[ChatSession]:
        pass

    @abstractmethod
    def add_message(self, message: ChatMessage) -> None:
        pass

    @abstractmethod
    def list_sessions(self, repository_id: Optional[str] = None) -> List[ChatSession]:
        pass

    @abstractmethod
    def delete_session(self, session_id: str) -> None:
        pass

    @abstractmethod
    def load_recent_history(self, session_id: str, limit: int) -> List[ChatMessage]:
        pass
