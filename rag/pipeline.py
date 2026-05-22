"""
RAG Pipeline - RAG 流水线

整合检索和生成，提供完整的 AI 辅助代码生成能力。
"""

import json
from pathlib import Path
from typing import Optional
from dataclasses import asdict

from rag.knowledge_processor import KnowledgeProcessor, KnowledgeChunk
from rag.embedder import get_embedder
from rag.vector_store import VectorStore
from rag.retriever import Retriever, RetrievalResult
from rag.generator import CodeGenerator, GenerationResult, get_generator


class RAGPipeline:
    """RAG 流水线"""

    def __init__(
        self,
        knowledge_dir: str = "d:/Claude code/sdtm_gen/knowledge",
        knowledge_base_path: str = "D:/Claude code/Knowlegde base",
        embedding_model: str = "openai",
        embedding_name: str = "text-embedding-3-small",
        llm_model: str = "claude-3-5-sonnet",
        use_mock_llm: bool = False
    ):
        self.knowledge_dir = Path(knowledge_dir)
        self.knowledge_base_path = Path(knowledge_base_path)

        # 如果使用 mock LLM，也使用 mock embedding
        use_mock_embedding = use_mock_llm

        self.embedder = get_embedder(embedding_model, embedding_name, use_mock=use_mock_embedding)
        self.vector_store = VectorStore(
            persist_dir=str(self.knowledge_dir / "chroma"),
            embedding_model=embedding_model,
            embedding_name=embedding_name,
            use_simple=True  # 使用简单存储模式
        )
        # 复用同一个 embedder
        if hasattr(self.vector_store, '_simple_store'):
            self.vector_store._simple_store.embedder = self.embedder
        self.retriever = Retriever(self.vector_store)
        self.generator = get_generator(llm_model, use_mock=use_mock_llm)

        self.processor = KnowledgeProcessor(str(knowledge_base_path))

    def build_knowledge_base(self, force_rebuild: bool = False) -> dict:
        """构建/更新知识库"""
        # 检查是否已存在
        current_count = self.vector_store.count("knowledge")
        if current_count > 0 and not force_rebuild:
            return {"status": "exists", "count": current_count}

        # 处理知识库文件
        all_chunks = []

        # SAS 代码
        sas_dir = self.processor.knowledge_base_path / "SAS code"
        if sas_dir.exists():
            for sas_file in sas_dir.glob("*.sas"):
                chunks = self.processor.sas_parser.parse_file(str(sas_file))
                all_chunks.extend(chunks)

        # Macros
        macro_dir = self.processor.knowledge_base_path / "SAS macro"
        if macro_dir.exists():
            for macro_file in macro_dir.glob("*.*"):
                chunks = self.processor.macro_parser.parse_file(str(macro_file))
                all_chunks.extend(chunks)

        # SPEC 模板
        spec_dir = self.processor.knowledge_base_path / "SPEC template"
        if spec_dir.exists():
            for spec_file in spec_dir.glob("*.xlsx"):
                chunks = self.processor.spec_parser.parse_file(str(spec_file))
                all_chunks.extend(chunks)

        # SDTM IG
        sdtm_ig_dir = self.processor.knowledge_base_path / "SDTM IG"
        if sdtm_ig_dir.exists():
            try:
                parser = self.processor._get_sdtm_ig_parser()
                for pdf_file in sdtm_ig_dir.glob("*.pdf"):
                    chunks = parser.parse_file(str(pdf_file))
                    all_chunks.extend(chunks)
                    print(f"Processed SDTM IG: {len(chunks)} chunks")
            except Exception as e:
                print(f"Error processing SDTM IG: {e}")

        # 清空现有数据
        self.vector_store.delete_collection("knowledge")

        # 添加到向量库
        added = self.vector_store.add_chunks(all_chunks, "knowledge")

        return {
            "status": "built",
            "total_chunks": len(all_chunks),
            "added": added
        }

    def retrieve(
        self,
        query: str,
        domain: Optional[str] = None,
        top_k: int = 5
    ) -> list[RetrievalResult]:
        """检索相似代码"""
        return self.retriever.retrieve_for_derivation(
            variable_name="",
            algorithm=query,
            domain=domain,
            n_results=top_k
        )

    def generate(
        self,
        variable_name: str,
        algorithm: str,
        context: dict,
        variable_whitelist: list[str] = None,
        macro_whitelist: list[str] = None
    ) -> GenerationResult:
        """生成衍生变量代码"""
        # 检索相关代码
        retrieved = self.retriever.retrieve_for_derivation(
            variable_name=variable_name,
            algorithm=algorithm,
            domain=context.get("domain"),
            n_results=5
        )

        # 生成代码
        result = self.generator.generate(
            variable_name=variable_name,
            algorithm=algorithm,
            context=context,
            retrieved_chunks=retrieved,
            variable_whitelist=variable_whitelist,
            macro_whitelist=macro_whitelist
        )

        return result

    def generate_with_report(
        self,
        variable_name: str,
        algorithm: str,
        context: dict,
        variable_whitelist: list[str] = None,
        macro_whitelist: list[str] = None
    ) -> dict:
        """生成代码并返回详细报告"""
        result = self.generate(
            variable_name=variable_name,
            algorithm=algorithm,
            context=context,
            variable_whitelist=variable_whitelist,
            macro_whitelist=macro_whitelist
        )

        return {
            "variable_name": variable_name,
            "algorithm": algorithm,
            "generated_code": result.code,
            "confidence": result.confidence,
            "sources": result.sources,
            "warnings": result.warnings,
            "explanation": result.explanation,
            "review_required": result.confidence < 0.8 or len(result.warnings) > 0,
            "review_notes": self._generate_review_notes(result)
        }

    def _generate_review_notes(self, result: GenerationResult) -> list[str]:
        """生成复核建议"""
        notes = []

        if result.confidence < 0.6:
            notes.append("低置信度生成，建议人工检查")

        if result.confidence < 0.8:
            notes.append("建议验证代码逻辑正确性")

        for warning in result.warnings:
            notes.append(f"警告: {warning}")

        if not result.sources:
            notes.append("未找到参考代码，生成可能不准确")

        return notes

    def get_stats(self) -> dict:
        """获取知识库统计"""
        return self.vector_store.get_stats()

    def export_for_template(
        self,
        generation_result: GenerationResult,
        domain: str,
        variable_name: str
    ) -> str:
        """导出为模板格式"""
        code = generation_result.code
        confidence = generation_result.confidence
        review_flag = "REVIEW" if generation_result.confidence < 0.8 else "OK"

        return f"""/* [AI-GEN-START] domain={domain} variable={variable_name} confidence={confidence:.2f} {review_flag} */
{code}
/* [AI-GEN-END] */"""


def create_pipeline(
    knowledge_base_path: str = "D:/Claude code/Knowlegde base",
    use_mock_llm: bool = False
) -> RAGPipeline:
    """创建 RAG 流水线实例"""
    return RAGPipeline(
        knowledge_base_path=knowledge_base_path,
        use_mock_llm=use_mock_llm
    )


if __name__ == "__main__":
    # 测试
    pipeline = create_pipeline(use_mock_llm=True)

    # 构建知识库
    print("Building knowledge base...")
    stats = pipeline.build_knowledge_base()
    print(f"Stats: {stats}")

    # 测试检索
    print("\nRetrieving...")
    results = pipeline.retrieve("AE outcome derivation", domain="AE", top_k=3)
    for r in results:
        print(f"- {r.id}: {r.score:.3f}")

    # 测试生成
    print("\nGenerating...")
    result = pipeline.generate_with_report(
        variable_name="AEREL",
        algorithm="若 AEOUT='FATAL' 则 AEREL='Y'",
        context={"domain": "AE"}
    )
    print(f"Code:\n{result['generated_code']}")
    print(f"Confidence: {result['confidence']}")
