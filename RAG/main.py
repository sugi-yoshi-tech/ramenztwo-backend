# main.py
# ------------------------------------------------------------
# 目的:
#  1) PR TIMES Hackathon API から実データを取得（stg）
#  2) Streamlit アプリと互換（/companies, /companies/{id}/releases, /analyze）
#  3) /analyze に OpenAI を組み込み、RAG文脈を効果的に活用した改善提案
#  4) 全メディアフック項目の評価を保証
#  5) RAG文脈表示用API追加
# ------------------------------------------------------------

import json
import os
import uuid
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from collections import Counter

import httpx
from fastapi import FastAPI, HTTPException, Query, Path, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import BaseModel, Field, field_validator

# OpenAI（任意）
try:
    from openai import AsyncOpenAI
except Exception:
    AsyncOpenAI = None


# =========================
# 設定（pydantic-settings）
# =========================
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # OpenAI（任意）
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o"

    # PR TIMES（必須）
    PRTIMES_TOKEN: str
    PRTIMES_BASE_URL: str = "https://hackathon.stg-prtimes.net/api"

    # CORS
    CORS_ORIGINS: Optional[str | List[str]] = None

    # 任意設定
    OUTPUT_DIR: str = "outputs"
    LLM_TEMPERATURE: float = 0.2
    LLM_MAX_TOKENS: int = 4096

    # 企業取得設定
    DEFAULT_INDUSTRY_ID: int = 5
    MAX_COMPANIES_PER_PAGE: int = 100


settings = Settings()


# ---------------
# ロガー設定
# ---------------
logger = logging.getLogger("app")
logger.setLevel(logging.INFO)
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(_handler)


# ---------------
# FastAPI 準備
# ---------------
app = FastAPI(
    title="PR TIMES RAG API",
    description="プレスリリース取得・分析API - RAG強化版",
    version="2.1.0"
)


def _parse_cors(origins_val: Optional[str | List[str]]) -> List[str]:
    """CORS_ORIGINS は配列/カンマ区切り/JSON文字列のどれでも可。"""
    if origins_val is None:
        return ["*"]
    if isinstance(origins_val, list):
        return origins_val
    val = str(origins_val).strip()
    if val.startswith("["):
        try:
            arr = json.loads(val)
            return [str(x) for x in arr]
        except Exception:
            pass
    return [s.strip() for s in val.split(",") if s.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_cors(settings.CORS_ORIGINS),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------
# アプリ状態
# ---------------
class AppState:
    client: httpx.AsyncClient | None = None
    openai: Any | None = None
    companies_cache: List[Dict[str, Any]] | None = None
    cache_timestamp: datetime | None = None


state = AppState()


@app.on_event("startup")
async def on_startup():
    state.client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0))
    if settings.OPENAI_API_KEY and AsyncOpenAI is not None:
        state.openai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
    logger.info("Startup complete - RAG Enhanced API ready")


@app.on_event("shutdown")
async def on_shutdown():
    if state.client:
        await state.client.aclose()
    logger.info("Shutdown complete")


# ---------------
# 共通ユーティリティ
# ---------------

def auth_headers() -> Dict[str, str]:
    return {
        "Accept": "application/json",
        "Authorization": f"Bearer {settings.PRTIMES_TOKEN}",
    }


def raise_from_httpx(e: httpx.HTTPStatusError, request_id: str):
    """上流HTTPエラーを整形してProxyする。401/403はヒントを追加。"""
    status = e.response.status_code
    try:
        payload = e.response.json()
    except Exception:
        payload = {"message": e.response.text}

    code_map = {
        400: ("BAD_REQUEST", 400),
        401: ("UNAUTHORIZED", 401),
        403: ("FORBIDDEN", 403),
        404: ("NOT_FOUND", 404),
        429: ("RATE_LIMITED", 429),
        500: ("UPSTREAM_ERROR", 502),
        502: ("UPSTREAM_ERROR", 502),
        503: ("UPSTREAM_UNAVAILABLE", 503),
        504: ("UPSTREAM_TIMEOUT", 504),
    }
    code, http = code_map.get(status, ("UPSTREAM_ERROR", 502))

    message = f"PRTIMES upstream returned {status}"
    if status in (401, 403):
        message = "PR TIMES stg への認可に失敗しました。VPN/社内Wi-Fiに接続するか、IP許可を依頼してください。"

    raise HTTPException(
        status_code=http,
        detail={
            "error": {
                "code": code,
                "message": message,
                "upstream": payload,
            },
            "request_id": request_id,
        },
    )


# ===============================
# 業種情報（定数）
# ===============================

INDUSTRIES = {
    1: "商業（卸売業、小売業）",
    2: "飲食店、宿泊業",
    3: "金融・保険業",
    4: "医療、福祉",
    5: "サービス業",
    6: "運輸業",
    7: "製造業",
    8: "IT・通信",
    9: "建設業",
    10: "電気・ガス・熱供給・水道業",
    11: "不動産業",
    12: "教育、学習支援業",
    13: "農業・林業",
    14: "漁業・水産養殖業",
    15: "鉱業",
    16: "その他"
}

