"""
Retriever - 检索器模块

实现多种检索策略：语义检索、关键词检索、混合检索。
"""

import re
from typing import Optional
from dataclasses import dataclass

from rag.vector_store import VectorStore


@dataclass
class RetrievalResult:
    """检索结果"""
    id: str
    content: str
    metadata: dict
    score: float
    source_type: str  # semantic | keyword | hybrid


class Retriever:
    """知识检索器"""

    def __init__(self, vector_store: VectorStore = None):
        self.store = vector_store or VectorStore()

    def retrieve(
        self,
        query: str,
        domain: Optional[str] = None,
        chunk_type: Optional[str] = None,
        n_results: int = 5
    ) -> list[RetrievalResult]:
        """通用检索"""
        where = {}
        if domain:
            where["domain"] = domain
        if chunk_type:
            where["type"] = chunk_type

        results = self.store.search(
            query=query,
            n_results=n_results,
            where=where if where else None
        )

        return [
            RetrievalResult(
                id=r["id"],
                content=r["content"],
                metadata=r["metadata"],
                score=1 - (r["distance"] or 0),
                source_type="semantic"
            )
            for r in results
        ]

    def retrieve_for_derivation(
        self,
        variable_name: str,
        algorithm: str,
        domain: Optional[str] = None,
        n_results: int = 5
    ) -> list[RetrievalResult]:
        """为衍生变量生成检索相关代码"""
        # 构建查询
        query = f"Variable: {variable_name}\nAlgorithm: {algorithm}"

        results = []

        # 1. 语义检索相似算法实现
        semantic_results = self.retrieve(
            query=algorithm,
            domain=domain,
            chunk_type="sas_code",
            n_results=n_results
        )
        results.extend(semantic_results)

        # 2. 检索相似变量处理
        spec_results = self.retrieve(
            query=query,
            domain=domain,
            chunk_type="spec_variable",
            n_results=3
        )
        results.extend(spec_results)

        # 3. 去重并排序
        seen = set()
        unique_results = []
        for r in results:
            if r.id not in seen:
                seen.add(r.id)
                unique_results.append(r)

        return sorted(unique_results, key=lambda x: -x.score)[:n_results * 2]

    def retrieve_macro(
        self,
        macro_name: str,
        n_results: int = 3
    ) -> list[RetrievalResult]:
        """检索宏定义"""
        return self.retrieve(
            query=f"macro {macro_name}",
            chunk_type="macro",
            n_results=n_results
        )

    def retrieve_by_variables(
        self,
        variables: list[str],
        domain: Optional[str] = None,
        n_results: int = 5
    ) -> list[RetrievalResult]:
        """根据变量名检索相关代码"""
        query = " ".join(variables)
        return self.retrieve(
            query=query,
            domain=domain,
            chunk_type="sas_code",
            n_results=n_results
        )

    def hybrid_search(
        self,
        query: str,
        keywords: list[str],
        domain: Optional[str] = None,
        n_results: int = 5
    ) -> list[RetrievalResult]:
        """混合检索：语义 + 关键词"""
        # 语义检索
        semantic_results = self.retrieve(
            query=query,
            domain=domain,
            n_results=n_results * 2
        )

        # 关键词过滤/增强
        keyword_matches = []
        for result in semantic_results:
            content_lower = result.content.lower()
            keyword_score = sum(1 for kw in keywords if kw.lower() in content_lower)
            if keyword_score > 0:
                result.score += keyword_score * 0.1
                result.source_type = "hybrid"
            keyword_matches.append(result)

        # 重新排序
        return sorted(keyword_matches, key=lambda x: -x.score)[:n_results]


class CodeRetriever(Retriever):
    """SAS 代码检索器"""

    def find_similar_data_step(
        self,
        description: str,
        domain: Optional[str] = None,
        n_results: int = 3
    ) -> list[RetrievalResult]:
        """查找相似的 DATA 步实现"""
        return self.retrieve(
            query=f"data step {description}",
            domain=domain,
            n_results=n_results
        )

    def find_merge_logic(
        self,
        domains: list[str],
        n_results: int = 3
    ) -> list[RetrievalResult]:
        """查找跨域合并逻辑"""
        query = f"merge {' '.join(domains)} cross-domain"
        return self.retrieve(
            query=query,
            n_results=n_results
        )

    def find_date_derivation(
        self,
        date_type: str = "dtc",
        n_results: int = 3
    ) -> list[RetrievalResult]:
        """查找日期衍生逻辑"""
        return self.retrieve(
            query=f"date derivation {date_type} dtc",
            chunk_type="sas_code",
            n_results=n_results
        )

    def find_conditional_logic(
        self,
        condition_description: str,
        domain: Optional[str] = None,
        n_results: int = 3
    ) -> list[RetrievalResult]:
        """查找条件逻辑实现"""
        keywords = ["if", "then", "else", "select", "when"]
        return self.hybrid_search(
            query=condition_description,
            keywords=keywords,
            domain=domain,
            n_results=n_results
        )


class SpecRetriever(Retriever):
    """SPEC 变量检索器"""

    def find_similar_variable(
        self,
        variable_name: str,
        algorithm_hint: str = None,
        n_results: int = 5
    ) -> list[RetrievalResult]:
        """查找相似变量的处理方式"""
        query = f"variable {variable_name}"
        if algorithm_hint:
            query += f" {algorithm_hint}"

        return self.retrieve(
            query=query,
            chunk_type="spec_variable",
            n_results=n_results
        )

    def find_algorithm_pattern(
        self,
        algorithm: str,
        n_results: int = 5
    ) -> list[RetrievalResult]:
        """查找相似算法模式"""
        return self.retrieve(
            query=algorithm,
            chunk_type="spec_variable",
            n_results=n_results
        )


if __name__ == "__main__":
    # 测试
    retriever = Retriever()
    results = retriever.retrieve("AE outcome derivation", domain="AE", n_results=3)
    for r in results:
        print(f"ID: {r.id}, Score: {r.score:.3f}")
        print(f"Content preview: {r.content[:100]}...")
        print()
