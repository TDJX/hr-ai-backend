from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableWithMessageHistory

from rag.database.model import VectorStoreModel
from rag.llm.model import ChatModel
from rag.memory import ChatMemoryManager

rag_template: str = """
You are a beverage and alcohol expert — like a sommelier, but for all kinds of alcoholic drinks, including beer, wine, spirits, cocktails, etc
Answer clearly and stay within your expertise in alcohol and related topics
Rules:
1. Speak in first person: "I recommend", "I think"
2. Be conversational and personable - like a knowledgeable friend at a bar
3. Use facts from the context for specific characteristics, but speak generally when needed
4. Do not disclose sources or metadata from contextual documents
5. Answer questions about alcohol and related topics (food pairings, culture, serving, etc) but politely decline unrelated subjects
6. Be brief and useful - keep answers to 2-4 sentences
7. Use chat history to maintain a natural conversation flow
8. Feel free to use casual language and humor when appropriate

Context: {context}
"""

get_summary_template = """Create a concise 3-5 word title for the following conversation.
                          Focus on the main topic. Reply only with the title.\n\n
                          Chat history:\n"""

rephrase_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Given a chat history and the latest user question which might reference context in the chat history, "
            "formulate a standalone question. Do NOT answer the question.",
        ),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ]
)

qa_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", rag_template),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ]
)


class RagService:
    def __init__(self, vector_store: VectorStoreModel, llm: ChatModel):
        self.vector_store = vector_store.get_store()
        self.llm = llm.get_llm()

        retriever = self.vector_store.as_retriever()

        self.rephrase_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "Given a chat history and the latest user question which might reference context in the chat history, "
                    "formulate a standalone question. Do NOT answer the question.",
                ),
                MessagesPlaceholder("chat_history"),
                ("human", "{input}"),
            ]
        )

        self.qa_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", rag_template),
                MessagesPlaceholder("chat_history"),
                ("human", "{input}"),
            ]
        )

        self.history_aware_retriever = create_history_aware_retriever(
            self.llm, retriever, self.rephrase_prompt
        )

        self.question_answer_chain = create_stuff_documents_chain(
            self.llm, self.qa_prompt
        )

        self.rag_chain = create_retrieval_chain(
            self.history_aware_retriever, self.question_answer_chain
        )

    def get_qa_from_query(self, query: str, session_id: int) -> str:
        memory = ChatMemoryManager(self.llm)

        async def get_session_history(_):
            # TODO: Pass actual AsyncSession here
            return (await memory.get_session_memory(session_id, None)).chat_memory

        conversational_rag_chain = RunnableWithMessageHistory(
            self.rag_chain,
            get_session_history,
            input_messages_key="input",
            history_messages_key="chat_history",
            output_messages_key="answer",
        )

        for chunk in conversational_rag_chain.stream(
            {"input": query}, config={"configurable": {"session_id": str(session_id)}}
        ):
            answer = chunk.get("answer", "")
            if answer:
                yield answer

    def generate_title_with_llm(self, chat_history: str | list[str]) -> str:
        # Вариант 1: Если chat_history — строка
        if isinstance(chat_history, str):
            prompt = get_summary_template + chat_history

            messages = [
                SystemMessage(
                    content="You are a helpful assistant that generates chat titles."
                ),
                HumanMessage(content=prompt),
            ]

        # Вариант 2: Если chat_history — список сообщений (например, ["user: ...", "bot: ..."])
        else:
            prompt = get_summary_template + "\n".join(chat_history)
            messages = [
                SystemMessage(
                    content="You are a helpful assistant that generates chat titles."
                ),
                HumanMessage(content=prompt),
            ]

        response = self.llm.invoke(messages)
        return response.content.strip()
