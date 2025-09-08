import os
import instructor
from fastapi import FastAPI, HTTPException, Form
# PydanticからEnum, Field, field_validatorを追加でインポート
from pydantic import BaseModel, Field, field_validator
from openai import AsyncOpenAI
from dotenv import load_dotenv
from typing import List
from enum import Enum # enumをインポート

# .envファイルから環境変数を読み込む
load_dotenv()

# --- 1. テキストカテゴリ用のEnumを定義 ---
class TextCategory(str, Enum):
    """テキストのカテゴリを定義するEnum"""
    EMAIL = "メール"
    REPORT = "レポート"
    NEWS_ARTICLE = "ニュース記事"
    SOCIAL_MEDIA_POST = "SNS投稿"
    CONTRACT = "契約書"
    OTHER = "その他"

# --- 構造化出力用のPydanticモデルをテキスト分析用に変更 ---
class TextAnalysisResponse(BaseModel):
    category: TextCategory = Field(..., description="提示された選択肢の中から、最もテキストのカテゴリに合うものを1つ選んでください。")
    summary: str = Field(..., description="テキスト全体の内容を要約した文章。")
    keywords: List[str] = Field(..., description="テキスト中の主要なキーワードやエンティティのリスト。最低3つは挙げてください。")
    confidence_score: float = Field(..., description="この分析結果に対するAIの自信度を0.0から1.0の間の数値で示してください。")
    analysis: str = Field(..., description="ユーザーからの指示や質問に対する分析結果や回答。")

    # --- 2. Validatorで意味的なチェックを定義 ---
    @field_validator("keywords")
    def keywords_must_not_be_empty(cls, v):
        """keywordsリストが空ではないことを検証する"""
        if not v or len(v) < 1: # 1つ以上を要求
            raise ValueError("テキストからキーワードが抽出されませんでした。必ず1つ以上リストに含めてください。")
        return v

    @field_validator("confidence_score")
    def score_must_be_in_range(cls, v):
        """confidence_scoreが0.0から1.0の範囲内であることを検証する"""
        if not (0.0 <= v <= 1.0):
            raise ValueError("自信度は0.0から1.0の範囲でなければなりません。")
        return v


# FastAPIアプリケーションのインスタンスを作成
app = FastAPI(
    title="Advanced Text Analysis API",
    description="ValidatorとEnumを活用した、堅牢な構造化テキスト分析JSONを返すAPI",
    version="1.0.0",
)

# instructor でOpenAIクライアントをパッチ
client = instructor.patch(AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY")))


@app.post("/analyze_text_advanced", response_model=TextAnalysisResponse)
async def analyze_text(
    instruction: str = Form(..., description="テキストに対して行う指示や質問を記述します。"),
    text_to_analyze: str = Form(..., description="分析対象のテキスト本文。")
):
    """
    テキストを分析し、検証済みの構造化JSONを返すエンドポイント
    """
    try:
        analysis_result = await client.chat.completions.create(
            model="gpt-4o",
            response_model=TextAnalysisResponse,
            # instructorにバリデーションに失敗した場合の再試行を指示
            max_retries=3,
            messages=[
                {
                    "role": "user",
                    "content": f"""以下のテキストを分析してください。

# 指示
{instruction}

# 分析対象テキスト
{text_to_analyze}
"""
                }
            ],
            max_tokens=1500,
        )
        return analysis_result
    except Exception as e:
        print(f"エラーが発生しました: {e}")
        raise HTTPException(status_code=500, detail="処理中にサーバーエラーが発生しました。")