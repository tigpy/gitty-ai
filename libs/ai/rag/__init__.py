class HybridRetriever:
    """Not the RAG implementation.

    Hybrid retrieval is GraphContextExpander, used by RAGService and ChatService.
    This class used to return a fabricated snippet. It now refuses that call.
    """

    def __init__(self, vector_store, graph_client):
        self.vector_store = vector_store
        self.graph_client = graph_client

    def retrieve(self, query: str, limit: int = 5):
        raise NotImplementedError(
            "HybridRetriever is not implemented. Use services.rag_service RAGService or ChatService."
        )