CATEGORIES = {
    1: "商品サービス",
    2: "経営・人事",
    3: "企業動向・業績",
    4: "技術・研究開発",
    5: "マーケティング・リサーチ",
    6: "イベント・セミナー",
    7: "キャンペーン",
    8: "提携・M&A",
    9: "ファイナンス",
    10: "アワード・表彰",
    11: "CSR",
    12: "その他"
}


# ===============================
# Pydantic モデル
# ===============================

class Company(BaseModel):
    """企業情報（API仕様準拠）"""
    company_id: int
    company_name: str
    president_name: str
    address: str
    phone: str
    description: str
    industry: str
    ipo_type: str
    capital: int
    foundation_date: str
    url: str
    twitter_screen_name: str


class CategoryReleasesQuery(BaseModel):
    per_page: int = Field(30, ge=1, le=999)
    page: int = Field(0, ge=0, le=99)
    from_date: Optional[str] = Field(None, description="YYYY-MM-DD")
    to_date: Optional[str] = Field(None, description="YYYY-MM-DD")

    @field_validator("from_date", "to_date")
    @classmethod
    def _validate_date(cls, v: Optional[str]):
        if v is None:
            return v
        datetime.strptime(v, "%Y-%m-%d")
        return v


class RAGCategoryRequest(BaseModel):
    """RAG用のリクエスト"""
    per_page: int = Field(30, ge=1, le=999)
    page: int = Field(0, ge=0, le=99)
    from_date: Optional[str] = Field(None, description="YYYY-MM-DD")
    to_date: Optional[str] = Field(None, description="YYYY-MM-DD")
    query: Optional[str] = Field(None, description="検索クエリ（将来実装）")
    top_k: int = Field(10, ge=1, le=100, description="上位K件を返す")
    use_statistics: bool = Field(False, description="統計情報を含める")
    ranking_method: str = Field("like", description="ランキング方法: like, pv(予定), uu(予定), recent")

    @field_validator("from_date", "to_date")
    @classmethod
    def _validate_date2(cls, v: Optional[str]):
        if v is None:
            return v
        datetime.strptime(v, "%Y-%m-%d")
        return v


class ReleaseWithStats(BaseModel):
    """統計情報付きリリース"""
    release: Dict[str, Any]
    statistics: Optional[Dict[str, Any]] = None
    relevance_score: Optional[float] = None


class RAGResponse(BaseModel):
    """RAGレスポンス"""
    request_id: str
    category_id: int
    total_count: int
    filtered_count: int
    releases: List[ReleaseWithStats]
    metadata: Dict[str, Any]


class ImageData(BaseModel):
    """画像データ"""
    url: Optional[str] = Field(None, description="画像URL")


class MetadataInput(BaseModel):
    """メタデータ（ペルソナ情報）"""
    persona: str = Field("指定なし", description="ターゲットペルソナ")


class PressReleaseInput(BaseModel):
    """プレスリリース入力データ（Streamlit互換 + RAG文脈の任意フィールド）"""
    title: str = Field(..., min_length=1, max_length=200, description="記事のタイトル")
    content_markdown: str = Field(..., min_length=1, description="プレスリリース本文（Markdown/HTML）")
    top_image: Optional[ImageData] = Field(None, description="トップ画像")
    metadata: Optional[MetadataInput] = Field(default_factory=MetadataInput)
    # RAG 文脈（任意）
    context_category_id: Optional[int] = Field(None, ge=1)
    context_window_days: int = Field(30, ge=1, le=180)
    context_top_k: int = Field(12, ge=1, le=30)


# ===============================
# コア機能 - API実データ取得
# ===============================

