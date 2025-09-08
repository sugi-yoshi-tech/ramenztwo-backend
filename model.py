"""
プレスリリース改善WebアプリケーションのAPIデータ型定義
FastAPI用のPydanticモデル
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, HttpUrl, validator
from datetime import datetime
from enum import Enum


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
    url: Optional[HttpUrl] = Field(None, description="画像URL")
    base64_data: Optional[str] = Field(None, description="Base64エンコードされた画像データ")
    mime_type: Optional[str] = Field(None, description="画像のMIMEタイプ (例: image/jpeg)")
    alt_text: Optional[str] = Field(None, description="画像の代替テキスト")
    
    @validator('base64_data')
    def validate_base64(cls, v):
        if v and not v.startswith('data:'):
            # Base64データにプレフィックスがない場合は追加
            return f"data:image/jpeg;base64,{v}"
        return v
    
    class Config:
        schema_extra = {
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
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="追加メタデータ")


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
    
    class Config:
        schema_extra = {
            "example": {
                "hook_type": "novelty_uniqueness",
                "hook_name_ja": "新規性・独自性",
                "score": 4,
                "description": "「日本初」という強力な新規性アピールがあります",
                "examples": ["業界初の試み", "特許取得済み"],
                "current_elements": ["日本初", "サブスクサービス"]
            }
        }


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
    
    class Config:
        schema_extra = {
            "example": {
                "paragraph_index": 0,
                "original_text": "当社は新サービスを開始しました。",
                "improved_text": "当社は本日、日本初となるヴィーガン惣菜のサブスクリプションサービスを開始しました。",
                "improvements": [
                    "具体的な日付を追加",
                    "「日本初」という新規性を強調",
                    "サービス内容を明確化"
                ],
                "priority": "high",
                "applicable_hooks": ["novelty_uniqueness", "trending_seasonal"]
            }
        }


class OverallAssessment(BaseModel):
    """全体評価サマリー"""
    total_score: float = Field(..., ge=0, le=5, description="総合スコア（0-5）")
    strengths: List[str] = Field(default_factory=list, description="強み")
    weaknesses: List[str] = Field(default_factory=list, description="改善が必要な点")
    top_recommendations: List[str] = Field(default_factory=list, description="最優先の改善推奨事項")
    estimated_impact: str = Field(..., description="改善による期待される影響")
    
    class Config:
        schema_extra = {
            "example": {
                "total_score": 3.5,
                "strengths": ["新規性が明確", "ターゲットが明確"],
                "weaknesses": ["ビジュアル要素が不足", "地域性の訴求が弱い"],
                "top_recommendations": [
                    "インパクトのある画像を追加",
                    "具体的な数値データを含める",
                    "季節性を意識したタイミング調整"
                ],
                "estimated_impact": "メディア掲載率が30-50%向上する可能性"
            }
        }


class PressReleaseAnalysisResponse(BaseModel):
    """プレスリリース分析結果のレスポンス"""
    request_id: str = Field(..., description="リクエストID（トラッキング用）")
    analyzed_at: datetime = Field(default_factory=datetime.now, description="分析実行日時")
    
    # メイン分析結果
    media_hook_evaluations: List[MediaHookEvaluation] = Field(
        ..., 
        description="9つのメディアフックに対する評価",
        min_items=9,
        max_items=9
    )
    paragraph_improvements: List[ParagraphImprovement] = Field(
        ..., 
        description="段落ごとの改善提案"
    )
    overall_assessment: OverallAssessment = Field(..., description="全体評価サマリー")
    
    # 追加情報
    processing_time_ms: Optional[int] = Field(None, description="処理時間（ミリ秒）")
    ai_model_used: Optional[str] = Field(None, description="使用したAIモデル")
    
    @validator('media_hook_evaluations')
    def validate_all_hooks_present(cls, v):
        """全てのメディアフックが評価されているか確認"""
        hook_types = {eval.hook_type for eval in v}
        expected_hooks = set(MediaHookType)
        if hook_types != expected_hooks:
            missing = expected_hooks - hook_types
            raise ValueError(f"Missing evaluations for hooks: {missing}")
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "request_id": "req_12345",
                "analyzed_at": "2024-01-15T10:30:00",
                "media_hook_evaluations": [
                    {
                        "hook_type": "trending_seasonal",
                        "hook_name_ja": "時流・季節性",
                        "score": 3,
                        "description": "季節性の要素が弱い",
                        "examples": ["春の新生活に向けて", "年末年始キャンペーン"],
                        "current_elements": []
                    }
                    # ... 他8つのフック評価
                ],
                "paragraph_improvements": [
                    {
                        "paragraph_index": 0,
                        "original_text": "当社は新サービスを開始しました。",
                        "improved_text": "当社は本日、日本初となる...",
                        "improvements": ["具体性を追加"],
                        "priority": "high",
                        "applicable_hooks": ["novelty_uniqueness"]
                    }
                ],
                "overall_assessment": {
                    "total_score": 3.5,
                    "strengths": ["新規性が明確"],
                    "weaknesses": ["ビジュアル要素が不足"],
                    "top_recommendations": ["画像を追加"],
                    "estimated_impact": "掲載率30%向上の可能性"
                },
                "processing_time_ms": 1500,
                "ai_model_used": "gpt-4"
            }
        }


# ================================================================================
# Error Response Models
# ================================================================================

class ErrorDetail(BaseModel):
    """エラー詳細"""
    code: str = Field(..., description="エラーコード")
    message: str = Field(..., description="エラーメッセージ")
    field: Optional[str] = Field(None, description="エラーが発生したフィールド")
    
    class Config:
        schema_extra = {
            "example": {
                "code": "INVALID_MARKDOWN",
                "message": "Markdownの形式が不正です",
                "field": "content_markdown"
            }
        }


class ErrorResponse(BaseModel):
    """エラーレスポンス"""
    error: ErrorDetail = Field(..., description="エラー詳細")
    request_id: Optional[str] = Field(None, description="リクエストID")
    
    class Config:
        schema_extra = {
            "example": {
                "error": {
                    "code": "PROCESSING_ERROR",
                    "message": "分析処理中にエラーが発生しました"
                },
                "request_id": "req_12345"
            }
        }


# ================================================================================
# Database Models (将来的なDB移行用)
# ================================================================================

class PressReleaseRecord(BaseModel):
    """DBに保存するプレスリリースレコード"""
    id: Optional[int] = Field(None, description="レコードID")
    request_id: str = Field(..., description="リクエストID")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    
    # 入力データ
    input_data: PressReleaseInput
    
    # 分析結果
    analysis_result: Optional[PressReleaseAnalysisResponse] = None
    
    # ステータス
    status: str = Field(default="pending", description="処理ステータス")
    
    class Config:
        orm_mode = True  # SQLAlchemyモデルとの互換性のため