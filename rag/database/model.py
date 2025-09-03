from langchain_core.vectorstores.base import VectorStore


class VectorStoreModel:
    def __init__(self, store: VectorStore):
        self.store = store

    def get_store(self):
        return self.store

    def similarity_search(self, query: str):
        results = self.store.similarity_search(
            query,
            k=5,
        )

        return results
