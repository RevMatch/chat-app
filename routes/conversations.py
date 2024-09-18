import logging
import asyncio
from typing import Annotated, List, Optional
from fastapi import APIRouter, status, Request, Query, Body, Form, Depends, File, UploadFile, logger
from auth.bearer_authentication import get_current_user
from models.mongo_schema import ObjectId
from routes.chats import get_current_models, get_prompt_template, get_message_history, chat
from routes.uploads import ingest_file
from orchestrators.chat.llm_models.llm import LLM
from repositories.conversation_mongo_repository import ConversationMongoRepository as ConversationRepo
from models.conversation import (
    ConversationSchema,
    ConversationCollectionSchema, 
    UpdateConversationSchema,
)
from models.message import MessageSchema, BaseMessageSchema
from fastapi.responses import StreamingResponse

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
    # response_model=CreatedMessageSchema,
    status_code=status.HTTP_201_CREATED,
    response_model_by_alias=False,
)
async def create_conversation(
    request: Request,
    uuid: str = Form(...),
    title: str = Form(...),
    content: str = Form(...),
    # conversation: Annotated[ConversationSchema, Form()],
    # message: Annotated[MessageSchema, Form()],
    models: List[LLM] = Depends(get_current_models), 
    prompt_template: str = Depends(get_prompt_template),
    upload_file: Optional[UploadFile] = File(None)):
    """Insert new conversation record and message record in configured database, returning AI Response"""
    conversation_schema = ConversationSchema(uuid=uuid, title=title)
    message_schema = MessageSchema(History=BaseMessageSchema(content=content, type='human'))
    conversation_schema.uuid = request.state.uuid

    if (
        created_conversation_id := await ConversationRepo.create(conversation_schema=conversation_schema)
    ) is not None:
        if upload_file:
            await ingest_file(request.state.uuid, upload_file, created_conversation_id)
        metadata = { 'uuid': conversation_schema.uuid, 'conversation_id': created_conversation_id }
        run_llm, streaming_handler = await chat(
            prompt_template, 
            models, 
            metadata,
            message_schema)
        asyncio.create_task(asyncio.to_thread(run_llm))
        return StreamingResponse(streaming_handler.get_streamed_response(), media_type="text/plain")
        
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
        updated_conversation := await ConversationRepo.update_one(options={'_id': ObjectId(id), request.state.uuid_name: request.state.uuid}, assigns=dict(conversation_schema))
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