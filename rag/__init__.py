"""
RAG Module - 检索增强生成模块

提供知识库向量化、检索和 AI 代码生成能力。
"""

from rag.knowledge_processor import (
    KnowledgeChunk,
    KnowledgeProcessor,
    SASCodeParser,
    MacroParser,
    SpecParser
)
from rag.embedder import (
    get_embedder,
    BaseEmbedder,
    OpenAIEmbedder,
    LocalEmbedder,
    MockEmbedder
)
from rag.vector_store import VectorStore
from rag.retriever import (
    Retriever,
    CodeRetriever,
    SpecRetriever,
    RetrievalResult
)
from rag.generator import (
    CodeGenerator,
    GenerationResult,
    get_generator
)
from rag.pipeline import (
    RAGPipeline,
    create_pipeline
)

# 延迟导入 SDTM IG 解析器
def get_sdtm_ig_parser():
    """获取 SDTM IG 解析器"""
    from rag.sdtm_ig_parser import SDTMIGParser
    return SDTMIGParser()

__all__ = [
    # Knowledge processing
    "KnowledgeChunk",
    "KnowledgeProcessor",
    "SASCodeParser",
    "MacroParser",
    "SpecParser",
    "get_sdtm_ig_parser",

    # Embedding
    "get_embedder",
    "BaseEmbedder",
    "OpenAIEmbedder",
    "LocalEmbedder",
    "MockEmbedder",

    # Vector store
    "VectorStore",

    # Retrieval
    "Retriever",
    "CodeRetriever",
    "SpecRetriever",
    "RetrievalResult",

    # Generation
    "CodeGenerator",
    "GenerationResult",
    "get_generator",

    # Pipeline
    "RAGPipeline",
    "create_pipeline",
]
