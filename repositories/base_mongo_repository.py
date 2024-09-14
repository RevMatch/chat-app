import logging
from typing import List, Dict, Any, Optional
from pymongo import ReturnDocument
from motor.motor_asyncio import AsyncIOMotorCollection
from clients.mongo_strategy import mongo_instance as instance
from models.mongo_schema import ObjectId
from models.abstract_model import AbstractModel
from models.mongo_schema import ChatSchema
from pydantic import BaseModel

def base_mongo_factory(model: AbstractModel):
    """Abstract the data storage and retrieval logic from the business logic of the application using first-class object BaseMongoRepository"""
    class BaseMongoRepository:
        @staticmethod
        def get_collection() -> AsyncIOMotorCollection:
            """Get the collection associated with Pydantic model"""
            return instance.get_database().get_collection(model.get_model_name())
        
        @classmethod
        async def all(cls, *, options: Optional[dict] = {}, offset: int = 0, limit: int = 20) -> List[Dict[str, Any]]:
            """Fetch all documents in database filtered by user, limit, and offset"""
            return await cls.get_collection().find(options).skip(offset).limit(limit).to_list(limit)

        @classmethod
        async def create(cls, *, schema: ChatSchema = BaseModel,  options: Optional[dict] = {}) -> Dict[str, Any]:
            """Create document"""
            insert_data = {**schema.model_dump(by_alias=True), **options}
            new_document = await cls.get_collection().insert_one(insert_data)
            return await cls.find_one(new_document.inserted_id)
        
        @classmethod
        async def find(cls, id: str = None, *, options: dict = {}) -> List[Dict[str, Any]]:
            """"Find documents by filter"""
            query = {"_id": ObjectId(id)} if id else {} 
            return await cls.get_collection().find({**query, **options})
        
        @classmethod
        async def find_one(cls, id: str = None, *, options: dict = {}) -> Dict[str, Any]:
            """"Find a document by filter"""
            query = {"_id": ObjectId(id)} if id else {} 
            return await cls.get_collection().find_one({**query, **options})
        
        @classmethod
        async def count(cls, *, options: dict = {}) -> int:
            """"Count number of documents in filter"""
            return await cls.get_collection().count_documents(options)

        @classmethod
        async def update(cls, id: str, *, schema: ChatSchema = ChatSchema, options: dict = {}):
            """"Update a document"""
            # keep only fields with values
            document = {
                k: v for k, v in schema.model_dump(by_alias=True).items() if v is not None
            }
            if len(document) >= 1:
                update_result = await cls.get_collection().find_one_and_update(
                    {"_id": ObjectId(id), **options},
                    {"$set": document},
                    return_document=ReturnDocument.AFTER,
                )
            return update_result
        
        @classmethod
        async def update_one(cls, *, options: dict, assigns: dict):
            return await cls.get_collection().update_one(options, { '$set': assigns})

        @classmethod
        async def delete(cls, id: str, *, options: Optional[dict] = {}) -> bool:
            """"Delete a document"""
            delete_result = await cls.get_collection().delete_one({"_id": ObjectId(id), **options})
            if delete_result.deleted_count == 1:
                return True
            return False
        
        @classmethod
        async def sync(cls, *, options: dict, source: List[ChatSchema], attribute: str, identifier: str) -> List[dict]:
            """Synchronize an array of documents in data store with a specified data source"""
            def key_in_dicts(key, dicts):
                return any(d.get(identifier) == key for d in dicts)
            
            source = [ { **config.model_dump(by_alias=True) } for config in source]
            document = await cls.find_one(options=options)
            if document and attribute in document:
                target = document[attribute]
            else:
                target = []
            target_dicts = {config[identifier]: config for config in target}
            for config in source:
                if not key_in_dicts(config[identifier], target):
                    target_dicts[config[identifier]] = config
            target_dicts = {name: config for name, config in target_dicts.items() if name in [c[identifier] for c in source]}
            sync_attributes = list(target_dicts.values())
            await cls.update_one(options=options, assigns={attribute: sync_attributes})
            return sync_attributes

    BaseMongoRepository.model = model
    return BaseMongoRepository