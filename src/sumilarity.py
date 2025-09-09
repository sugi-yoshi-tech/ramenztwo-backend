# similarity.py

import os
import torch
import numpy as np
from typing import List, Dict
import asyncio
from sentence_transformers import SentenceTransformer
from huggingface_hub import login

from .database import db_get_all_releases_for_similarity
from .models import SimilarRelease

# --- グローバル変数 ---
EMBEDDING_MODEL_ID = "google/embeddinggemma-300M"
embedding_model: SentenceTransformer = None # モデルをグローバル変数として保持

# キャッシュ
release_vectors_cache: Dict[int, np.ndarray] = {}
all_releases_cache: List[Dict] = []

def load_embedding_model():
    """
    アプリケーション起動時にEmbeddingGemmaモデルをロードする
    """
    global embedding_model
    if embedding_model is None:
        print("EmbeddingGemmaモデルをロードしています...")
        
        hf_token = os.getenv("HUGGING_FACE_TOKEN")
        if not hf_token:
            raise ValueError("HUGGING_FACE_TOKENが.envファイルに設定されていません。")
        login(token=hf_token)

        device = "cuda" if torch.cuda.is_available() else "cpu"
        embedding_model = SentenceTransformer(EMBEDDING_MODEL_ID).to(device=device)
        print(f"モデルのロード完了。デバイス: {device}")

def get_embeddings_batch(texts: List[str]) -> List[np.ndarray]:
    """
    テキストのリストをまとめてベクトル化する (同期的)
    """
    if embedding_model is None:
        raise RuntimeError("Embeddingモデルがロードされていません。")
    
    embeddings = embedding_model.encode(
        texts,
        prompt_name="Retrieval-document"
    )
    return [np.array(emb) for emb in embeddings]

def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """コサイン類似度を計算する"""
    if np.linalg.norm(vec1) == 0 or np.linalg.norm(vec2) == 0:
        return 0.0
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

async def find_similar_releases(
    target_release_id: int, target_title: str, top_k: int = 5
) -> List[SimilarRelease]:
    """
    EmbeddingGemmaを使って類似したプレスリリースを検索する
    """
    global all_releases_cache, release_vectors_cache

    if not all_releases_cache:
        print("DBから全リリース情報を取得します...")
        all_releases_cache = db_get_all_releases_for_similarity()

    target_vector = (await asyncio.to_thread(get_embeddings_batch, [target_title]))[0]

    releases_to_embed_titles = [
        r["title"] for r in all_releases_cache 
        if r["release_id"] not in release_vectors_cache
    ]
    releases_to_embed_ids = [
        r["release_id"] for r in all_releases_cache
        if r["release_id"] not in release_vectors_cache
    ]

    if releases_to_embed_titles:
        print(f"{len(releases_to_embed_titles)}件のタイトルをベクトル化します...")
        new_vectors = await asyncio.to_thread(get_embeddings_batch, releases_to_embed_titles)
        for rel_id, vector in zip(releases_to_embed_ids, new_vectors):
            release_vectors_cache[rel_id] = vector
        print("ベクトル化が完了しました。")

    similarities = []
    for release_data in all_releases_cache:
        if release_data["release_id"] == target_release_id:
            continue
        
        vec = release_vectors_cache.get(release_data["release_id"])
        if vec is not None:
            sim = cosine_similarity(target_vector, vec)
            similarities.append((sim, release_data))

    similarities.sort(key=lambda x: x[0], reverse=True)
    
    top_releases = []
    for sim_score, rel_data in similarities[:top_k]:
        top_releases.append(
            SimilarRelease(
                release_id=rel_data['release_id'],
                title=rel_data['title'],
                company_name=rel_data.get('company_name'),
                url=rel_data.get('url'),
                created_at=rel_data.get('created_at'),
                similarity_score=sim_score
            )
        )
    return top_releases