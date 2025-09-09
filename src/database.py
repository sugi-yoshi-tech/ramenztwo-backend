# database.py
import os
from contextlib import contextmanager
from typing import List, Optional, Dict

import psycopg2
from psycopg2.extras import DictCursor

# models.pyからインポート
from .models import Company, PressRelease


@contextmanager
def get_db_connection():
    """データベース接続を管理するコンテキストマネージャ"""
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT", 5432),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            dbname=os.getenv("DB_NAME"),
        )
        yield conn
    except psycopg2.OperationalError as e:
        print(f"DB接続エラー: {e}")
        raise
    finally:
        if "conn" in locals() and conn:
            conn.close()

# ★★★★★ 単一記事取得用の関数 (ここから追加) ★★★★★
def db_get_release_by_id(release_id: int) -> Optional[Dict]:
    """DBから特定のIDを持つプレスリリースを1件取得する"""
    query = """
        SELECT c.company_name, r.* FROM release r 
        JOIN company c ON r.company_id = c.company_id 
        WHERE r.release_id = %s;
    """
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute(query, (release_id,))
            row = cur.fetchone()
            return dict(row) if row else None
# ★★★★★ ここまで追加 ★★★★★


def db_get_companies(keyword: Optional[str] = None) -> List[Company]:
    """DBから企業一覧を取得する。キーワード検索に対応。"""
    query = "SELECT * FROM company"
    params = []
    if keyword:
        query += " WHERE company_name ILIKE %s OR description ILIKE %s"
        params.extend([f"%{keyword}%", f"%{keyword}%"])
    query += " ORDER BY company_id;"

    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            return [Company(**row) for row in rows]


def db_get_releases_by_company(
    company_id: int,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    keyword: Optional[str] = None,
) -> List[PressRelease]:
    """DBから指定された企業のプレスリリース一覧を取得する。"""
    query = "SELECT c.company_name, r.* FROM release r JOIN company c ON r.company_id = c.company_id WHERE r.company_id = %s"
    params = [company_id]

    if from_date:
        query += " AND r.created_at >= %s"
        params.append(from_date)
    if to_date:
        query += " AND r.created_at <= %s"
        params.append(to_date)
    if keyword:
        query += " AND (r.title ILIKE %s OR r.body ILIKE %s)"
        params.extend([f"%{keyword}%", f"%{keyword}%"])

    query += " ORDER BY r.created_at DESC;"

    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            return [PressRelease(**row) for row in rows]


def db_get_all_releases_for_similarity() -> List[dict]:
    """類似度計算用に、DBから全リリースのIDとタイトルを取得"""
    query = "SELECT release_id, title, company_name, url, created_at FROM release JOIN company ON release.company_id = company.company_id WHERE title IS NOT NULL;"
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute(query)
            return [dict(row) for row in cur.fetchall()]