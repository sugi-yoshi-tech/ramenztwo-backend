プレスリリース改善API (Press Release Analysis API)

概要
このプロジェクトは、プレスリリースの内容をメディアフックの観点からAIが分析し、具体的な改善点を提案するFastAPIアプリケーションです。

入力されたプレスリリースのタイトル、本文、画像情報などを基に、9つのメディアフック要素を5段階で評価し、全体および段落ごとの改善案を構造化されたJSON形式で返却します。これにより、広報担当者はよりメディアの目に留まりやすい、訴求力の高いプレスリリースを作成できます。

主な機能 ✨
メディアフック9要素の定量的評価: 各要素を1〜5のスコアで評価し、客観的な分析を提供します。

段落ごとの具体的改善案: 本文の各段落に対し、改善後のテキスト案や改善点を提案します。

全体サマリー: プレスリリース全体の強み・弱み、総合スコア、最優先の改善点を提示します。

厳密な型定義: Pydanticによる厳密な入出力の型定義により、安定したAPIレスポンスを保証します。

AIによる高精度分析: instructorライブラリとOpenAIのLLMを活用し、高品質な分析結果を生成します。

セットアップ手順 🚀
1. 前提条件
Python 3.9以上

pip (Pythonのパッケージ管理ツール)

OpenAI APIキー

2. リポジトリのクローン
Bash

git clone https://github.com/your-username/press-release-analyzer.git
cd press-release-analyzer
3. 依存関係のインストール
プロジェクトルートで以下のコマンドを実行し、必要なライブラリをインストールします。

Bash

pip install "fastapi[all]" python-dotenv openai "instructor>=1.0.0"
4. 環境変数の設定
プロジェクトルートに .env という名前のファイルを作成し、以下のようにOpenAIのAPIキーを記述します。

.env

コード スニペット

# .env
OPENAI_API_KEY="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
OPENAI_MODEL="gpt-4o" # (オプション) 使用するモデルを指定
実行方法 サーバーの起動
以下のコマンドでAPIサーバーを起動します。--reloadフラグにより、コードの変更が即座に反映されます。

Bash

uvicorn main:app --reload
サーバーが起動すると、ターミナルに Uvicorn running on http://127.0.0.1:8000 と表示されます。

ブラウザで http://127.0.0.1:8000/docs にアクセスすると、APIの対話的なドキュメント（Swagger UI）が表示され、そこから直接APIをテストできます。

API仕様
エンドポイント: POST /analyze
プレスリリースを分析し、改善案を返します。

リクエストボディ
application/json形式で以下のデータを送信します。

JSON

{
  "title": "当社、革新的な新サービス「AIコンシェルジュ」を発表",
  "top_image": {
    "url": "https://example.com/images/ai-concierge.jpg",
    "alt_text": "AIコンシェルジュのイメージ画像"
  },
  "content_markdown": "本日、株式会社サンプルは、顧客対応を自動化する画期的な新サービス「AIコンシェルジュ」の提供を開始したことを発表します。\n\nこのサービスは、最新の自然言語処理技術を活用しており、24時間365日、人間のような自然な対話で問い合わせに応じます。初期費用は無料で、月額5万円から利用可能です。",
  "metadata": {
    "persona": "中小企業のカスタマーサポート部門長"
  }
}
レスポンス
分析結果が PressReleaseAnalysisResponse モデルに基づいたJSON形式で返されます。

JSON

{
  "request_id": "req_a1b2c3d4-...",
  "analyzed_at": "2025-09-08T08:30:00.123Z",
  "media_hook_evaluations": [
    {
      "hook_type": "novelty_uniqueness",
      "hook_name_ja": "新規性・独自性",
      "score": 4,
      "description": "「画期的な新サービス」という表現で新規性を訴求できているが、他社との具体的な違いが不明確。",
      "examples": ["「業界初」「特許取得済み」などのキーワードを追加する"],
      "current_elements": ["画期的な新サービス", "最新の自然言語処理技術"]
    }
    // ... 他8つのメディアフック評価
  ],
  "paragraph_improvements": [
    {
      "paragraph_index": 0,
      "original_text": "本日、株式会社サンプルは、顧客対応を自動化する画期的な新サービス「AIコンシェルジュ」の提供を開始したことを発表します。",
      "improved_text": "株式会社サンプルは本日9月8日、AIが顧客対応を完全自動化する、業界初のSaaS型サービス「AIコンシェルジュ」の提供を開始します。",
      "improvements": ["具体的な日付を追加", "「業界初」で新規性を強調", "SaaS型サービスであることを明記"],
      "priority": "high",
      "applicable_hooks": ["novelty_uniqueness", "trending_seasonal"]
    }
    // ... 他の段落の改善提案
  ],
  "overall_assessment": {
    "total_score": 3.2,
    "strengths": ["サービス内容が明確"],
    "weaknesses": ["社会性や意外性の要素が不足", "具体的な導入効果のデータがない"],
    "top_recommendations": ["導入事例や具体的な数値をタイトルに追加する", "社会的な課題（例：人手不足）と関連付ける"],
    "estimated_impact": "見出しのクリック率が20%向上し、メディアからの問い合わせが増加する可能性。"
  },
  "processing_time_ms": 4580,
  "ai_model_used": "gpt-4o"
}
技術スタック
フレームワーク: FastAPI

データ検証: Pydantic

LLM連携: Instructor, OpenAI

サーバー: Uvicorn