async def fetch_companies_from_api(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """企業一覧をAPIから取得（実際のエンドポイント使用）"""
    url = f"{settings.PRTIMES_BASE_URL}/companies"
    resp = await state.client.get(url, headers=auth_headers(), params=params)
    resp.raise_for_status()
    return resp.json()


async def fetch_all_companies_from_api() -> List[Dict[str, Any]]:
    """
    全企業情報を実際にAPIから取得
    キャッシュを使用（5分間有効）
    ページネーション対応
    """
    # キャッシュチェック
    if state.companies_cache and state.cache_timestamp:
        cache_age = datetime.now() - state.cache_timestamp
        if cache_age < timedelta(minutes=5):
            logger.info("Using cached companies data")
            return state.companies_cache

    logger.info("Fetching companies data from API")
    all_companies: List[Dict[str, Any]] = []
    page = 0
    per_page = 100

    # ページネーションで全企業を取得
    while True:
        try:
            params = {"per_page": per_page, "page": page}
            companies = await fetch_companies_from_api(params)
            
            if not companies:  # 空の場合は終了
                break
                
            all_companies.extend(companies)
            logger.info(f"Fetched page {page}: {len(companies)} companies")
            
            # 100件未満なら最後のページ
            if len(companies) < per_page:
                break
                
            page += 1
            
            # 安全装置（最大20ページまで）
            if page >= 20:
                logger.warning("Reached maximum page limit (20)")
                break
                
        except Exception as e:
            logger.warning(f"Failed to fetch page {page}: {e}")
            break

    # キャッシュ更新
    state.companies_cache = all_companies
    state.cache_timestamp = datetime.now()

    logger.info(f"Total companies fetched: {len(all_companies)}")
    return all_companies


async def fetch_category_releases(
    category_id: int,
    params: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """カテゴリ別リリース取得"""
    url = f"{settings.PRTIMES_BASE_URL}/categories/{category_id}/releases"
    resp = await state.client.get(url, headers=auth_headers(), params=params)
    resp.raise_for_status()
    return resp.json()


async def fetch_company_releases(
    company_id: int,
    params: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """企業別リリース取得"""
    url = f"{settings.PRTIMES_BASE_URL}/companies/{company_id}/releases"
    resp = await state.client.get(url, headers=auth_headers(), params=params)
    resp.raise_for_status()
    return resp.json()


async def fetch_release_statistics(
    company_id: int,
    release_id: int
) -> Optional[Dict[str, Any]]:
    """リリース統計情報取得"""
    try:
        url = f"{settings.PRTIMES_BASE_URL}/companies/{company_id}/releases/{release_id}/statistics"
        resp = await state.client.get(url, headers=auth_headers())
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning(f"Failed to fetch statistics for {company_id}/{release_id}: {e}")
        return None


def rank_releases(
    releases: List[Dict[str, Any]],
    method: str = "like",
    top_k: int = 10
) -> List[Dict[str, Any]]:
    """リリースをランキング"""
    if method == "like":
        sorted_releases = sorted(
            releases,
            key=lambda x: x.get("like", 0),
            reverse=True
        )
    elif method == "recent":
        sorted_releases = sorted(
            releases,
            key=lambda x: x.get("created_at", ""),
            reverse=True
        )
    else:
        sorted_releases = releases

    return sorted_releases[:top_k]


def analyze_category_trends(releases: List[Dict[str, Any]]) -> Dict[str, Any]:
    """カテゴリのトレンド分析"""
    if not releases:
        return {}

    subcategories = Counter()
    companies = Counter()
    total_likes = 0

    for release in releases:
        subcategories[release.get("sub_category_name", "不明")] += 1
        companies[release.get("company_name", "不明")] += 1
        total_likes += release.get("like", 0)

    return {
        "total_releases": len(releases),
        "total_likes": total_likes,
        "avg_likes": total_likes / len(releases) if releases else 0,
        "top_subcategories": dict(subcategories.most_common(5)),
        "top_companies": dict(companies.most_common(5)),
        "date_range": {
            "oldest": min(r.get("created_at", "") for r in releases) if releases else None,
            "newest": max(r.get("created_at", "") for r in releases) if releases else None,
        }
    }


# ===============================
# エンドポイント
# ===============================

@app.get("/")
async def root():
    return {
        "service": "PR TIMES RAG API (Enhanced)",
        "version": "2.1.0",
        "base_url": settings.PRTIMES_BASE_URL,
        "features": [
            "Real-time data from PR TIMES stg API",
            "RAG-enhanced AI analysis",
            "Success pattern learning",
            "Complete media hook evaluation"
        ],
        "endpoints": [
            "GET  /",
            "GET  /healthz",
            "GET  /companies",
            "GET  /industries",
            "GET  /industries/{industry_id}/companies",
            "POST /analyze",
            "GET  /categories/{category_id}/releases",
            "GET  /companies/{company_id}/releases",
            "GET  /companies/{company_id}/releases/{release_id}/statistics",
            "POST /rag/categories/{category_id}",
            "GET  /rag/context/{category_id}",  # 新規追加
            "GET  /debug/config",
            "GET  /debug/cache/clear",
            "GET  /stats/companies/{company_id}",
            "GET  /trending",
            "GET  /categories",
            "GET  /health/detailed",
        ],
    }


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/industries")
async def get_industries():
    """業種一覧取得"""
    return {
        "industries": [
            {"id": k, "name": v} for k, v in INDUSTRIES.items()
        ]
    }


@app.get("/industries/{industry_id}/companies")
async def get_industry_companies(
    industry_id: int = Path(..., ge=1, le=16),
    per_page: int = Query(100, ge=1, le=999),
    page: int = Query(0, ge=0, le=99)
):
    """業種別企業一覧（全企業から業種でフィルタリング）"""
    if state.client is None:
        raise HTTPException(status_code=500, detail={"error": {"code": "BOOTSTRAP", "message": "client not ready"}})

    request_id = str(uuid.uuid4())
    industry_name = INDUSTRIES.get(industry_id, "不明")

    try:
        # 全企業を取得
        all_companies = await fetch_all_companies_from_api()
        
        # 業種でフィルタリング
        industry_companies = [
            c for c in all_companies 
            if c.get("industry") == industry_name
        ]
        
        # ページネーション適用
        start = page * per_page
        end = start + per_page
        paginated = industry_companies[start:end]
        
        return {
            "request_id": request_id,
            "industry_id": industry_id,
            "industry_name": industry_name,
            "total_count": len(industry_companies),
            "count": len(paginated),
            "items": paginated
        }
        
    except httpx.HTTPStatusError as e:
        raise_from_httpx(e, request_id)
    except Exception as e:
        logger.exception("industry companies error")
        raise HTTPException(status_code=500, detail={"error": {"code": "UNEXPECTED", "message": str(e)}, "request_id": request_id})


@app.get("/companies")
async def get_companies():
    """
    企業一覧取得（Streamlit互換）
    実際のAPIからデータを取得（キャッシュあり）
    """
    if state.client is None:
        raise HTTPException(status_code=500, detail={"error": {"code": "BOOTSTRAP", "message": "client not ready"}})

    try:
        # 実際のAPIから企業データを取得
        companies = await fetch_all_companies_from_api()
        # Streamlit互換のフォーマットで返す（シンプルな配列）
        return companies

    except httpx.HTTPStatusError as e:
        request_id = str(uuid.uuid4())
        raise_from_httpx(e, request_id)
    except Exception as e:
        logger.exception("Failed to fetch companies")
        # エラー時は空配列を返す
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": "COMPANIES_FETCH_ERROR",
                    "message": "企業一覧の取得に失敗しました。しばらく待ってから再試行してください。"
                }
            }
        )


