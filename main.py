import os
import instructor
from fastapi import FastAPI, HTTPException, Form
from pydantic import BaseModel, Field, conint, field_validator
from openai import AsyncOpenAI
from dotenv import load_dotenv
from typing import List
from enum import Enum

# .envファイルから環境変数を読み込む
load_dotenv()
MODEL = "gpt-4o-mini" # モデルは要件に合わせて変更してください

# --- メディアフックの9つの要素を定義するEnum ---
class MediaHook(str, Enum):
    """メディアフックを構成する9つの要素を定義するEnum"""
    TIMELINESS_SEASONALITY = "時流／季節性"
    IMAGE_VIDEO = "画像／映像"
    PARADOX_CONFLICT = "逆説／対立"
    REGIONALITY = "地域性"
    TOPICALITY = "話題性"
    SOCIAL_PUBLIC_INTEREST = "社会性／公益性"
    NOVELTY_UNIQUENESS = "新規性／独自性"
    SUPERLATIVE_RARITY = "最上級／希少性"
    UNEXPECTEDNESS = "意外性"

# --- 構造化出力用のPydanticモデル（修正箇所） ---

class ImprovementSuggestions(BaseModel):
    title_suggestions: List[str] = Field(..., description="タイトルの改善点を5つ挙げてください。", min_items=5, max_items=5)
    paragraph_suggestions: List[List[str]] = Field(..., description="各段落の改善点をそれぞれ5つずつ挙げてください。リストの各要素が1つの段落に対応します。")

# ▼▼▼【変更点 1】辞書ではなく、リストで受け取るための新しいモデルを定義 ▼▼▼
class SingleHookEvaluation(BaseModel):
    """メディアフックの単一要素に対する評価を格納するモデル"""
    hook_name: MediaHook = Field(..., description="評価対象のメディアフックの要素名。")
    evaluation: conint(ge=1, le=5) = Field(..., description="1から5までの5段階評価。")
    reason: str = Field(..., description="なぜその評価になったのかの具体的な理由。")

class ArticleAnalysisResponse(BaseModel):
    """記事分析結果の全体を格納するモデル"""
    media_hook_evaluations: List[SingleHookEvaluation] = Field(..., description="メディアフック9要素それぞれに対する評価と理由のリスト。")
    improvement_suggestions: ImprovementSuggestions = Field(..., description="タイトルと各段落の具体的な改善案。")

    @field_validator("media_hook_evaluations")
    def check_all_hooks_evaluated(cls, v):
        """全てのメディアフックが評価されているか検証する"""
        if len(v) != len(MediaHook):
            raise ValueError("9つ全てのメディアフック要素を評価してください。")
        return v

# FastAPIアプリケーションのインスタンスを作成
app = FastAPI(
    title="Article Analysis API for Media Hooks",
    description="メディアフックの観点から記事を分析し、改善点を提案するAPI",
    version="2.1.0", # バージョンアップ
)

# instructor でOpenAIクライアントをパッチ
client = instructor.patch(AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY")))

@app.post("/analyze_article", response_model=ArticleAnalysisResponse)
async def analyze_article(
    title: str = Form(..., description="分析対象の記事タイトル。"),
    article_body: str = Form(..., description="分析対象の記事本文。改行で段落を区切ってください。"),
    persona: str = Form(..., description="記事のターゲットとなるペルソナ。")
):
    try:
        paragraphs = article_body.strip().split('\n')
        paragraph_count = len(paragraphs)

        analysis_result = await client.chat.completions.create(
            model=MODEL,
            response_model=ArticleAnalysisResponse,
            max_retries=3,
            messages=[
                {
                    "role": "system",
                    "content": "あなたは優秀な広報・PRの専門家です。提供された記事をメディアフックの観点から厳しく分析し、具体的な改善点を提案してください。"
                },
                {
                    "role": "user",
                    "content": f"""以下の記事を分析し、メディアフックの9要素をそれぞれ5段階で評価し、タイトルと各段落の改善点を5つずつ提案してください。

# ターゲットペルソナ
{persona}

# 記事タイトル
{title}

# 記事本文（{paragraph_count}個の段落で構成されています）
{article_body}

## 分析の指示
1.  **メディアフックの評価**: 9つの要素それぞれについて、評価(1-5)、理由、要素名を `{{"hook_name": "要素名", "evaluation": 評価, "reason": "理由"}}` という形式のオブジェクトにし、それらをリストとして生成してください。
2.  **改善点の提案**:
    -   タイトルの改善案を5つ提案してください。
    -   記事本文の各段落（全部で{paragraph_count}個）について、それぞれ改善案を5つずつ提案してください。出力は段落の数に応じたリストのリスト形式にしてください。
"""
                }
            ],
            max_tokens=4000,
        )
        return analysis_result
    except Exception as e:
        print(f"エラーが発生しました: {e}")
        raise HTTPException(status_code=500, detail=f"処理中にサーバーエラーが発生しました: {str(e)}")