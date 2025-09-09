import base64
# main.py

import os
import time
import uuid
import time
import httpx
import base64
from typing import List, Optional

import httpx
import instructor
from dotenv import load_dotenv
from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI

# models.pyのインポートパスを修正 (環境に合わせて調整してください)
from .models import (
    Company,
    MediaHookType,
    PressRelease,
    PressReleaseAnalysisResponse,
    PressReleaseInput,
)

# .envファイルから環境変数を読み込む
load_dotenv()
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# APIキーのチェック
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY is not set in the environment variables.")

PRTIMES_ACCESS_TOKEN = os.getenv("PRTIMES_ACCESS_TOKEN")
if not PRTIMES_ACCESS_TOKEN:
    raise ValueError("PRTIMES_ACCESS_TOKEN is not set in the environment variables.")
PRTIMES_BASE_URL = "https://hackathon.stg-prtimes.net/api"


# FastAPIアプリケーションのインスタンスを作成
app = FastAPI(
    title="Press Release Analysis API",
    description="データ型定義に基づき、プレスリリースをメディアフックの観点から分析し、改善点を提案する",
    version="3.2.0",  # バージョンアップ
)

# CORS設定
origins = ["http://localhost:3000", "http://localhost:8501"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# メディアフック詳細 (変更なし)
MEDIA_HOOK_DETAILS = {
    MediaHookType.TRENDING_SEASONAL: {
        "ja": "時流・季節性",
        "desc": "社会のトレンドや季節イベントに関連しているか",
    },
    MediaHookType.UNEXPECTEDNESS: {
        "ja": "意外性",
        "desc": "常識を覆すような驚きがあるか",
    },
    MediaHookType.PARADOX_CONFLICT: {
        "ja": "逆説・対立",
        "desc": "一見矛盾する要素や対立構造があるか",
    },
    MediaHookType.REGIONAL: {"ja": "地域性", "desc": "特定の地域に密着した情報か"},
    MediaHookType.TOPICALITY: {
        "ja": "話題性",
        "desc": "現在話題の事柄と関連しているか",
    },
    MediaHookType.SOCIAL_PUBLIC: {
        "ja": "社会性・公益性",
        "desc": "社会問題の解決など公共の利益に貢献するか",
    },
    MediaHookType.NOVELTY_UNIQUENESS: {
        "ja": "新規性・独自性",
        "desc": "「日本初」や独自の技術など、他にはない要素があるか",
    },
    MediaHookType.SUPERLATIVE_RARITY: {
        "ja": "最上級・希少性",
        "desc": "「No.1」や「限定」など、希少価値やインパクトがあるか",
    },
    MediaHookType.VISUAL_IMPACT: {
        "ja": "画像・映像",
        "desc": "印象的で目を引くビジュアルがあるか",
    },
}


# --- PR TIMES API エンドポイント (変更なし) ---
@app.get("/companies", response_model=List[Company], tags=["PR TIMES"])
async def get_companies():
    url = f"{PRTIMES_BASE_URL}/companies"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {PRTIMES_ACCESS_TOKEN}",
    }
    async with httpx.AsyncClient() as http_client:
        try:
            res = await http_client.get(url, headers=headers)
            res.raise_for_status()
            return res.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Failed to fetch data from PR TIMES API: {e.response.text}",
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/companies/{company_id}/releases",
    response_model=List[PressRelease],
    tags=["PR TIMES"],
)
async def get_company_releases(
    company_id: int, from_date: Optional[str] = None, to_date: Optional[str] = None
):
    url = f"{PRTIMES_BASE_URL}/companies/{company_id}/releases"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {PRTIMES_ACCESS_TOKEN}",
    }
    params = {}
    if from_date:
        params["from_date"] = from_date
    if to_date:
        params["to_date"] = to_date
    async with httpx.AsyncClient() as http_client:
        try:
            res = await http_client.get(url, headers=headers, params=params)
            res.raise_for_status()
            return res.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise HTTPException(
                    status_code=404, detail=f"Company with ID {company_id} not found."
                )
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Failed to fetch data from PR TIMES API: {e.response.text}",
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