@app.get("/categories/{category_id}/releases")
async def get_category_releases(
    category_id: int = Path(..., ge=1),
    per_page: int = Query(30, ge=1, le=999),
    page: int = Query(0, ge=0, le=99),
    from_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    to_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
):
    """カテゴリ別リリース取得API（実データ）"""
    if state.client is None:
        raise HTTPException(status_code=500, detail={"error": {"code": "BOOTSTRAP", "message": "client not ready"}})

    request_id = str(uuid.uuid4())
    params: Dict[str, Any] = {"per_page": per_page, "page": page}
    if from_date:
        params["from_date"] = from_date
    if to_date:
        params["to_date"] = to_date

    try:
        releases = await fetch_category_releases(category_id, params)
        return {
            "request_id": request_id,
            "category_id": category_id,
            "count": len(releases),
            "items": releases
        }
    except httpx.HTTPStatusError as e:
        raise_from_httpx(e, request_id)
    except Exception as e:
        logger.exception("category releases error")
        raise HTTPException(status_code=500, detail={"error": {"code": "UNEXPECTED", "message": str(e)}, "request_id": request_id})


@app.get("/companies/{company_id}/releases")
async def get_company_releases(
    company_id: int = Path(..., ge=1),
    per_page: int = Query(30, ge=1, le=999),
    page: int = Query(0, ge=0, le=99),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
):
    """企業別リリース取得API（実データ、Streamlit互換）"""
    if state.client is None:
        raise HTTPException(status_code=500, detail={"error": {"code": "BOOTSTRAP", "message": "client not ready"}})

    params: Dict[str, Any] = {"per_page": per_page, "page": page}
    if from_date:
        params["from_date"] = from_date
    if to_date:
        params["to_date"] = to_date

    try:
        # 実際のAPIから取得
        releases = await fetch_company_releases(company_id, params)
        return releases  # Streamlit互換のため配列を直接返す

    except httpx.HTTPStatusError as e:
        request_id = str(uuid.uuid4())
        raise_from_httpx(e, request_id)
    except Exception as e:
        logger.exception("company releases error")
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "RELEASES_FETCH_ERROR",
                    "message": f"企業ID {company_id} のリリース取得に失敗しました"
                }
            }
        )


@app.get("/companies/{company_id}/releases/{release_id}/statistics")
async def get_release_statistics(
    company_id: int = Path(..., ge=1),
    release_id: int = Path(..., ge=1),
):
    """リリース統計取得API（実データ）"""
    if state.client is None:
        raise HTTPException(status_code=500, detail={"error": {"code": "BOOTSTRAP", "message": "client not ready"}})

    request_id = str(uuid.uuid4())
    try:
        stats = await fetch_release_statistics(company_id, release_id)
        return {"request_id": request_id, "statistics": stats}
    except httpx.HTTPStatusError as e:
        raise_from_httpx(e, request_id)
    except Exception as e:
        logger.exception("release stats error")
        raise HTTPException(status_code=500, detail={"error": {"code": "UNEXPECTED", "message": str(e)}, "request_id": request_id})


# ===============================
# RAG関連エンドポイント
# ===============================

