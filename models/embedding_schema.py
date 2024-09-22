from typing import TypeAlias, Literal
from pydantic import BaseModel, Field
from models.mongo_schema import PrimaryKeyMixinSchema, TimestampMixinSchema

EmbeddingSchema: TypeAlias = BaseModel

_TextTask = Literal['feature-extraction']

class EmbeddingBase(PrimaryKeyMixinSchema, TimestampMixinSchema):
    name: str = Field(description='Embedding Model Name')
    description: str = Field(description='Description of the Embedding Model', default='Description of TEI Model')
    task: _TextTask = Field(description='Specify task for what kind of processing or output to use for embedding model', default='feature-extraction')    
    active: bool = Field(description='Specify if the model is active', default=False)