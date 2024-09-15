
from typing import Sequence
from dataclasses import dataclass, field, asdict
from langchain_mongodb import MongoDBChatMessageHistory
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage
from langchain_core.runnables.history import RunnableWithMessageHistory

_INPUT_MESSAGES_KEY = 'question'
_HISTORY_MESSAGES_KEY = 'history'

@dataclass(kw_only=True, slots=True)
class BaseMessageHistorySchema:
    """Base Schema for a data store like Redis, MongoDB, PostgreSQL, ChromaDB, etc"""
    connection_string: str
    session_id_key: str
    session_id: str

@dataclass(kw_only=True, slots=True)
class MongoMessageHistorySchema(BaseMessageHistorySchema):
    """Schema for MongoDB data store"""
    database_name: str
    collection_name: str
    create_index: bool = True

class MongoMessageHistory:
    def __init__(self, schema: MongoMessageHistorySchema):
        self._schema = schema
        self._message_history = MongoDBChatMessageHistory(**asdict(self._schema))

    @property
    def messages(self) -> list[BaseMessage]:
        return self._message_history.messages
    
    @property
    def has_no_messages(self) -> bool:
        return not self.messages

    async def add_messages(self, messages: Sequence[BaseMessage]):
        """Add messages to store"""
        await self._message_history.aadd_messages(messages)

    async def system(self, prompt: str) -> SystemMessage:
        """Add system message to store"""
        system_message = SystemMessage(prompt)
        await self.add_messages([system_message])
        return system_message

    async def human(self, message_schema: dict) -> HumanMessage:
        """Add system message to store"""
        human_message = HumanMessage(message_schema)
        await self.add_messages([human_message])
        return human_message
    
    async def ai(self, message_schema: dict) -> AIMessage:
        """Add ai message to store"""
        ai_message = AIMessage(message_schema)
        await self.add_messages([ai_message])
        return ai_message

    async def bulk_add(self, messages: Sequence[BaseMessage]) -> bool:
        """Bulk add operation to store"""
        await self.add_messages(messages)
        return True

    def runnable(self, chain = None) -> RunnableWithMessageHistory:
        """Wraps a Runnable with a Chat History Runnable"""
        """session_id is used to determine whether to create a new message history or load existing"""
        """If message history is stored in the mongo store, it will be loaded here"""
        return RunnableWithMessageHistory(
            chain,
            self._schema.session_id,
            input_messages_key=_INPUT_MESSAGES_KEY,
            history_messages_key=_HISTORY_MESSAGES_KEY,
        )