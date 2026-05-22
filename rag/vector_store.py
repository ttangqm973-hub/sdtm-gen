"""
Vector Store - 向量存储模块

支持 ChromaDB 和简单文件存储两种模式。
"""

from pathlib import Path
from typing import Optional
from dataclasses import asdict

from rag.knowledge_processor import KnowledgeChunk
from rag.embedder import get_embedder, BaseEmbedder

# 尝试导入 chromadb，失败则使用简单存储
try:
    import chromadb
    from chromadb.config import Settings
    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False


class VectorStore:
    """向量存储管理 - 支持 ChromaDB 和 Simple 两种模式"""

    def __init__(
        self,
        persist_dir: str = "d:/Claude code/sdtm_gen/knowledge/chroma",
        embedding_model: str = "openai",
        embedding_name: str = "text-embedding-3-small",
        use_simple: bool = False
    ):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        self.embedder = get_embedder(embedding_model, embedding_name)
        self.use_simple = use_simple or not HAS_CHROMADB

        if self.use_simple:
            self._init_simple_store()
        else:
            self._init_chroma()

    def _init_simple_store(self):
        """初始化简单存储"""
        from rag.simple_store import SimpleVectorStore
        self._simple_store = SimpleVectorStore(
            persist_dir=str(self.persist_dir.parent / "simple_store")
        )
        # 复用已有的 embedder
        self._simple_store.embedder = self.embedder

    def _init_chroma(self):
        """初始化 ChromaDB"""
        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=Settings(anonymized_telemetry=False)
        )
        self.collections = {}

    def add_chunks(self, chunks: list[KnowledgeChunk], collection_name: str = "knowledge") -> int:
        """添加知识块到向量库"""
        if not chunks:
            return 0

        if self.use_simple:
            return self._simple_store.add_chunks(chunks, collection_name)

        collection = self.get_collection(collection_name)

        # 批量生成向量
        texts = [chunk.content for chunk in chunks]
        embeddings = self.embedder.embed_batch(texts)

        # 准备数据
        ids = [chunk.id for chunk in chunks]
        metadatas = []
        for chunk in chunks:
            meta = {
                "type": chunk.type,
                "source": chunk.source,
                "domain": chunk.domain or "",
            }
            # 添加其他元数据
            for k, v in chunk.metadata.items():
                if isinstance(v, (str, int, float, bool)):
                    meta[f"meta_{k}"] = v
                elif isinstance(v, list):
                    meta[f"meta_{k}"] = ",".join(str(x) for x in v[:10])
            metadatas.append(meta)

        # 添加到集合
        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas
        )

        return len(ids)

    def search(
        self,
        query: str,
        collection_name: str = "knowledge",
        n_results: int = 5,
        where: Optional[dict] = None,
        where_document: Optional[dict] = None
    ) -> list[dict]:
        """检索相似知识块"""
        if self.use_simple:
            return self._simple_store.search(query, n_results, where)

        collection = self.get_collection(collection_name)

        # 生成查询向量
        query_embedding = self.embedder.embed(query)

        # 检索
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            where_document=where_document
        )

        # 格式化结果
        formatted = []
        for i in range(len(results["ids"][0])):
            item = {
                "id": results["ids"][0][i],
                "content": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i] if "distances" in results else None
            }
            formatted.append(item)

        return formatted

    def get_collection(self, name: str):
        """获取或创建集合 (仅 ChromaDB)"""
        if self.use_simple:
            return None
        if name not in self.collections:
            self.collections[name] = self.client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"}
            )
        return self.collections[name]

    def delete_collection(self, name: str):
        """删除集合"""
        if self.use_simple:
            self._simple_store.delete_all()
            return
        try:
            self.client.delete_collection(name)
            if name in self.collections:
                del self.collections[name]
        except Exception:
            pass

    def count(self, collection_name: str = "knowledge") -> int:
        """统计集合中的文档数"""
        if self.use_simple:
            return self._simple_store.count()
        collection = self.get_collection(collection_name)
        return collection.count()

    def get_stats(self) -> dict:
        """获取存储统计"""
        if self.use_simple:
            return self._simple_store.get_stats()
        collections = self.client.list_collections()
        return {
            "collections": [
                {
                    "name": c.name,
                    "count": self.client.get_collection(c.name).count()
                }
                for c in collections
            ]
        }


if __name__ == "__main__":
    # 测试
    store = VectorStore(use_simple=True)
    print(f"Stats: {store.get_stats()}")