@app.get("/rag/context/{category_id}")
async def get_rag_context(
    category_id: int = Path(..., ge=1),
    window_days: int = Query(30, ge=1, le=180),
    top_k: int = Query(12, ge=1, le=30)
):
    """RAG文脈データの取得（フロントエンド表示用）"""
    if state.client is None:
        raise HTTPException(status_code=500, detail={"error": {"code": "BOOTSTRAP", "message": "client not ready"}})
    
    request_id = str(uuid.uuid4())
    
    try:
        to_date = datetime.now()
        from_date = to_date - timedelta(days=window_days)
        params = {
            "per_page": min(top_k * 2, 100),
            "page": 0,
            "from_date": from_date.strftime("%Y-%m-%d"),
            "to_date": to_date.strftime("%Y-%m-%d"),
        }
        
        candidates = await fetch_category_releases(category_id, params)
        rag_context_items = sorted(candidates, key=lambda x: x.get("like", 0), reverse=True)[:top_k]
        
        # フロントエンド表示用に整形
        formatted_items = []
        for item in rag_context_items:
            formatted_items.append({
                "title": item.get("title", ""),
                "company": item.get("company_name", ""),
                "date": (item.get("created_at", "") or "")[:10],
                "likes": item.get("like", 0),
                "lead": item.get("lead_paragraph", "")[:200],
                "url": item.get("url", ""),
                "sub_category": item.get("sub_category_name", "")
            })
        
        return {
            "request_id": request_id,
            "category_id": category_id,
            "category_name": CATEGORIES.get(category_id, "不明"),
            "window_days": window_days,
            "top_k": top_k,
            "count": len(formatted_items),
            "items": formatted_items
        }
        
    except httpx.HTTPStatusError as e:
        raise_from_httpx(e, request_id)
    except Exception as e:
        logger.exception("RAG context error")
        raise HTTPException(status_code=500, detail={"error": {"code": "UNEXPECTED", "message": str(e)}, "request_id": request_id})


@app.post("/rag/categories/{category_id}")
async def rag_category(
    category_id: int = Path(..., ge=1),
    request: RAGCategoryRequest = Body(default=RAGCategoryRequest()),
):
    """
    RAG: カテゴリ別プレスリリースの取得・分析・ランキング
    全て実データを使用
    """
    if state.client is None:
        raise HTTPException(status_code=500, detail={"error": {"code": "BOOTSTRAP", "message": "client not ready"}})

    request_id = str(uuid.uuid4())

    try:
        # 1. Retrieval: プレスリリース取得（実データ）
        params: Dict[str, Any] = {
            "per_page": request.per_page,
            "page": request.page
        }
        if request.from_date:
            params["from_date"] = request.from_date
        if request.to_date:
            params["to_date"] = request.to_date

        releases = await fetch_category_releases(category_id, params)
        logger.info(f"Retrieved {len(releases)} releases for category {category_id}")

        # 2. Ranking: ランキング処理
        ranked_releases = rank_releases(
            releases,
            method=request.ranking_method,
            top_k=request.top_k
        )

        # 3. Augmentation: 統計情報付与（実データ）
        enriched_releases: List[ReleaseWithStats] = []
        if request.use_statistics:
            for release in ranked_releases:
                stats = await fetch_release_statistics(
                    release["company_id"],
                    release["release_id"]
                )
                enriched_releases.append(ReleaseWithStats(release=release, statistics=stats))
        else:
            for release in ranked_releases:
                enriched_releases.append(ReleaseWithStats(release=release))

        # 4. Analysis: トレンド分析
        trends = analyze_category_trends(releases)

        # レスポンス構築
        response = RAGResponse(
            request_id=request_id,
            category_id=category_id,
            total_count=len(releases),
            filtered_count=len(enriched_releases),
            releases=enriched_releases,
            metadata={
                "ranking_method": request.ranking_method,
                "trends": trends,
                "params": params,
            }
        )

        return response

    except httpx.HTTPStatusError as e:
        raise_from_httpx(e, request_id)
    except Exception as e:
        logger.exception("RAG category error")
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "UNEXPECTED", "message": str(e)}, "request_id": request_id}
        )


# ===============================
# RAG強化 - AI分析
# ===============================

