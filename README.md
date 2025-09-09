# ramenztwo-frontend

PRTimes Hackathon Summer

プレスリリース改善 AI (Press Release Analysis AI)

## 概要

このプロジェクトは、プレスリリースの内容をメディアフックの観点から AI が分析し、具体的な改善点を提案する FastAPI アプリケーションと、その API を利用するための Streamlit 製 Web UI を提供します。

入力されたプレスリリースのタイトルと本文を基に、9 つのメディアフック要素を 5 段階で評価し、全体および段落ごとの改善案を構造化された JSON 形式で返却します。これにより、広報担当者はよりメディアの目に留まりやすい、訴求力の高いプレスリリースを作成できます。

### 主な機能 ✨

メディアフック 9 要素の定量的評価: 各要素を 1〜5 のスコアで評価し、客観的な分析を提供します。

段落ごとの具体的改善案: 本文の各段落に対し、改善後のテキスト案や改善点を提案します。

全体サマリー: プレスリリース全体の強み・弱み、総合スコア、最優先の改善点を提示します。

対話的な Web UI: Streamlit 製の UI で、手軽に分析を実行し、結果を視覚的に確認できます。

厳密な型定義: Pydantic による厳密な入出力の型定義により、安定した API レスポンスを保証します。

AI による高精度分析: instructor ライブラリと OpenAI の LLM を活用し、高品質な分析結果を生成します。

### 技術スタック

フレームワーク: FastAPI, Streamlit

データ検証: Pydantic

LLM 連携: Instructor, OpenAI

サーバー: Uvicorn

---

## 必要環境

- [uv](https://github.com/astral-sh/uv)（依存関係管理・仮想環境の作成に使用）
- OpenAI API キー

## セットアップ手順 🚀

### 1. リポジトリをクローン

```bash
git clone https://github.com/sugi-yoshi-tech/ramenztwo-backend.git
cd ramenztwo-backend
```

### 2. 依存関係のインストール

```bash
uv sync
```

### 3. 仮想環境に入る

Mac, Linux:

```bash
source .venv/bin/activate
```

Windows:

```bash
.venv\Scripts\activate
```

### 4. 環境変数を設定する

```bash
cp ./.env.sample ./.env
```

コピー後、以下のように環境変数を設定してください。

```bash
OPENAI_API_KEY="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

### 5. サーバーの起動

```bash
uvicorn main:app --reload
```

サーバーが起動すると、ターミナルに Uvicorn running on <http://127.0.0.1:8000> と表示されます。

### 6. API ドキュメントの確認

```bash
streamlit run app_streamlit.py
```

自動的にブラウザが開き、<http://localhost:8501> で操作画面が表示されます。

## API 仕様

### エンドポイント: POST /analyze

プレスリリースを分析し、改善案を返します。

リクエストボディ
application/json 形式で以下のデータを送信します。

```JSON
{
  "title": "当社、革新的な新サービス「AI コンシェルジュ」を発表",
  "top_image": {
    "url": "https://example.com/images/ai-concierge.jpg",
    "alt_text": "AI コンシェルジュのイメージ画像"
  },
  "content_markdown": "本日、株式会社サンプルは、顧客対応を自動化する画期的な新サービス「AI コンシェルジュ」の提供を開始したことを発表します。\n\n このサービスは、最新の自然言語処理技術を活用しており、24 時間 365 日、人間のような自然な対話で問い合わせに応じます。初期費用は無料で、月額 5 万円から利用可能です。",
  "metadata": {
    "persona": "中小企業のカスタマーサポート部門長"
  }
}
```

レスポンス
分析結果が PressReleaseAnalysisResponse モデルに基づいた JSON 形式で返されます。（models.py の定義に準拠）

```JSON
{
  "request_id": "req_a1b2c3d4-...",
  "analyzed_at": "2025-09-08T09:30:00.123Z",
  "media_hook_evaluations": [
    {
      "hook_type": "novelty_uniqueness",
      "hook_name_ja": "新規性・独自性",
      "score": 4,
      "description": "「画期的な新サービス」という表現で新規性を訴求できているが、他社との具体的な違いが不明確。",
      "improve_examples": [
        "「業界初」「特許取得済み」などのキーワードを追加する"
      ],
      "current_elements": [
        "画期的な新サービス",
        "最新の自然言語処理技術"
      ]
    }
    // ... 他 8 つのメディアフック評価
  ],
  "paragraph_improvements": [
    {
      "paragraph_index": 0,
      "original_text": "本日、株式会社サンプルは、顧客対応を自動化する画期的な新サービス「AI コンシェルジュ」の提供を開始したことを発表します。",
      "improved_text": "株式会社サンプルは本日 9 月 8 日、AI が顧客対応を完全自動化する、業界初の SaaS 型サービス「AI コンシェルジュ」の提供を開始します。",
      "improvements": [
        "具体的な日付を追加",
        "「業界初」で新規性を強調",
        "SaaS 型サービスであることを明記"
      ],
      "priority": "high",
      "applicable_hooks": [
        "novelty_uniqueness",
        "trending_seasonal"
      ]
    }
    // ... 他の段落の改善提案
  ],
  "overall_assessment": {
    "total_score": 3.2,
    "strengths": [
      "サービス内容が明確"
    ],
    "weaknesses": [
      "社会性や意外性の要素が不足",
      "具体的な導入効果のデータがない"
    ],
    "top_recommendations": [
      "導入事例や具体的な数値をタイトルに追加する",
      "社会的な課題（例：人手不足）と関連付ける"
    ],
    "estimated_impact": "見出しのクリック率が 20%向上し、メディアからの問い合わせが増加する可能性。"
  },
  "processing_time_ms": 4580,
  "ai_model_used": "gpt-4o"
}
```

ファイル構成
.
├── .env # 環境変数ファイル（API キーなどを格納）
├── main.py # FastAPI アプリケーション本体
├── models.py # Pydantic による API のデータモデル定義
├── app_streamlit.py # Streamlit 製のフロントエンド UI
├── requirements.txt # プロジェクトの依存ライブラリ
└── README.md # このファイル
