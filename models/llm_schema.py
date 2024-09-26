from typing import List, Optional, TypeAlias, TypedDict, Literal
from pydantic import BaseModel, Field
from models.mongo_schema import PrimaryKeyMixinSchema, TimestampMixinSchema, ChatSchema

LLMSchema: TypeAlias = BaseModel

_TextTask = Literal['text-generation', 'text2text-generation', 'summarization', 'translation']

class LLMPrompt(ChatSchema):
    title: str
    content: str

class PromptDict(TypedDict):
    title: str
    content: str

class LLMParamSchema(ChatSchema):
    max_new_tokens: Optional[int] = Field(description='Maximum number of new tokens that model generates in response to prompt', default=1024)
    # Note Stop Sequences is used for the LLM that implements Runnable interface
    stop_sequences: Optional[List[str]] = Field(description='Specify stop sequence that model should use to indicate the end of a response', default_factory=lambda: ["<|eot_id|>"])
    truncate: Optional[int] = Field(description='Truncate generated text to the specified length. If generated text exceeds the specified length, it will be cut off at that point.', default=None)
    do_sample: Optional[bool] = Field(description='Control whether the model should sample from the output probability distribution or not', default=False)
    repetition_penalty: Optional[float] = Field(description='control the repetition of tokens in the generated text', default=1.2)
    top_k: Optional[int] = Field(description='Consider the top k tokens with the highest probability when sampling from the output probability distribution', default=None)
    top_p: Optional[float] = Field(description='Control the probability threshold for sampling from the output probability distribution', default=0.95)
    temperature: Optional[float] = Field(description='Generate output based on a probability distribution that is smoothed by the temperature value', default=0.01)
    # timeout: Optional[int] = Field(description='Set a time limit for the generation of text. If exceeded, model stops generating text', default=120)
    # task: Optional[_TextTask] = Field(description='Text-centric Task', default='text-generation')


class LLMBase(PrimaryKeyMixinSchema, TimestampMixinSchema):
    name: str = Field(description='Model Name')
    description: str = Field(description='Description of the Model', default='Description of TGI Model')
    preprompt: str = Field(description='Default prompt (Note users can create custom ones)', default='')
    parameters: LLMParamSchema = Field(default_factory=LLMParamSchema)
    active: bool = Field(description='Specify if the model is active', default=False)