from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
from motor.motor_asyncio import AsyncIOMotorCollection
from bson import ObjectId
from pymongo import ReturnDocument
from chat_client import ChatClient as client
from models.bsonid import PyObjectId
from models.message import MessageModel

class ConversationModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", description='bson object id', default=None)
    title: str = Field(description='title of conversation')
    # rootMessageId: str = Field(description='the root message of the list of messages')
    messages: List[MessageModel] = Field(description='list of messages associated with conversation')
    model: str = Field(description='LLM model name')
    preprompt: Optional[str] = Field(description='preprompt to send to LLM')
    createdAt: datetime = Field(default_factory=datetime.now)
    updatedAt: datetime = Field(default_factory=datetime.now)
    userAgent: Optional[str] = Field(description='browser user agent', default=None)
    embeddingModel: Optional[str] = Field(description='embedding model name', default=None)
    sessionId: str = Field(description='downcased alphanumeric session id (cannot be all numbers)')

    class Config:
        from_attributes = True
        populate_by_name = True
        arbitrary_types_allowed = True

    @field_validator('sessionId')
    def downcase_session_id(cls, value: str):
        return value.lower()
    
class UpdateConversationModel(BaseModel):
    title: Optional[str] = None
    messages: Optional[MessageModel] = None
    updatedAt: datetime
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True

class ConversationCollection(BaseModel):
    conversations: List[ConversationModel]

class ConversationFacade:
    @staticmethod
    def get_collection() -> AsyncIOMotorCollection:
        """Get the collection associated with Pydantic model"""
        return client.instance().db().get_collection('conversations')

    @classmethod
    async def all(cls, limit: int, offset: int) -> List[ConversationModel]:
        """Fetch all conversations in database filtered by a limit and offset"""
        return await cls.get_collection().find().skip(offset).limit(limit).to_list(limit)

    @classmethod
    async def create(cls, conversation: ConversationModel):
        """"Create a new conversation"""
        new_conversation = await cls.get_collection().insert_one(
            conversation.model_dump(by_alias=True, exclude=["id"])
        )
        created_conversation = await cls.get_collection().find_one(
            {"_id": new_conversation.inserted_id}
        )
        return created_conversation
    
    @classmethod
    async def find(cls, id: int) -> ConversationModel:
        """"Find a conversation"""
        await cls.get_collection().find_one({"_id": ObjectId(id)})

    @classmethod
    async def update(cls, id: int, conversation: UpdateConversationModel) -> Optional[ConversationModel]:
        """"Update a conversation"""
        conversation = {
            k: v for k, v in conversation.model_dump(by_alias=True).items() if v is not None
        }
        if len(conversation) >= 1:
            update_result = await cls.get_collection().find_one_and_update(
                {"_id": ObjectId(id)},
                {"$set": conversation},
                return_document=ReturnDocument.AFTER,
            )
            if update_result is not None:
                return update_result
            else:
                return None
    
    @classmethod
    async def delete(cls, id: str) -> bool:
        """"Delete a conversation"""
        delete_result = await cls.get_collection().delete_one({"_id": ObjectId(id)})
        if delete_result.deleted_count == 1:
            return True
        return False