@app.post("/analyze")
async def analyze_press_release(payload: PressReleaseInput):
    """
    プレスリリース分析エンドポイント（RAG強化版）
    - OpenAI による全メディアフック評価・改善提案
    - 成功事例を基にした具体的な改善案を生成
    """
    request_id = str(uuid.uuid4())
    started = datetime.now()

    # 1) RAG文脈（必要時）
    rag_context_items: List[Dict[str, Any]] = []
    if payload.context_category_id and state.client is not None:
        try:
            to_date = datetime.now()
            from_date = to_date - timedelta(days=payload.context_window_days)
            params = {
                "per_page": min(payload.context_top_k * 2, 100),
                "page": 0,
                "from_date": from_date.strftime("%Y-%m-%d"),
                "to_date": to_date.strftime("%Y-%m-%d"),
            }
            candidates = await fetch_category_releases(payload.context_category_id, params)
            # いいね順で上位 context_top_k 件
            rag_context_items = sorted(candidates, key=lambda x: x.get("like", 0), reverse=True)[: payload.context_top_k]
            logger.info(f"RAG: Retrieved {len(rag_context_items)} context items for category {payload.context_category_id}")
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status in (401, 403):
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": {
                            "code": "PRTIMES_FORBIDDEN",
                            "message": "PR TIMES stg への認可に失敗しました。VPN/社内Wi-Fiに接続するか、IP許可を依頼してください。",
                            "upstream_status": status,
                        },
                        "request_id": request_id,
                    },
                )
            raise_from_httpx(e, request_id)
        except Exception as e:
            logger.warning(f"RAG context fetch skipped due to error: {e}")

    # 全メディアフック項目定義
    required_hooks = [
        {"hook_type": "trending_seasonal", "hook_name_ja": "トレンド・季節性"},
        {"hook_type": "unexpectedness", "hook_name_ja": "意外性"},
        {"hook_type": "paradox_conflict", "hook_name_ja": "パラドックス・対立構造"},
        {"hook_type": "regional", "hook_name_ja": "地域性"},
        {"hook_type": "topicality", "hook_name_ja": "話題性"},
        {"hook_type": "social_public", "hook_name_ja": "社会性・公共性"},
        {"hook_type": "novelty_uniqueness", "hook_name_ja": "新規性・独自性"},
        {"hook_type": "superlative_rarity", "hook_name_ja": "最上級・希少性"},
        {"hook_type": "visual_impact", "hook_name_ja": "ビジュアルインパクト"},
    ]

    # 2) OpenAI未設定なら簡易フォールバック（全項目含む）
    if state.openai is None:
        elapsed = (datetime.now() - started).total_seconds() * 1000
        return {
            "request_id": request_id,
            "analyzed_at": datetime.now().isoformat(),
            "media_hook_evaluations": [
                {
                    "hook_type": hook["hook_type"],
                    "hook_name_ja": hook["hook_name_ja"],
                    "score": 3,
                    "description": "OpenAI未設定のため簡易評価",
                    "improve_examples": ["OPENAI_API_KEY を設定してください"],
                    "current_elements": [],
                    "success_patterns": []
                } for hook in required_hooks
            ],
            "paragraph_improvements": [],
            "overall_assessment": {
                "total_score": 2.5,
                "strengths": ["OpenAI未設定のため簡易評価"],
                "weaknesses": ["OpenAI未設定のため簡易評価"],
                "top_recommendations": ["OPENAI_API_KEY を設定してください"],
                "estimated_impact": "分析機能実装前の暫定表示",
                "benchmark_comparison": "設定が必要"
            },
            "processing_time_ms": int(elapsed),
            "ai_model_used": "none",
            "rag_used": bool(payload.context_category_id),
            "rag_context_count": len(rag_context_items),
        }

    # 3) RAG文脈の整形（本文も含める）
    def _compact_item(r: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "title": r.get("title", "")[:140],
            "company": r.get("company_name", ""),
            "date": (r.get("created_at", "") or "")[:10],
            "sub_category": r.get("sub_category_name", ""),
            "likes": r.get("like", 0),
            "lead": (r.get("lead_paragraph", "") or "")[:220],
            "body_snippet": (r.get("body", "") or "")[:300],  # 本文も追加
        }

    rag_brief = [_compact_item(r) for r in rag_context_items]

    # 4) RAG文脈を活用する強化されたプロンプト
    system_prompt = (
        "あなたは日本のプレスリリース編集者です。"
        "与えられたリリース本文を、メディアが取り上げやすい『フック』の観点で評価してください。"
        
        "**重要**: 以下の作業手順に従ってください：\n"
        "1. まず『related_context.items』の成功事例を分析し、どのような要素がメディアに受けているかを把握\n"
        "2. 入力記事と成功事例を比較し、足りない要素や改善点を特定\n"
        "3. 成功事例から学んだパターンを基に、具体的で実行可能な改善案を提案\n"
        "4. 各メディアフック項目で、成功事例との比較を含めた評価を実施\n"
        
        "**分析のポイント**:\n"
        "- 成功事例（いいね数が多い）の共通パターンを見つける\n"
        "- タイトルの書き方、数値の使い方、キーワードの選択を参考にする\n"
        "- 業界のトレンドや話題性のパターンを分析する\n"
        "- 具体性や独自性の表現方法を学ぶ\n"
        
        "以下の9つのメディアフック項目について、必ずすべて評価してください。"
        "各項目のスコアは1〜5の整数で評価し、成功事例との比較を含めて根拠を述べてください。"
        "出力は必ずJSON一つだけ。"
    )

    # 5) スキーマ定義（成功パターン追加）
    schema_hint = {
        "media_hook_evaluations": [
            {
                "hook_type": hook["hook_type"],
                "hook_name_ja": hook["hook_name_ja"],
                "score": 3,
                "description": "成功事例との比較を含めた評価理由",
                "improve_examples": [
                    "成功事例「○○」のように、具体的な数値を含める",
                    "「××社の事例」を参考に、より具体的な効果を明記する"
                ],
                "current_elements": ["現状で満たしている要素"],
                "success_patterns": ["参考にした成功事例のパターン"]
            } for hook in required_hooks
        ],
        "paragraph_improvements": [
            {
                "where": "改善箇所",
                "before": "元文",
                "after": "改善案",
                "reference_example": "参考にした成功事例のタイトル/文章"
            }
        ],
        "overall_assessment": {
            "total_score": 0.0,
            "strengths": ["強み"],
            "weaknesses": ["弱み"],
            "top_recommendations": ["具体的な推奨事項"],
            "estimated_impact": "推定インパクト",
            "benchmark_comparison": "成功事例との比較結果"
        }
    }

    user_payload = {
        "input_article": {
            "title": payload.title,
            "markdown_or_html": payload.content_markdown,
            "image_url": (payload.top_image.url if payload.top_image and payload.top_image.url else None),
            "persona": (payload.metadata.persona if payload.metadata else "指定なし"),
        },
        "related_context": {
            "category_id": payload.context_category_id,
            "window_days": payload.context_window_days,
            "top_k": payload.context_top_k,
            "items": rag_brief,
            "analysis_instruction": "これらは同カテゴリで高評価を得たプレスリリースです。成功パターンを分析し、入力記事の改善に活用してください。"
        },
        "required_evaluations": required_hooks,
        "output_schema_hint": schema_hint,
    }

    try:
        completion = await state.openai.chat.completions.create(
            model=settings.OPENAI_MODEL,
            temperature=settings.LLM_TEMPERATURE,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        "以下の分析を実行してください：\n"
                        "1. 『related_context.items』の成功事例を分析\n"
                        "2. 入力記事と成功事例を比較\n"
                        "3. 9つのメディアフック項目すべてを評価\n"
                        "4. 成功事例から学んだ具体的な改善案を提案\n\n"
                        "分析対象データ:\n"
                        + json.dumps(user_payload, ensure_ascii=False)
                    ),
                },
            ],
            max_tokens=settings.LLM_MAX_TOKENS,
        )
        raw = completion.choices[0].message.content or "{}"
        ai = json.loads(raw)
        
        # 全項目が存在することを保証（不足分は補完）
        ai_hooks = ai.get("media_hook_evaluations", [])
        hooks_by_type = {hook.get("hook_type"): hook for hook in ai_hooks}
        
        complete_hooks = []
        for required_hook in required_hooks:
            hook_type = required_hook["hook_type"]
            if hook_type in hooks_by_type:
                complete_hooks.append(hooks_by_type[hook_type])
            else:
                # 不足分を補完
                complete_hooks.append({
                    "hook_type": hook_type,
                    "hook_name_ja": required_hook["hook_name_ja"],
                    "score": 2,
                    "description": "AIによる評価が不完全でした。再実行を推奨します。",
                    "improve_examples": ["再分析を実行してください"],
                    "current_elements": [],
                    "success_patterns": []
                })
        
        ai["media_hook_evaluations"] = complete_hooks
        
    except Exception as e:
        logger.exception("OpenAI analyze error")
        # エラー時も全項目を含む
        ai = {
            "media_hook_evaluations": [
                {
                    "hook_type": hook["hook_type"],
                    "hook_name_ja": hook["hook_name_ja"],
                    "score": 2,
                    "description": "分析中にエラーが発生しました。",
                    "improve_examples": ["しばらくしてから再実行してください"],
                    "current_elements": [],
                    "success_patterns": []
                } for hook in required_hooks
            ],
            "paragraph_improvements": [],
            "overall_assessment": {
                "total_score": 2.5,
                "strengths": ["分析中にエラー。簡易結果を表示"],
                "weaknesses": ["ネットワーク/レート制限の可能性"],
                "top_recommendations": ["しばらくしてから再実行してください"],
                "estimated_impact": "限定的",
                "benchmark_comparison": "エラーのため比較不可"
            },
        }

    elapsed_ms = int((datetime.now() - started).total_seconds() * 1000)
    return {
        "request_id": request_id,
        "analyzed_at": datetime.now().isoformat(),
        "media_hook_evaluations": ai.get("media_hook_evaluations", []),
        "paragraph_improvements": ai.get("paragraph_improvements", []),
        "overall_assessment": ai.get("overall_assessment", {}),
        "processing_time_ms": elapsed_ms,
        "ai_model_used": settings.OPENAI_MODEL if state.openai else "none",
        "rag_used": bool(payload.context_category_id),
        "rag_context_count": len(rag_brief),
    }


