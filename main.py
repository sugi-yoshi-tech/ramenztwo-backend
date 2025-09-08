import os
import base64
import instructor
from fastapi import FastAPI, HTTPException, File, UploadFile, Form
# PydanticからEnum, Field, field_validatorを追加でインポート
from pydantic import BaseModel, Field, field_validator 
from openai import AsyncOpenAI
from dotenv import load_dotenv
from typing import List
from enum import Enum # enumをインポート

# .envファイルから環境変数を読み込む
load_dotenv()

# --- 1. Enumで選択肢を定義 ---
class ImageCategory(str, Enum):
    """画像のカテゴリを定義するEnum"""
    INDOOR = "室内"
    OUTDOOR = "屋外"
    PORTRAIT = "人物"
    LANDSCAPE = "風景"
    DOCUMENT = "ドキュメント"
    OTHER = "その他"

# --- 構造化出力用のPydanticモデルを拡張 ---
class ImageAnalysisResponse(BaseModel):
    category: ImageCategory = Field(..., description="提示された選択肢の中から、最も画像のカテゴリに合うものを1つ選んでください。")
    description: str = Field(..., description="画像の内容を詳細に説明した文章。")
    objects: List[str] = Field(..., description="画像に写っている主要なオブジェクトのリスト。最低1つは挙げてください。")
    confidence_score: float = Field(..., description="この分析結果に対するAIの自信度を0.0から1.0の間の数値で示してください。")
    analysis: str = Field(..., description="ユーザーからの指示や質問に対する分析結果や回答。")

    # --- 2. Validatorで意味的なチェックを定義 ---
    @field_validator("objects")
    def objects_must_not_be_empty(cls, v):
        """objectsリストが空ではないことを検証する"""
        if not v:
            raise ValueError("画像からオブジェクトが検出されませんでした。必ず1つ以上リストに含めてください。")
        return v

    @field_validator("confidence_score")
    def score_must_be_in_range(cls, v):
        """confidence_scoreが0.0から1.0の範囲内であることを検証する"""
        if not (0.0 <= v <= 1.0):
            raise ValueError("自信度は0.0から1.0の範囲でなければなりません。")
        return v


# FastAPIアプリケーションのインスタンスを作成
app = FastAPI(
    title="Advanced Image Analysis API",
    description="ValidatorとEnumを活用した、より堅牢な構造化JSONを返すAPI",
    version="4.0.0",
)

# instructor でOpenAIクライアントをパッチ
client = instructor.patch(AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY")))


@app.post("/analyze_image_advanced", response_model=ImageAnalysisResponse)
async def analyze_image(
    text: str = Form(..., description="画像に対して行う指示や質問を記述します。"),
    image: UploadFile = File(..., description="分析対象の画像ファイル。")
):
    """
    画像とテキストを分析し、検証済みの構造化JSONを返すエンドポイント
    """
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="アップロードされたファイルは画像形式ではありません。")

    image_bytes = await image.read()
    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    base64_image_url = f"data:{image.content_type};base64,{base64_image}"

    try:
        analysis_result = await client.chat.completions.create(
            model="gpt-4o",
            response_model=ImageAnalysisResponse,
            # instructorにバリデーションに失敗した場合の再試行を指示
            max_retries=3,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"この画像を分析してください。指示: {text}"},
                        {"type": "image_url", "image_url": {"url": base64_image_url}}
                    ]
                }
            ],
            max_tokens=1500,
        )
        return analysis_result
    except Exception as e:
        print(f"エラーが発生しました: {e}")
        raise HTTPException(status_code=500, detail="処理中にサーバーエラーが発生しました。")