import os
import instructor
import uuid
import time
import httpx # httpxをインポート
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Body
from openai import AsyncOpenAI
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

# models.pyから定義したデータ型をインポート
from models import (
    PressReleaseInput, 
    PressReleaseAnalysisResponse, 
    MediaHookType,
    Company,          # 追加
    PressRelease      # 追加
)

# .envファイルから環境変数を読み込む
load_dotenv()
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# OpenAI APIキーのチェック
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY is not set in the environment variables.")

# PR TIMES APIのアクセストークンとベースURLを設定
PRTIMES_ACCESS_TOKEN = os.getenv("PRTIMES_ACCESS_TOKEN")
if not PRTIMES_ACCESS_TOKEN:
    raise ValueError("PRTIMES_ACCESS_TOKEN is not set in the environment variables.")
PRTIMES_BASE_URL = "https://hackathon.stg-prtimes.net/api"


# instructorでOpenAIクライアントをパッチ
client = instructor.patch(AsyncOpenAI(api_key=api_key))

# FastAPIアプリケーションのインスタンスを作成
app = FastAPI(
    title="Press Release Analysis API",
    description="データ型定義に基づき、プレスリリースをメディアフックの観点から分析し、改善点を提案する",
    version="3.0.0",
)

# CORSを許可するオリジン
origins = [
    "http://localhost:3000",
    "http://localhost:8501", # Streamlitのデフォルトポート
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 各メディアフックの日本語名と説明を定義
MEDIA_HOOK_DETAILS = {
    MediaHookType.TRENDING_SEASONAL: {"ja": "時流・季節性", "desc": "社会のトレンドや季節イベントに関連しているか"},
    MediaHookType.UNEXPECTEDNESS: {"ja": "意外性", "desc": "常識を覆すような驚きがあるか"},
    MediaHookType.PARADOX_CONFLICT: {"ja": "逆説・対立", "desc": "一見矛盾する要素や対立構造があるか"},
    MediaHookType.REGIONAL: {"ja": "地域性", "desc": "特定の地域に密着した情報か"},
    MediaHookType.TOPICALITY: {"ja": "話題性", "desc": "現在話題の事柄と関連しているか"},
    MediaHookType.SOCIAL_PUBLIC: {"ja": "社会性・公益性", "desc": "社会問題の解決など公共の利益に貢献するか"},
    MediaHookType.NOVELTY_UNIQUENESS: {"ja": "新規性・独自性", "desc": "「日本初」や独自の技術など、他にはない要素があるか"},
    MediaHookType.SUPERLATIVE_RARITY: {"ja": "最上級・希少性", "desc": "「No.1」や「限定」など、希少価値やインパクトがあるか"},
    MediaHookType.VISUAL_IMPACT: {"ja": "画像・映像", "desc": "印象的で目を引くビジュアルがあるか"},
}

# ================================================================================
# 新しく追加したPR TIMES APIのエンドポイント
# ================================================================================

@app.get("/companies", response_model=List[Company], tags=["PR TIMES"])
async def get_companies():
    """
    PR TIMESに登録されている企業の一覧を取得します。
    """
    url = f"{PRTIMES_BASE_URL}/companies"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {PRTIMES_ACCESS_TOKEN}",
    }
    
    async with httpx.AsyncClient() as http_client:
        try:
            res = await http_client.get(url, headers=headers)
            res.raise_for_status()  # 4xx, 5xxエラーの場合は例外を発生させる
            return res.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Failed to fetch data from PR TIMES API: {e.response.text}"
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.get("/companies/{company_id}/releases", response_model=List[PressRelease], tags=["PR TIMES"])
async def get_company_releases(
    company_id: int,
    # クエリパラメータとして日付を受け取れるようにする
    from_date: Optional[str] = None,
    to_date: Optional[str] = None
):
    """
    指定された企業IDのプレスリリース一覧を取得します。
    期間を指定することも可能です (例: ?from_date=2023-01-01&to_date=2023-12-31)
    """
    url = f"{PRTIMES_BASE_URL}/companies/{company_id}/releases"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {PRTIMES_ACCESS_TOKEN}",
    }
    
    # 日付パラメータを組み立てる
    params = {}
    if from_date:
        params["from_date"] = from_date
    if to_date:
        params["to_date"] = to_date

    async with httpx.AsyncClient() as http_client:
        try:
            # paramsをリクエストに追加
            res = await http_client.get(url, headers=headers, params=params)
            res.raise_for_status()
            return res.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise HTTPException(
                    status_code=404, 
                    detail=f"Company with ID {company_id} not found."
                )
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Failed to fetch data from PR TIMES API: {e.response.text}"
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


# ================================================================================
# 既存のプレスリリース分析エンドポイント
# ================================================================================

@app.post("/analyze", response_model=PressReleaseAnalysisResponse, tags=["Analysis"])
async def analyze_press_release(
    data: PressReleaseInput = Body(...)
):
    """
    プレスリリースをメディアフックの観点から分析し、評価と改善点を構造化JSONで返すエンドポイント
    """
    request_id = f"req_{uuid.uuid4()}"
    start_time = time.time()

    try:
        paragraphs = [p.strip() for p in data.content_markdown.split('\n\n') if p.strip()]
        
        prompt = f"""
        # 指示
        あなたは日本の広報・PR分野におけるトップ専門家です。
        以下のプレスリリースを分析し、メディアフックの観点から厳しく評価と改善提案を行ってください。
        出力は必ず指定されたJSON形式に従ってください。

        # 分析対象プレスリリース
        ## タイトル
        {data.title}
        
        ## ターゲットペルソナ
        {data.metadata.get('persona', '指定なし')}

        ## 本文（{len(paragraphs)}段落）
        {data.content_markdown}
        
        ## トップ画像
        - URL: {data.top_image.url if data.top_image else 'なし'}
        - 代替テキスト: {data.top_image.alt_text if data.top_image else 'なし'}

        # 分析タスク
        1. **メディアフック評価**: 9つのメディアフック（{', '.join(m.value for m in MediaHookType)}）について、それぞれ評価スコア(1-5)、評価理由、改善例、現在の文章に含まれる要素を具体的に記述してください。日本語名も必ず含めてください。
        2. **段落ごと改善提案**: 本文の各段落（全{len(paragraphs)}段落）に対して、改善案、改善優先度などを具体的に提案してください。
        3. **全体評価**: 全体を俯瞰した総括的な評価と、最も優先すべき改善点を挙げてください。
        """

        analysis_result = await client.chat.completions.create(
            model=MODEL,
            response_model=PressReleaseAnalysisResponse,
            max_retries=2,
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=4096,
            temperature=0.2,
        )

        end_time = time.time()
        analysis_result.request_id = request_id
        analysis_result.processing_time_ms = int((end_time - start_time) * 1000)
        analysis_result.ai_model_used = MODEL
        
        for eval_item in analysis_result.media_hook_evaluations:
            eval_item.hook_name_ja = MEDIA_HOOK_DETAILS[eval_item.hook_type]["ja"]

        return analysis_result

    except Exception as e:
        print(f"Error during analysis for request_id {request_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "ANALYSIS_FAILED",
                    "message": f"An unexpected error occurred during analysis: {str(e)}"
                },
                "request_id": request_id
            }
        )