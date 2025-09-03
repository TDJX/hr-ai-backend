import json
from datetime import datetime
from typing import List, Optional
import redis
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from langchain.schema import HumanMessage, AIMessage
from langchain.memory import ConversationSummaryBufferMemory

from rag.settings import settings


class ChatMemoryManager:
    def __init__(self, llm, token_limit=3000):
        self.redis = redis.Redis(host=settings.redis_cache_url, port=settings.redis_cache_port, db=settings.redis_cache_db)
        self.llm = llm
        self.token_limit = token_limit

    def _convert_to_langchain(self, messages: List[dict]):
        return [
            AIMessage(content=msg["content"]) if msg["is_ai"]
            else HumanMessage(content=msg["content"])
            for msg in messages
        ]

    def _annotate_messages(self, messages: List):
        # Convert to format compatible with langchain
        # Assuming messages have some way to identify if they're from AI
        return [
            {
                **msg,
                "is_ai": msg.get("user_type") == "AI" or msg.get("username") == "SOMMELIER"
            }
            for msg in messages
        ]

    def _serialize_messages(self, messages: List[dict]):
        return [
            {**msg, "created_at": msg["created_at"].isoformat()}
            for msg in messages
        ]

    def _cache_key(self, session_id: int) -> str:
        return f"chat_memory:{session_id}"

    async def load_chat_history(self, session_id: int, session: AsyncSession) -> List[HumanMessage | AIMessage]:
        cache_key = self._cache_key(session_id)
        serialized = self.redis.get(cache_key)

        if serialized:
            cached_messages = json.loads(serialized)
            if cached_messages:
                last_time = datetime.fromisoformat(cached_messages[-1]["created_at"])
                
                # TODO: Replace with actual Message model query when available
                # This would need to be implemented with SQLModel/SQLAlchemy
                new_messages = []  # Placeholder for actual DB query
                
                if new_messages:
                    annotated_messages = self._annotate_messages(new_messages)
                    all_messages = cached_messages + self._serialize_messages(annotated_messages)
                    self.redis.setex(cache_key, 3600, json.dumps(all_messages))
                    return self._convert_to_langchain(all_messages)

            return self._convert_to_langchain(cached_messages)

        # TODO: Replace with actual Message model query when available
        # This would need to be implemented with SQLModel/SQLAlchemy
        db_messages = []  # Placeholder for actual DB query
        
        if db_messages:
            annotated_messages = self._annotate_messages(db_messages)
            self.redis.setex(cache_key, 3600, json.dumps(self._serialize_messages(annotated_messages)))
            return self._convert_to_langchain(annotated_messages)

        return []

    async def get_session_memory(self, session_id: int, session: AsyncSession) -> ConversationSummaryBufferMemory:
        memory = ConversationSummaryBufferMemory(
            llm=self.llm,
            max_token_limit=self.token_limit
        )

        messages = await self.load_chat_history(session_id, session)
        for msg in messages:
            if isinstance(msg, HumanMessage):
                memory.chat_memory.add_user_message(msg.content)
            elif isinstance(msg, AIMessage):
                memory.chat_memory.add_ai_message(msg.content)
        return memory
