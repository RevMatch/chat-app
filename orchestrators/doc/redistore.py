import os
from typing import List
from langchain_core.documents import Document
from langchain_redis import RedisConfig as Config, RedisVectorStore as VectorStore
from langchain_core.vectorstores import VectorStoreRetriever
from redisvl.query.filter import Tag
from orchestrators.doc.abstract_vector_store import AbstractVectorStore, VectorStoreRetrieval
from orchestrators.doc.embedding_models.model_proxy import ModelProxy

SCHEMA = [
    {"name": "uuid", "type": "tag"},
    {"name": "conversation_id", "type": "tag"},
]

# Note you cannot reuse the same index for two different embedding models
_config = Config(
    index_name='user_conversations',
    redis_url = os.environ['REDIS_URL'],
    metadata_schema=SCHEMA,
)

class RediStore(AbstractVectorStore):
    def __init__(self, embeddings: ModelProxy, uuid: str, conversation_id: str):
        self._embeddings = embeddings
        self._vector_store = VectorStore(self._embeddings.get().endpoint_object, config=_config)
        # TODO: no need to explicitly define the metadata. Needs to be general solution
        self.uuid = uuid
        self.conversation_id = conversation_id

    async def add(self, documents: List[Document]) -> List[str]:
        """Add documents to the vector store, expecting metadata per document"""
        return await self._vector_store.aadd_documents(documents)
    
    def similarity_search(self, query: str, kwargs) -> List[Document]:
        """Use Cosine Similarity Search to get immediate results"""
        """It's recommended to use runnable instead"""
        filter = (Tag("uuid") == kwargs['uuid']) & (Tag("conversation_id") == str(kwargs['conversation_id']))
        # TODO: change to async vector store
        results = self._vector_store.similarity_search(query, filter=filter)
        return results
    
    def retriever(self, options: VectorStoreRetrieval = VectorStoreRetrieval()) -> VectorStoreRetriever:
        """Generate a retriever which is a runnable to be incorporated in chain"""
        vector_filter = { 
            'uuid': self.uuid, 
            'conversation_id': str(self.conversation_id),
        }
        retriever = self._vector_store.as_retriever(search_type="similarity", k=options.k, score_threshold=options.score_threshold, filter=vector_filter)
        return retriever