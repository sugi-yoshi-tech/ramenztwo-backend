"""
プレスリリース改善WebアプリケーションのAPIデータ型定義
FastAPI用のPydanticモデル
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, HttpUrl, field_validator
from datetime import datetime
from enum import Enum
import re

# ================================================================================
# Enums
# ================================================================================

class MediaHookType(str, Enum):
    """メディアフックの種類"""
    TRENDING_SEASONAL = "trending_seasonal"  # 時流・季節性
    UNEXPECTEDNESS = "unexpectedness"  # 意外性
    PARADOX_CONFLICT = "paradox_conflict"  # 逆説・対立
    REGIONAL = "regional"  # 地域性
    TOPICALITY = "topicality"  # 話題性
    SOCIAL_PUBLIC = "social_public"  # 社会性・公益性
    NOVELTY_UNIQUENESS = "novelty_uniqueness"  # 新規性・独自性
    SUPERLATIVE_RARITY = "superlative_rarity"  # 最上級・希少性
    VISUAL_IMPACT = "visual_impact"  # 画像・映像


class EvaluationScore(int, Enum):
    """5段階評価スコア"""
    VERY_POOR = 1
    POOR = 2
    AVERAGE = 3
    GOOD = 4
    EXCELLENT = 5


class ImprovementPriority(str, Enum):
    """改善優先度"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ================================================================================
# Request Models (入力データ)
# ================================================================================

class ImageData(BaseModel):
    """画像データ"""
    url: Optional[str] = Field(None, description="画像URL") # HttpUrlからstrに変更
    base64_data: Optional[str] = Field(None, description="Base64エンコードされた画像データ")
    mime_type: Optional[str] = Field(None, description="画像のMIMEタイプ (例: image/jpeg)")
    alt_text: Optional[str] = Field(None, description="画像の代替テキスト")

    @field_validator('base64_data')
    def validate_base64(cls, v):
        if v and not re.match(r'^data:image\/[a-zA-Z]+;base64,', v):
             # Base64データにプレフィックスがない場合は追加
            return f"data:image/jpeg;base64,{v}"
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://example.com/image.jpg",
                "mime_type": "image/jpeg",
                "alt_text": "プレスリリースのトップ画像"
            }
        }


class PressReleaseInput(BaseModel):
    """プレスリリース入力データ"""
    title: str = Field(..., min_length=1, max_length=200, description="記事のタイトル")
    top_image: Optional[ImageData] = Field(None, description="トップ画像")
    content_markdown: str = Field(..., min_length=1, description="プレスリリース本文（Markdown形式）")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="追加メタデータ (例: ターゲットペルソナ)")


# ================================================================================
# Response Models (出力データ)
# ================================================================================

class MediaHookEvaluation(BaseModel):
    """メディアフック評価"""
    hook_type: MediaHookType = Field(..., description="メディアフックの種類")
    hook_name_ja: str = Field(..., description="メディアフック名（日本語）")
    score: EvaluationScore = Field(..., description="5段階評価スコア")
    description: str = Field(..., description="評価の説明")
    examples: List[str] = Field(default_factory=list, description="改善例")
    current_elements: List[str] = Field(default_factory=list, description="現在含まれている要素")


class ParagraphImprovement(BaseModel):
    """段落ごとの改善提案"""
    paragraph_index: int = Field(..., ge=0, description="段落のインデックス（0から開始）")
    original_text: str = Field(..., description="元のテキスト")
    improved_text: Optional[str] = Field(None, description="改善後のテキスト案")
    improvements: List[str] = Field(default_factory=list, description="改善点のリスト")
    priority: ImprovementPriority = Field(..., description="改善優先度")
    applicable_hooks: List[MediaHookType] = Field(
        default_factory=list,
        description="この段落に適用可能なメディアフック"
    )

class OverallAssessment(BaseModel):
    """全体評価サマリー"""
    total_score: float = Field(..., ge=0, le=5, description="総合スコア（0-5）")
    strengths: List[str] = Field(default_factory=list, description="強み")
    weaknesses: List[str] = Field(default_factory=list, description="改善が必要な点")
    top_recommendations: List[str] = Field(default_factory=list, description="最優先の改善推奨事項")
    estimated_impact: str = Field(..., description="改善による期待される影響")


class PressReleaseAnalysisResponse(BaseModel):
    """プレスリリース分析結果のレスポンス"""
    request_id: str = Field(..., description="リクエストID（トラッキング用）")
    analyzed_at: datetime = Field(default_factory=datetime.now, description="分析実行日時")

    # メイン分析結果
    media_hook_evaluations: List[MediaHookEvaluation] = Field(
        ...,
        description="9つのメディアフックに対する評価",
        min_length=9,
        max_length=9
    )
    paragraph_improvements: List[ParagraphImprovement] = Field(
        ...,
        description="段落ごとの改善提案"
    )
    overall_assessment: OverallAssessment = Field(..., description="全体評価サマリー")

    # 追加情報
    processing_time_ms: Optional[int] = Field(None, description="処理時間（ミリ秒）")
    ai_model_used: Optional[str] = Field(None, description="使用したAIモデル")

    @field_validator('media_hook_evaluations')
    def validate_all_hooks_present(cls, v):
        """全てのメディアフックが評価されているか確認"""
        hook_types = {eval.hook_type for eval in v}
        expected_hooks = set(MediaHookType)
        if hook_types != expected_hooks:
            missing = expected_hooks - hook_types
            raise ValueError(f"Missing evaluations for hooks: {', '.join(m.value for m in missing)}")
        return v