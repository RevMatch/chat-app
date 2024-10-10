from __future__ import annotations

import logging
from typing import Callable, AsyncGenerator, Optional, List, Any
from pymongo import DESCENDING
from langchain_core.runnables import Runnable, RunnablePassthrough, RunnableLambda, RunnableParallel
from langchain.chains.retrieval import create_retrieval_chain
from langchain.chains.history_aware_retriever import create_history_aware_retriever
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables.config import RunnableConfig
from langchain_core.tracers.schemas import Run
from orchestrators.doc.ingestors.ingest import ingest
from orchestrators.doc.vector_stores.abstract_vector_store import (
    AbstractVectorStore,
    AbstractFlexiSchemaFields,
    AbstractFlexiSchema,
)
from orchestrators.doc.vector_stores.factories import FACTORIES as V_FACTORIES
from orchestrators.doc.embedding_models.embedding import BaseEmbedding
from orchestrators.doc.embedding_models.model_proxy import ModelProxy as EmbeddingsProxy
from orchestrators.chat.messages.prompts import registry
from orchestrators.chat.abstract_bot import AbstractBot
from orchestrators.chat.llm_models.llm import LLM
from orchestrators.chat.llm_models.model_proxy import ModelProxy as LLMProxy
from orchestrators.chat.messages.message_history import (
    MongoMessageHistorySchema,
    MongoMessageHistory,
    SystemMessage,
    HumanMessage,
    AIMessage,
    BaseMessage,
    Sequence,
)

class ChatBot(AbstractBot):
    def __init__(self):
        """Composite parts"""
        self.vector_part: ChatBotBuilder.VectorPart = None
        self.llm_part: ChatBotBuilder.LLMPart = None
        self.prompt_part: ChatBotBuilder.PromptPart = None
        self.message_part: ChatBotBuilder.MessagePart = None
    
    def create_rag_chain(self, llm: BaseChatModel) -> Runnable:
        """Create history-aware Retriever chain (`create_retriever_chain` populates context)"""
        history_aware_retriever = create_history_aware_retriever(
            llm,
            self.vector_part.vector_store.retriever(),
            self.prompt_part.registry['contextualized_template']())
        question_answer_chain = create_stuff_documents_chain(llm, self.prompt_part.registry['qa_template']())
        return create_retrieval_chain(history_aware_retriever, question_answer_chain)
    
    def multi_doc_rag_chain(self):
        self.vector_part.vector_store.retriever(filter_expression=self._vector_store.flexi_schema.get_all_filters())
        pass

    def create_llm_chain(self, llm: BaseChatModel) -> Runnable:
        chain = self.prompt_part.registry['chat_history_template']() | llm
        return chain

    def _trace_history_chain(self) -> None:
        def _historic_messages_by(n: int) -> List[BaseMessage]:
            messages = self.message_part.message_history.messages[-n:]
            logging.warning(f'Message History {messages}')
            return messages
        runnable = RunnableLambda(
            _historic_messages_by).with_config(run_name='trace_my_history')
        runnable.invoke(20)

    async def _aenter_chat_chain(self, run: Run, config: RunnableConfig) -> Optional[SystemMessage]:
        """On start runnable listener"""
        logging.warning(f'WE SHOULD HAVE ENTERED HERE _aenter')
        collection = self.message_part.message_history.chat_message_history.collection
        if(
            _ := collection.find_one(
                {
                    'type': 'system', 
                    'content': self.prompt_part.user_prompt, 
                    'conversation_id': config['configurable']['session_id']})
        ) is None:
            await self.message_part.add_system_message(self.prompt_part.user_prompt)

    async def _aexit_chat_chain(self, run: Run, config: RunnableConfig) -> None:
        """On end runnable listener"""
        collection = self.message_part.message_history.chat_message_history.collection
        if(
            ai_message := collection.find_one(
                {
                    'type': { '$in': ['ai', 'AIMessageChunk'] }, 
                    'conversation_id': config['configurable']['session_id']
                }, 
                sort=[("createdAt", DESCENDING)])
        ) is not None:
            chain = self.prompt_part.registry['summarization_template']() | self.llm_part.llm.summary_object
            summary = await chain.ainvoke({'input': ai_message['content']})
            self.message_part.message_history.chat_message_history.add_summary(summary.content)

    async def rag_astream(self, chat_llm: BaseChatModel, message: str):
        chain = self.create_rag_chain(chat_llm)
        chain_with_history = self.message_part.message_history.get(chain, True)
        chain_with_history = chain_with_history.with_alisteners(
            on_start=self._aenter_chat_chain,
            on_end=self._aexit_chat_chain)
        config = self.message_part.runnable_config
        async def llm_astream():
            stop_token = "<|eot_id|>"
            async for s in chain_with_history.astream(
                {'input': message},
                config=config):
                if 'answer' in s:
                    s_content = s['answer']
                    if stop_token in s_content:
                        s_content = s_content.replace(stop_token, "")

                    yield s_content
        return llm_astream

    async def chat_astream(self, chat_llm: BaseChatModel, message: str):
        chain = self.create_llm_chain(chat_llm)
        chain_with_history = self.message_part.message_history.get(chain, False)
        chain_with_history = chain_with_history.with_alisteners(
            on_start=self._aenter_chat_chain,
            on_end=self._aexit_chat_chain)
        config = self.message_part.runnable_config
        async def llm_astream():
            stop_token = "<|eot_id|>"
            async for s in chain_with_history.astream(
                {'input': message},
                config=config):
                    # Remove the stop token if it's present
                    if stop_token in s.content:
                        s.content = s.content.replace(stop_token, "")
                    yield s.content
        return llm_astream

    # TODO: add trimmer runnable  
    async def astream(self, message: str) -> Callable[[], AsyncGenerator[str, None]]:
        """Invoke the chain"""
        await self.vector_part.vector_store.inspect(message)
        self._trace_history_chain()
        chat_llm = self.llm_part.llm.endpoint_object
        # TODO: QUERY VECTOR DB BY uuid and conversation_id and then check the metadata (specifically the source attribute)
        # if it has no source, then not rag altogether; if it has one source, then follow the existing rag function, but if two documents,
        # then that's the functionality that needs to be added now.
        rag_chain = await self.vector_part.aavailable_vectors(message)
        return await self.rag_astream(chat_llm, message) if rag_chain else await self.chat_astream(chat_llm, message)

    chat = astream

