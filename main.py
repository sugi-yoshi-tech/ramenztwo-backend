import os
import instructor
import uuid
import time
from fastapi import FastAPI, HTTPException, Body
from openai import AsyncOpenAI
from dotenv import load_dotenv

# models.pyから定義したデータ型をインポート
from models import PressReleaseInput, PressReleaseAnalysisResponse, MediaHookType

# .envファイルから環境変数を読み込む
load_dotenv()
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o") # 環境変数からモデル名を取得、なければgpt-4o

# instructorでOpenAIクライアントをパッチ
# APIキーが設定されていない場合はエラーを出す
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY is not set in the environment variables.")

client = instructor.patch(AsyncOpenAI(api_key=api_key))

# FastAPIアプリケーションのインスタンスを作成
app = FastAPI(
    title="Press Release Analysis API",
    description="最新のデータ型定義に基づき、プレスリリースをメディアフックの観点から分析し、改善点を提案するAPI",
    version="3.0.0",
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


@app.post("/analyze", response_model=PressReleaseAnalysisResponse)
async def analyze_press_release(
    # Bodyから直接PressReleaseInputモデルを受け取る
    data: PressReleaseInput = Body(...)
):
    """
    プレスリリースをメディアフックの観点から分析し、評価と改善点を構造化JSONで返すエンドポイント
    """
    request_id = f"req_{uuid.uuid4()}"
    start_time = time.time()

    try:
        # Markdown本文を段落に分割（空行で分割）
        paragraphs = [p.strip() for p in data.content_markdown.split('\n\n') if p.strip()]
        
        # AIへの指示（プロンプト）を作成
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

        # 処理時間と固定情報をレスポンスに追加
        end_time = time.time()
        analysis_result.request_id = request_id
        analysis_result.processing_time_ms = int((end_time - start_time) * 1000)
        analysis_result.ai_model_used = MODEL
        
        # hook_name_jaを辞書から補完
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