# --- プレスリリース分析エンドポイント (ロジックを修正・整理) ---
@app.post("/analyze", response_model=PressReleaseAnalysisResponse, tags=["Analysis"])
async def analyze_press_release(data: PressReleaseInput = Body(...)):
    request_id = f"req_{uuid.uuid4()}"
    start_time = time.time()

    try:
        # OpenAIクライアントを準備
        client = instructor.patch(AsyncOpenAI(api_key=api_key))

        # --- プロンプトとメッセージの準備 ---

        # 1. 本文を段落に分割し、AIが認識しやすいように番号付けする
        paragraphs = [
            p.strip() for p in data.content_markdown.split("\n\n") if p.strip()
        ]
        formatted_content = ""
        if not paragraphs:
            formatted_content = "本文がありません。"
        else:
            formatted_content = "\n\n".join(
                [f"--- 段落 {i} ---\n{p}" for i, p in enumerate(paragraphs)]
            )

        # --- OpenAIに渡すメッセージを作成 ---
        text_prompt = f"""
        # 指示
        あなたは日本の広報・PR分野におけるトップ専門家です。
        以下のプレスリリース（テキストと画像）を分析し、メディアフックの観点から厳しく評価と改善提案を行ってください。
        特に「画像・映像」の項目は、提供された画像を直接評価してください。
        出力は必ず指定されたJSON形式に従ってください。

        # 分析対象プレスリリース
        ## タイトル: {data.title}
        ## ターゲットペルソナ: {data.metadata.persona}
        ## 本文（{len(paragraphs)}段落）: 
        {formatted_content}
        """
        user_content = [{"type": "text", "text": text_prompt}]

        # --- 画像部分の処理 ---
        if data.top_image and data.top_image.url:
            try:
                async with httpx.AsyncClient() as http_client:
                    response = await http_client.get(data.top_image.url, timeout=20) # タイムアウトを少し延長
                    response.raise_for_status()
                    
                    # 【修正点】非同期でレスポンスボディを読み込み、イベントループのブロッキングを回避
                    image_bytes = await response.aread()
                    base64_image = base64.b64encode(image_bytes).decode('utf-8')
                    mime_type = response.headers.get('Content-Type', 'image/jpeg')
                    
                    user_content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}
                    })
            # 【修正点】より具体的なエラーハンドリングを追加
            except httpx.HTTPStatusError as img_e:
                error_message = f"\n## トップ画像\n- 画像の取得に失敗しました (ステータスコード: {img_e.response.status_code})。"
                print(f"Image download failed (HTTP Status): {img_e.response.status_code} for url {data.top_image.url}")
                user_content[0]["text"] += error_message
            except httpx.RequestError as img_e:
                error_message = f"\n## トップ画像\n- 画像の取得に失敗しました (接続エラー)。"
                print(f"Image download failed (Request Error): {img_e} for url {data.top_image.url}")
                user_content[0]["text"] += error_message

        # --- AIによる分析実行 ---
        analysis_result = await client.chat.completions.create(
            model=MODEL,
            response_model=PressReleaseAnalysisResponse,
            max_retries=2,
            messages=[{"role": "user", "content": user_content}],
            max_tokens=4096,
            temperature=0.2,
        )

        end_time = time.time()
        analysis_result.request_id = request_id
        analysis_result.processing_time_ms = int((end_time - start_time) * 1000)
        analysis_result.ai_model_used = MODEL

        # レスポンスにメディアフックの日本語名を追加
        for eval_item in analysis_result.media_hook_evaluations:
            eval_item.hook_name_ja = MEDIA_HOOK_DETAILS[eval_item.hook_type]["ja"]

        return analysis_result

    except APIError as e:
        # OpenAI APIからのエラーを個別に捕捉
        print(f"OpenAI API Error for request_id {request_id}: {e}")
        raise HTTPException(status_code=502, detail={"error": {"code": "AI_SERVICE_ERROR", "message": f"AI service returned an error: {e.message}"}, "request_id": request_id})
    except Exception as e:
        # その他の予期せぬエラー
        print(f"Error during analysis for request_id {request_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "ANALYSIS_FAILED",
                    "message": f"An unexpected error occurred: {str(e)}",
                },
                "request_id": request_id,
            },
        )
