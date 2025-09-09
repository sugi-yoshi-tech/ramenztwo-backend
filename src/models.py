"""
プレスリリース改善WebアプリケーションのAPIデータ型定義
FastAPI用のPydanticモデル
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

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

    url: Optional[str] = Field(None, description="画像URL")
    # base64_dataフィールドを削除したため、関連するバリデータも削除しました。

    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://example.com/image.jpg",
            }
        }


class MetadataInput(BaseModel):
    """メタデータ（ペルソナ情報）"""

    persona: str = Field("指定なし", description="ターゲットペルソナ")


class PressReleaseInput(BaseModel):
    """プレスリリース入力データ"""

    title: str = Field(..., min_length=1, max_length=200, description="記事のタイトル")
    top_image: Optional[ImageData] = Field(None, description="トップ画像")
    content_markdown: str = Field(
        ..., min_length=1, description="プレスリリース本文（Markdown形式）"
    )
    metadata: MetadataInput


# ================================================================================
# Response Models (出力データ)
# ================================================================================


class MediaHookEvaluation(BaseModel):
    """メディアフック評価"""

    hook_type: MediaHookType = Field(..., description="メディアフックの種類")
    hook_name_ja: str = Field(..., description="メディアフック名（日本語）")
    score: EvaluationScore = Field(..., description="5段階評価スコア")
    description: str = Field(..., description="評価の説明")
    improve_examples: List[str] = Field(default_factory=list, description="改善例")
    current_elements: List[str] = Field(
        default_factory=list, description="現在含まれている要素"
    )


class ParagraphImprovement(BaseModel):
    """段落ごとの改善提案"""

    paragraph_index: int = Field(
        ..., ge=0, description="段落のインデックス（0から開始）"
    )
    original_text: str = Field(..., description="元のテキスト")
    improved_text: Optional[str] = Field(None, description="改善後のテキスト案")
    improvements: List[str] = Field(default_factory=list, description="改善点のリスト")
    priority: ImprovementPriority = Field(..., description="改善優先度")
    applicable_hooks: List[MediaHookType] = Field(
        default_factory=list, description="この段落に適用可能なメディアフック"
    )


class OverallAssessment(BaseModel):
    """全体評価サマリー"""

    total_score: float = Field(..., ge=0, le=5, description="総合スコア（0-5）")
    strengths: List[str] = Field(default_factory=list, description="強み")
    weaknesses: List[str] = Field(default_factory=list, description="改善が必要な点")
    top_recommendations: List[str] = Field(
        default_factory=list, description="最優先の改善推奨事項"
    )
    estimated_impact: str = Field(..., description="改善による期待される影響")


class PressReleaseAnalysisResponse(BaseModel):
    """プレスリリース分析結果のレスポンス"""

    request_id: str = Field(..., description="リクエストID（トラッキング用）")
    analyzed_at: datetime = Field(
        default_factory=datetime.now, description="分析実行日時"
    )

    # メイン分析結果
    media_hook_evaluations: List[MediaHookEvaluation] = Field(
        ..., description="9つのメディアフックに対する評価", min_length=9, max_length=9
    )
    paragraph_improvements: List[ParagraphImprovement] = Field(
        ..., description="段落ごとの改善提案"
    )
    overall_assessment: OverallAssessment = Field(..., description="全体評価サマリー")

    # 追加情報
    processing_time_ms: Optional[int] = Field(None, description="処理時間（ミリ秒）")
    ai_model_used: Optional[str] = Field(None, description="使用したAIモデル")

    @field_validator("media_hook_evaluations")
    def validate_all_hooks_present(cls, v):
        """全てのメディアフックが評価されているか確認"""
        hook_types = {eval.hook_type for eval in v}
        expected_hooks = set(MediaHookType)
        if hook_types != expected_hooks:
            missing = expected_hooks - hook_types
            raise ValueError(
                f"Missing evaluations for hooks: {', '.join(m.value for m in missing)}"
            )
        return v


# ================================================================================
# PR TIMES API Response Models
# ================================================================================


class Company(BaseModel):
    """PR TIMES APIから取得する企業情報"""

    company_id: int
    company_name: str
    president_name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    description: Optional[str] = None
    industry: Optional[str] = None
    ipo_type: Optional[str] = None
    capital: Optional[int] = None
    foundation_date: Optional[str] = None
    url: Optional[str] = None
    twitter_screen_name: Optional[str] = None


class PressRelease(BaseModel):
    """PR TIMES APIから取得するプレスリリース情報"""

    company_name: str
    company_id: int
    release_id: int
    title: str
    subtitle: Optional[str] = None
    url: str
    lead_paragraph: Optional[str] = None
    body: Optional[str] = None
    main_image: Optional[str] = None
    main_image_fastly: Optional[str] = None
    main_category_id: Optional[int] = None
    main_category_name: Optional[str] = None
    sub_category_id: Optional[int] = None
    sub_category_name: Optional[str] = None
    release_type: Optional[str] = None
    created_at: str
    like: Optional[int] = None
