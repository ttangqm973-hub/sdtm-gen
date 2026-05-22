"""
Simple Vector Store - 简单向量存储（无外部依赖）

使用 JSON 文件存储向量，适用于测试和小规模场景。
"""

import json
from pathlib import Path
from typing import Optional
from dataclasses import asdict

from rag.knowledge_processor import KnowledgeChunk
from rag.embedder import get_embedder, BaseEmbedder

# numpy 用于向量计算
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


class SimpleVectorStore:
    """简单向量存储"""

    def __init__(
        self,
        persist_dir: str = "d:/Claude code/sdtm_gen/knowledge/simple_store",
        embedding_model: str = "openai",
        embedding_name: str = "text-embedding-3-small"
    ):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        self.embedder = get_embedder(embedding_model, embedding_name)
        self.index_file = self.persist_dir / "index.json"
        self.vectors_file = self.persist_dir / "vectors.npy"

        self.chunks = []
        self.vectors = None

        self._load()

    def _load(self):
        """加载已有数据"""
        if self.index_file.exists():
            with open(self.index_file, 'r', encoding='utf-8') as f:
                self.chunks = json.load(f)

        if self.vectors_file.exists():
            self.vectors = np.load(str(self.vectors_file))

    def _save(self):
        """保存数据"""
        with open(self.index_file, 'w', encoding='utf-8') as f:
            json.dump(self.chunks, f, ensure_ascii=False, indent=2)

        if self.vectors is not None:
            np.save(str(self.vectors_file), self.vectors)

    def add_chunks(self, chunks: list[KnowledgeChunk], collection_name: str = "knowledge") -> int:
        """添加知识块"""
        if not chunks:
            return 0

        # 批量生成向量
        texts = [chunk.content for chunk in chunks]
        embeddings = self.embedder.embed_batch(texts)

        # 添加到存储
        for i, chunk in enumerate(chunks):
            chunk_data = {
                "id": chunk.id,
                "type": chunk.type,
                "source": chunk.source,
                "domain": chunk.domain or "",
                "content": chunk.content,
                "metadata": chunk.metadata
            }
            self.chunks.append(chunk_data)

        # 更新向量
        new_vectors = np.array(embeddings, dtype=np.float32)
        if self.vectors is None:
            self.vectors = new_vectors
        else:
            self.vectors = np.vstack([self.vectors, new_vectors])

        self._save()
        return len(chunks)

    def search(
        self,
        query: str,
        n_results: int = 5,
        where: Optional[dict] = None
    ) -> list[dict]:
        """检索相似知识块"""
        if self.vectors is None or len(self.chunks) == 0:
            return []

        # 生成查询向量
        query_vector = np.array(self.embedder.embed(query), dtype=np.float32)

        # 过滤符合条件的块
        filtered_indices = []
        for i, chunk in enumerate(self.chunks):
            if where:
                match = True
                for key, value in where.items():
                    if chunk.get(key) != value:
                        match = False
                        break
                if not match:
                    continue
            filtered_indices.append(i)

        if not filtered_indices:
            return []

        # 计算余弦相似度
        filtered_vectors = self.vectors[filtered_indices]
        norms = np.linalg.norm(filtered_vectors, axis=1) * np.linalg.norm(query_vector)
        similarities = np.dot(filtered_vectors, query_vector) / (norms + 1e-10)

        # 排序取 top_k
        top_indices = np.argsort(similarities)[::-1][:n_results]

        results = []
        for idx in top_indices:
            original_idx = filtered_indices[idx]
            chunk = self.chunks[original_idx]
            results.append({
                "id": chunk["id"],
                "content": chunk["content"],
                "metadata": {
                    "type": chunk["type"],
                    "source": chunk["source"],
                    "domain": chunk["domain"]
                },
                "distance": 1 - similarities[idx]
            })

        return results

    def delete_all(self):
        """清空所有数据"""
        self.chunks = []
        self.vectors = None
        self._save()

    def count(self) -> int:
        """统计文档数"""
        return len(self.chunks)

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "total_chunks": len(self.chunks),
            "vector_dim": self.vectors.shape[1] if self.vectors is not None else 0
        }


if __name__ == "__main__":
    # 测试
    store = SimpleVectorStore()
    print(f"Stats: {store.get_stats()}")