class ChatBotBuilder:
    def __init__(self, chat_bot: ChatBot):
        self.chat_bot = chat_bot

    class VectorPart:
        def __init__(
            self, 
            chat_bot: ChatBot, 
            store: str,
            ingestors: Any,
            embeddings: List[BaseEmbedding], 
            metadata: List[AbstractFlexiSchemaFields]):
            if store not in V_FACTORIES.keys():
                raise ValueError(f'Vector Store {store} is not supported')
            self.embeddings = EmbeddingsProxy(embeddings).get()
            self.vector_store: AbstractVectorStore = V_FACTORIES[store](self.embeddings, metadata)
            self.ingestors = ingestors
            chat_bot.vector_part = self
    
        async def aavailable_vectors(self, context):
            """Async Available Vector Search"""
            vectors = await self.vector_store.asimilarity_search(context)
            count = len(vectors)
            return count > 0

    class LLMPart:
        def __init__(
            self, 
            chat_bot: ChatBot, 
            llm: List[LLM]):
            self.llm = LLMProxy(llm).get()
            chat_bot.llm_part = self

    class PromptPart:
        def __init__(
            self, 
            chat_bot: ChatBot, 
            user_prompt: str):
            self.user_prompt = user_prompt
            self.registry = registry
            chat_bot.prompt_part = self

    class MessagePart:
        def __init__(self, chat_bot: ChatBot, history_config: dict, configurable: dict):
            if not configurable['session_id']:
                raise ValueError('Session ID Required for History')
            self.configurable = configurable
            message_schema = MongoMessageHistorySchema(
                session_id=self.configurable['session_id'], 
                **history_config)
            self.message_history = MongoMessageHistory(message_schema)
            chat_bot.message_part = self

        @property
        def runnable_config(self) -> dict:
            return {
                'configurable': self.configurable
            }

        async def add_system_message(self, message: str) -> SystemMessage:
            """Add system message to data store"""
            system_message = await self.message_history.system(message)
            return system_message

        async def add_human_message(self, message: dict) -> HumanMessage:
            """add human message to data store"""
            human_message = await self.message_history.human(message)
            return human_message

        async def add_ai_message(self, message: str) -> AIMessage:
            """Add ai message to data store"""
            ai_message = await self.message_history.ai(message)
            return ai_message
        
        async def add_bulk_messages(self, messages: Sequence[BaseMessage]) -> True:
            """Store messages in bulk in data store"""
            return await self.message_history.bulk_add(messages)

    def build_vector_part(
        self, 
        store: str,
        ingestors: Any,
        embeddings: List[LLM], 
        metadata: List[AbstractFlexiSchemaFields]):
        return ChatBotBuilder.VectorPart(self.chat_bot, store, ingestors, embeddings, metadata)
    
    def build_llm_part(self, llm: List[LLM]):
        return ChatBotBuilder.LLMPart(self.chat_bot, llm)
    
    def build_prompt_part(self, user_prompt: str):
        return ChatBotBuilder.PromptPart(self.chat_bot, user_prompt)

    def build_message_part(self, history_config: dict, configurable: dict):
        return ChatBotBuilder.MessagePart(self.chat_bot, history_config, configurable)