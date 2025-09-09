import base64
import os
import time
import uuid
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

# メディアフック詳細
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
            for i, p in enumerate(paragraphs):
                # 各段落の前にインデックスを明記する
                formatted_content += f"--- 段落 {i} ---\n{p}\n\n"

        # 2. メインの指示プロンプトを作成
        text_prompt = f"""
        # 指示
        あなたは日本の広報・PR分野におけるトップ専門家です。
        以下のプレスリリース（テキストと画像）を分析し、メディアフックの観点から厳しく評価と改善提案を行ってください。
        特に「画像・映像」の項目は、提供された画像を直接評価してください。
        
        段落ごとの改善提案（paragraph_improvements）では、**必ず以下の「分析対象プレスリリース」の本文で示されたインデックス番号（`--- 段落 0 ---`など）と対応する`paragraph_index`を付けてください**。

        出力は必ず指定されたJSON形式に従ってください。

        # 分析対象プレスリリース
        ## タイトル: {data.title}
        ## ターゲットペルソナ: {data.metadata.persona}
        ## 本文 ({len(paragraphs)}段落):
        {formatted_content}
        """

        # 3. OpenAIに渡すメッセージリストを作成
        messages = [
            {"role": "user", "content": [{"type": "text", "text": text_prompt}]}
        ]

        # 4. 画像があればメッセージに追加
        if data.top_image and data.top_image.url:
            try:
                # httpxを使って非同期で画像を取得
                async with httpx.AsyncClient() as http_client:
                    response = await http_client.get(data.top_image.url, timeout=10)
                    response.raise_for_status()

                    image_bytes = response.content
                    base64_image = base64.b64encode(image_bytes).decode("utf-8")
                    mime_type = response.headers.get("Content-Type", "image/jpeg")

                    # メッセージリストに画像を追加
                    messages[0]["content"].append(
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}"
                            },
                        }
                    )
            except Exception as img_e:
                print(f"Image download failed for url {data.top_image.url}: {img_e}")
                # 画像取得失敗の旨をプロンプトに追記
                messages[0]["content"][0]["text"] += (
                    "\n\n## トップ画像\n- 注意: 指定されたURLからの画像の取得に失敗しました。画像の評価はできません。"
                )

        # --- AIによる分析実行 ---
        analysis_result = await client.chat.completions.create(
            model=MODEL,
            response_model=PressReleaseAnalysisResponse,
            max_retries=2,
            messages=messages,
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

    except Exception as e:
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
