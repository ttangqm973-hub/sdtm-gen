"""
Embedder - 向量化模块

支持 OpenAI 和本地 Embedding 模型。
"""

import os
import hashlib
import json
from pathlib import Path
from typing import Optional
from dataclasses import asdict

# 延迟导入，避免未安装时报错
_embedding_model = None


def get_embedder(model_type: str = "openai", model_name: str = None, use_mock: bool = False):
    """获取 Embedder 实例"""
    if use_mock or model_type == "mock":
        return MockEmbedder()
    if model_type == "openai":
        return OpenAIEmbedder(model_name or "text-embedding-3-small")
    elif model_type == "local":
        return LocalEmbedder(model_name or "BAAI/bge-large-zh-v1.5")
    else:
        raise ValueError(f"Unknown model type: {model_type}")


class BaseEmbedder:
    """Embedder 基类"""

    def __init__(self, model_name: str):
        self.model_name = model_name
        self.cache_dir = Path("d:/Claude code/sdtm_gen/knowledge/embedding_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def embed(self, text: str) -> list[float]:
        """生成文本的向量表示"""
        raise NotImplementedError

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量生成向量"""
        return [self.embed(text) for text in texts]

    def _get_cache_key(self, text: str) -> str:
        """生成缓存键"""
        content = f"{self.model_name}:{text}"
        return hashlib.md5(content.encode()).hexdigest()

    def _load_cache(self, cache_key: str) -> Optional[list[float]]:
        """加载缓存"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            with open(cache_file, 'r') as f:
                return json.load(f)
        return None

    def _save_cache(self, cache_key: str, embedding: list[float]):
        """保存缓存"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        with open(cache_file, 'w') as f:
            json.dump(embedding, f)


class OpenAIEmbedder(BaseEmbedder):
    """OpenAI Embedding"""

    def __init__(self, model_name: str = "text-embedding-3-small"):
        super().__init__(model_name)
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        return self._client

    def embed(self, text: str) -> list[float]:
        cache_key = self._get_cache_key(text)
        cached = self._load_cache(cache_key)
        if cached:
            return cached

        response = self.client.embeddings.create(
            input=text,
            model=self.model_name
        )
        embedding = response.data[0].embedding
        self._save_cache(cache_key, embedding)
        return embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量生成向量（更高效）"""
        results = []
        uncached_texts = []
        uncached_indices = []

        for i, text in enumerate(texts):
            cache_key = self._get_cache_key(text)
            cached = self._load_cache(cache_key)
            if cached:
                results.append((i, cached))
            else:
                uncached_texts.append(text)
                uncached_indices.append(i)

        if uncached_texts:
            response = self.client.embeddings.create(
                input=uncached_texts,
                model=self.model_name
            )
            for idx, data in enumerate(response.data):
                embedding = data.embedding
                text = uncached_texts[idx]
                cache_key = self._get_cache_key(text)
                self._save_cache(cache_key, embedding)
                results.append((uncached_indices[idx], embedding))

        results.sort(key=lambda x: x[0])
        return [e for _, e in results]


class LocalEmbedder(BaseEmbedder):
    """本地 Embedding 模型"""

    def __init__(self, model_name: str = "BAAI/bge-large-zh-v1.5"):
        super().__init__(model_name)
        self._model = None
        self._tokenizer = None

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed(self, text: str) -> list[float]:
        cache_key = self._get_cache_key(text)
        cached = self._load_cache(cache_key)
        if cached:
            return cached

        embedding = self.model.encode(text, normalize_embeddings=True)
        embedding_list = embedding.tolist()
        self._save_cache(cache_key, embedding_list)
        return embedding_list

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量生成向量"""
        results = []
        uncached_texts = []
        uncached_indices = []

        for i, text in enumerate(texts):
            cache_key = self._get_cache_key(text)
            cached = self._load_cache(cache_key)
            if cached:
                results.append((i, cached))
            else:
                uncached_texts.append(text)
                uncached_indices.append(i)

        if uncached_texts:
            embeddings = self.model.encode(uncached_texts, normalize_embeddings=True)
            for idx, embedding in enumerate(embeddings):
                embedding_list = embedding.tolist()
                text = uncached_texts[idx]
                cache_key = self._get_cache_key(text)
                self._save_cache(cache_key, embedding_list)
                results.append((uncached_indices[idx], embedding_list))

        results.sort(key=lambda x: x[0])
        return [e for _, e in results]


class MockEmbedder(BaseEmbedder):
    """Mock Embedder（用于测试，无需 API）"""

    def __init__(self):
        super().__init__("mock-embedder")

    def embed(self, text: str) -> list[float]:
        """基于文本生成伪向量"""
        hash_obj = hashlib.md5(text.encode())
        hash_bytes = hash_obj.digest()
        # 生成 128 维向量
        vector = []
        for i in range(16):
            for j in range(8):
                val = (hash_bytes[i] >> j) & 1
                vector.append(float(val) * 2 - 1)  # -1 或 1
        # 归一化
        norm = sum(x * x for x in vector) ** 0.5
        return [x / norm for x in vector]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]


if __name__ == "__main__":
    # 测试
    embedder = get_embedder("openai")
    text = "Hello, world!"
    embedding = embedder.embed(text)
    print(f"Embedding dimension: {len(embedding)}")
    print(f"First 5 values: {embedding[:5]}")
