from dataclasses import dataclass
from langchain_huggingface import HuggingFacePipeline
from llm import LLM

@dataclass(frozen=True, kw_only=True, slots=True)
class HFPipelineLLM(LLM):
    pass