# ===============================
# その他のエンドポイント（統計・デバッグ等）
# ===============================

@app.get("/debug/config")
async def debug_config():
    """設定確認用（開発環境のみ使用）"""
    return {
        "cors_origins": _parse_cors(settings.CORS_ORIGINS),
        "base_url": settings.PRTIMES_BASE_URL,
        "output_dir": settings.OUTPUT_DIR,
        "openai_configured": bool(settings.OPENAI_API_KEY),
        "default_industry_id": settings.DEFAULT_INDUSTRY_ID,
        "max_companies_per_page": settings.MAX_COMPANIES_PER_PAGE,
        "cache_status": {
            "has_cache": state.companies_cache is not None,
            "cache_size": len(state.companies_cache) if state.companies_cache else 0,
            "cache_age_seconds": (datetime.now() - state.cache_timestamp).total_seconds() if state.cache_timestamp else None
        }
    }


@app.get("/debug/cache/clear")
async def clear_cache():
    """キャッシュクリア（開発用）"""
    state.companies_cache = None
    state.cache_timestamp = None
    return {"status": "cache_cleared", "timestamp": datetime.now().isoformat()}


@app.get("/stats/companies/{company_id}")
async def get_company_stats(
    company_id: int = Path(..., ge=1),
    from_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    to_date: Optional[str] = Query(None, description="YYYY-MM-DD")
):
    """
    企業の統計情報取得
    リリース数、総いいね数、平均PVなどを集計
    """
    if state.client is None:
        raise HTTPException(status_code=500, detail={"error": {"code": "BOOTSTRAP", "message": "client not ready"}})

    request_id = str(uuid.uuid4())

    try:
        # リリース一覧を取得
        params: Dict[str, Any] = {"per_page": 100, "page": 0}
        if from_date:
            params["from_date"] = from_date
        if to_date:
            params["to_date"] = to_date

        releases = await fetch_company_releases(company_id, params)

        # 統計情報を集計
        total_likes = sum(r.get("like", 0) for r in releases)

        # 各リリースの詳細統計を取得（最新10件のみ）
        detailed_stats = []
        for release in releases[:10]:
            stats = await fetch_release_statistics(
                company_id,
                release["release_id"]
            )
            if stats:
                detailed_stats.append({
                    "release_id": release["release_id"],
                    "title": release["title"],
                    "created_at": release["created_at"],
                    "statistics": stats
                })

        return {
            "request_id": request_id,
            "company_id": company_id,
            "period": {
                "from": from_date or "all",
                "to": to_date or "all"
            },
            "summary": {
                "total_releases": len(releases),
                "total_likes": total_likes,
                "avg_likes": total_likes / len(releases) if releases else 0,
                "latest_release": releases[0]["created_at"] if releases else None,
                "oldest_release": releases[-1]["created_at"] if releases else None
            },
            "recent_releases_stats": detailed_stats
        }

    except Exception as e:
        logger.exception(f"Failed to get company stats for {company_id}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "STATS_ERROR",
                    "message": f"統計情報の取得に失敗しました: {str(e)}"
                },
                "request_id": request_id
            }
        )


