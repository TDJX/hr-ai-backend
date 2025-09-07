from langchain_milvus import Milvus
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from rag.database.model import VectorStoreModel
from rag.llm.model import ChatModel, EmbeddingsModel
from rag.service.model import RagService
from rag.settings import settings
from rag.vector_store import MilvusVectorStore


class ModelRegistry:
    """Реестр для инициализации и получения моделей"""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._chat_model = None
            self._embeddings_model = None
            self._vector_store = None
            self._rag_service = None
            self._initialized = True

    def get_chat_model(self) -> ChatModel:
        """Получить или создать chat модель"""
        if self._chat_model is None:
            if settings.openai_api_key:
                llm = ChatOpenAI(
                    api_key=settings.openai_api_key, model="gpt-5-mini"
                )
                self._chat_model = ChatModel(llm)
            else:
                raise ValueError("OpenAI API key не настроен в settings")
        return self._chat_model

    def get_embeddings_model(self) -> EmbeddingsModel:
        """Получить или создать embeddings модель"""
        if self._embeddings_model is None:
            if settings.openai_api_key:
                embeddings = OpenAIEmbeddings(
                    api_key=settings.openai_api_key,
                    model=settings.openai_embeddings_model,
                )
                self._embeddings_model = EmbeddingsModel(embeddings)
            else:
                raise ValueError("OpenAI API key не настроен в settings")
        return self._embeddings_model

    def get_vector_store(self) -> MilvusVectorStore:
        """Получить или создать vector store"""
        if self._vector_store is None:
            embeddings_model = self.get_embeddings_model()
            self._vector_store = MilvusVectorStore(
                embeddings_model.get_model(), collection_name=settings.milvus_collection
            )
        return self._vector_store

    def get_rag_service(self) -> RagService:
        """Получить или создать RAG сервис"""
        if self._rag_service is None:
            # Создаем VectorStoreModel для совместимости с существующим кодом
            # Парсим URI для получения host и port
            uri_without_protocol = settings.milvus_uri.replace("http://", "").replace(
                "https://", ""
            )
            if ":" in uri_without_protocol:
                host, port = uri_without_protocol.split(":", 1)
                port = int(port)
            else:
                host = uri_without_protocol
                port = 19530  # Default Milvus port

            try:
                # Попробуем использовать URI напрямую
                milvus_store = Milvus(
                    embedding_function=self.get_embeddings_model().get_model(),
                    connection_args={
                        "uri": settings.milvus_uri,
                    },
                    collection_name=settings.milvus_collection,
                )
            except Exception:
                # Если не сработало, попробуем host/port
                milvus_store = Milvus(
                    embedding_function=self.get_embeddings_model().get_model(),
                    connection_args={
                        "host": host,
                        "port": port,
                    },
                    collection_name=settings.milvus_collection,
                )

            vector_store_model = VectorStoreModel(milvus_store)

            self._rag_service = RagService(
                vector_store=vector_store_model, llm=self.get_chat_model()
            )
        return self._rag_service


# Singleton instance
registry = ModelRegistry()
