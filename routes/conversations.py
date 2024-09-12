from fastapi import APIRouter, status, Request, Query, Body, Depends, logger
from auth.bearer_authentication import get_current_user
from repositories.conversation_mongo_repository import ConversationMongoRepository as ConversationRepo
from models.conversation import (
    ConversationSchema,
    CreateConversationSchema,
    ConversationCollectionSchema, 
    UpdateConversationSchema,
    ConversationIdSchema,
)

router = APIRouter(
    prefix='/conversations', 
    tags=['conversation'],
    dependencies=[Depends(get_current_user)]
)
@router.get(
    '/',
    response_description='List all conversations',
    response_model=ConversationCollectionSchema,
    response_model_by_alias=False,
)
async def conversations(request: Request, record_offset: int = Query(0, description='record offset', alias='offset'), record_limit: int = Query(20, description="record limit", alias='limit')):
    """List conversations by an offset and limit"""    
    return ConversationCollectionSchema(conversations=await ConversationRepo.all(options={request.state.uuid_name: request.state.uuid}, offset=record_offset, limit=record_limit))

@router.post(
    '/',
    response_description="Add new conversation",
    response_model=ConversationIdSchema,
    status_code=status.HTTP_201_CREATED,
    response_model_by_alias=False,
)
async def create_conversation(request: Request, conversation_schema: ConversationSchema = Body(...)): # CreateConversationSchema
    """Insert new conversation record in configured database, returning resource created"""
    if (
        created_conversation := await ConversationRepo.create(schema=conversation_schema, options={request.state.uuid_name: request.state.uuid})
    ) is not None:
        return { "_id": created_conversation }
    return {'error': f'Conversation not created'}, 400

@router.get(
    '/{id}',
    response_description="Get a single conversation",
    response_model=ConversationSchema,
    response_model_by_alias=False,
)
async def get_conversation(request: Request, id: str):
    """Get conversation record from configured database by id"""
    if (
        found_conversation := await ConversationRepo.find_one(id, options={request.state.uuid_name: request.state.uuid})
    ) is not None:
        return found_conversation
    return {'error': f'Conversation {id} not found'}, 404

@router.put(
    "/{id}",
    response_description="Update a single conversation",
    response_model=ConversationSchema,
    response_model_by_alias=False,
)
async def update_conversation(request: Request, id: str, conversation_schema: UpdateConversationSchema = Body(...)):
    """Update individual fields of an existing conversation record and return modified fields to client."""
    if (
        updated_conversation := await ConversationRepo.update_one(id, schema=conversation_schema, options={request.state.uuid_name: request.state.uuid})
    ) is not None:
        return updated_conversation
    return {'error': f'Conversation {id} not found'}, 404
    
@router.delete(
    '/{id}', 
    response_description='Delete a conversation',
)
async def delete_conversation(request: Request, id: str):
    """Remove a single conversation record from the database."""
    if (
        deleted_conversation := await ConversationRepo.delete(id, options={request.state.uuid_name: request.state.uuid})
    ) is not None:
        return deleted_conversation  
    return { 'error': f'Conversation {id} not found'}, 404