@app.get("/trending")
async def get_trending_releases(
    limit: int = Query(10, ge=1, le=50),
    days: int = Query(7, ge=1, le=30)
):
    """
    トレンドリリース取得
    指定期間内で最もいいねが多いリリースを返す
    """
    if state.client is None:
        raise HTTPException(status_code=500, detail={"error": {"code": "BOOTSTRAP", "message": "client not ready"}})

    request_id = str(uuid.uuid4())

    try:
        # 日付範囲を計算
        to_date = datetime.now()
        from_date = to_date - timedelta(days=days)

        all_releases: List[Dict[str, Any]] = []

        # 主要カテゴリから取得（1-10まで）
        for category_id in range(1, 11):
            try:
                params = {
                    "per_page": 20,
                    "page": 0,
                    "from_date": from_date.strftime("%Y-%m-%d"),
                    "to_date": to_date.strftime("%Y-%m-%d")
                }
                releases = await fetch_category_releases(category_id, params)
                all_releases.extend(releases)
            except Exception as e:
                logger.warning(f"Failed to fetch category {category_id}: {e}")
                continue

        # いいね数でソート
        trending = sorted(all_releases, key=lambda x: x.get("like", 0), reverse=True)[:limit]

        # 統計情報を追加
        enriched_trending = []
        for release in trending:
            try:
                stats = await fetch_release_statistics(
                    release["company_id"],
                    release["release_id"]
                )
                enriched_trending.append({
                    **release,
                    "statistics": stats
                })
            except Exception:
                enriched_trending.append(release)

        return {
            "request_id": request_id,
            "period_days": days,
            "count": len(enriched_trending),
            "trending_releases": enriched_trending
        }

    except Exception as e:
        logger.exception("Failed to get trending releases")
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "TRENDING_ERROR",
                    "message": f"トレンド取得に失敗しました: {str(e)}"
                },
                "request_id": request_id
            }
        )


@app.get("/categories")
async def get_categories():
    """カテゴリ一覧取得"""
    return {
        "categories": [
            {"id": k, "name": v} for k, v in CATEGORIES.items()
        ]
    }


@app.get("/health/detailed")
async def detailed_health_check():
    """詳細なヘルスチェック"""
    health_status: Dict[str, Any] = {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "api_client": "ok" if state.client else "not_initialized",
            "openai": "configured" if settings.OPENAI_API_KEY else "not_configured",
            "cache": {
                "companies_cached": state.companies_cache is not None,
                "cache_entries": len(state.companies_cache) if state.companies_cache else 0
            }
        }
    }

    # PR TIMES APIの疎通確認（軽量）
    if state.client:
        try:
            test_params = {"per_page": 1, "page": 0}
            await fetch_companies_from_api(test_params)
            health_status["components"]["prtimes_api"] = "ok"
        except Exception as e:
            health_status["components"]["prtimes_api"] = f"error: {str(e)}"
            health_status["status"] = "degraded"

    return health_status


# ===============================
# 例外ハンドラ
# ===============================

@app.exception_handler(httpx.TimeoutException)
async def timeout_exception_handler(request, exc):
    return JSONResponse(
        status_code=504,
        content={
            "error": {
                "code": "TIMEOUT",
                "message": "外部APIへのリクエストがタイムアウトしました"
            }
        }
    )


@app.exception_handler(httpx.ConnectError)
async def connection_exception_handler(request, exc):
    return JSONResponse(
        status_code=503,
        content={
            "error": {
                "code": "CONNECTION_ERROR",
                "message": "外部APIに接続できません"
            }
        }
    )