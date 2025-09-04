from typing import Any

from langchain_core.embeddings import Embeddings
from langchain_milvus import Milvus

from rag.settings import settings


class MilvusVectorStore:
    def __init__(
        self, embeddings_model: Embeddings, collection_name: str = "candidate_profiles"
    ):
        self.embeddings = embeddings_model
        self.collection_name = collection_name

        # Попробуем использовать URI напрямую
        self.vector_store = Milvus(
            embedding_function=embeddings_model,
            connection_args={
                "uri": settings.milvus_uri,
            },
            collection_name=collection_name,
        )

    def add_candidate_profile(self, candidate_id: str, resume_data: dict[str, Any]):
        """Добавляет профиль кандидата в векторную базу"""
        try:
            # Создаем текст для векторизации из навыков и опыта
            skills_text = " ".join(resume_data.get("skills", []))
            experience_text = " ".join(
                [
                    f"{exp.get('position', '')} {exp.get('company', '')} {exp.get('description', '')}"
                    for exp in resume_data.get("experience", [])
                ]
            )

            combined_text = (
                f"{skills_text} {experience_text} {resume_data.get('summary', '')}"
            )

            # Метаданные для поиска
            metadata = {
                "candidate_id": candidate_id,
                "name": resume_data.get("name", ""),
                "email": resume_data.get("email", ""),
                "phone": resume_data.get("phone", ""),
                "total_years": resume_data.get("total_years", 0),
                "skills": resume_data.get("skills", []),
                "education": resume_data.get("education", ""),
            }

            # Добавляем в векторную базу
            self.vector_store.add_texts(
                texts=[combined_text], metadatas=[metadata], ids=[candidate_id]
            )

            return True

        except Exception as e:
            raise Exception(f"Ошибка при добавлении кандидата в Milvus: {str(e)}") from e

    def search_similar_candidates(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        """Поиск похожих кандидатов по запросу"""
        try:
            results = self.vector_store.similarity_search_with_score(query, k=k)

            candidates = []
            for doc, score in results:
                candidate = {
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "similarity_score": score,
                }
                candidates.append(candidate)

            return candidates

        except Exception as e:
            raise Exception(f"Ошибка при поиске кандидатов в Milvus: {str(e)}") from e

    def get_candidate_by_id(self, candidate_id: str) -> dict[str, Any]:
        """Получает кандидата по ID"""
        try:
            results = self.vector_store.similarity_search(
                query="", k=1, expr=f"candidate_id == '{candidate_id}'"
            )

            if results:
                doc = results[0]
                return {"content": doc.page_content, "metadata": doc.metadata}
            else:
                return None

        except Exception as e:
            raise Exception(f"Ошибка при получении кандидата из Milvus: {str(e)}") from e

    def delete_candidate(self, candidate_id: str):
        """Удаляет кандидата из векторной базы"""
        try:
            # В Milvus удаление по ID
            self.vector_store.delete([candidate_id])
            return True

        except Exception as e:
            raise Exception(f"Ошибка при удалении кандидата из Milvus: {str(e)}") from e
