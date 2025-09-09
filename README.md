# プレスリリース改善AI API & アナライザー

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-green?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.25%2B-red?logo=streamlit)](https://streamlit.io/)

## 概要

このプロジェクトは、プレスリリースの内容をAIが多角的に分析し、メディアフック（報道価値）の観点から具体的な改善提案を行うためのバックエンドAPI（FastAPI）と、インタラクティブな分析ツール（Streamlit）を提供します。

### 主な機能

* **AIによるプレスリリース分析**:
    * OpenAIのGPTモデル (`gpt-4o`) を利用して、タイトルの魅力、本文の構成、画像のインパクトなどを9つのメディアフックに基づいて評価します。
    * 段落ごとの具体的な改善案や、全体的な強み・弱みを提示します。
* **類似記事の推薦**:
    * ローカルで動作する`embedding-gemma`モデルを利用して、分析対象の記事と類似した内容の記事をデータベースから検索・推薦します。
* **柔軟なデータソース**:
    * PR TIMES APIと内部データベースの両方から企業情報やリリース情報を取得可能。API経由でのリアルタイムな情報取得と、DBからの高速なキーワード検索を両立します。
* **インタラクティブなUI**:
    * Streamlit製のWebアプリケーションを通じて、誰でも簡単にプレスリリースの選択から分析実行、結果の確認までを行えます。

---

## 技術スタック

| カテゴリ         | 技術                                                                                                        | 目的                             |
| ---------------- | ----------------------------------------------------------------------------------------------------------- | -------------------------------- |
| **バックエンド** | FastAPI, Uvicorn                                                                                            | APIサーバーの構築                |
| **AI・機械学習** | OpenAI API (`gpt-4o`), `embedding-gemma-300M`, Sentence Transformers, PyTorch                               | プレスリリース分析、類似記事のベクトル化 |
| **フロントエンド** | Streamlit                                                                                                   | 分析用Webアプリケーションの構築      |
| **データベース** | PostgreSQL, psycopg2                                                                                        | 企業・記事データの永続化と検索     |
| **型定義** | Pydantic                                                                                                    | APIの型安全性の担保とバリデーション  |
| **その他** | python-dotenv, httpx                                                                                        | 環境変数管理、非同期HTTPリクエスト  |

---

## セットアップ手順

### 1. リポジトリのクローン

```bash
git clone <your-repository-url>
cd <your-repository-directory>

2. 仮想環境の作成と有効化
Bash

python -m venv venv
source venv/bin/activate  # macOS / Linux
# venv\Scripts\activate    # Windows

3. 必要なライブラリのインストール
requirements.txtを使用して、依存ライブラリを一括でインストールします。

Bash

pip install -r requirements.txt

4. 環境変数の設定
プロジェクトルートに.envファイルを作成し、以下の内容を記述・編集してください。

Ini, TOML

# OpenAI API
OPENAI_API_KEY="sk-..."
OPENAI_MODEL="gpt-4o"

# PR TIMES API
PRTIMES_ACCESS_TOKEN="..."

# Hugging Face (EmbeddingGemmaモデルダウンロード用)
HUGGING_FACE_TOKEN="hf_..."

# PostgreSQL Database Connection
DB_HOST="localhost"
DB_PORT="5432"
DB_USER="your_db_user"
DB_PASSWORD="your_db_password"
DB_NAME="your_db_name"

5. FastAPIサーバーの起動
Bash

uvicorn main:app --reload
サーバーはデフォルトで http://127.0.0.1:8000 で起動します。
起動時にEmbeddingGemmaモデルがダウンロード・ロードされるため、初回は時間がかかる場合があります。

6. Streamlitアプリケーションの起動
別のターミナルを開き、以下のコマンドを実行します。

Bash

streamlit run app_streamlit.py
ブラウザで http://localhost:8501 が自動的に開かれ、分析ツールを使用できます。

APIエンドポイント
APIドキュメントは、FastAPIサーバー起動後に http://127.0.0.1:8000/docs からアクセスできます。

メソッド	エンドポイント	説明
GET	/companies	企業一覧を取得します (source=api or db, keyword=...)。
GET	/companies/{company_id}/releases	指定された企業のプレスリリース一覧を取得します (source=api or db, keyword=...)。
POST	/analyze	プレスリリースの本文やタイトルを送信し、AIによる詳細な分析結果を受け取ります。
GET	/releases/{release_id}/similar	指定された記事IDに基づき、データベース内から類似した記事をtop_k件返します。

Google スプレッドシートにエクスポート
使い方
FastAPIサーバーとStreamlitアプリの両方を起動します。

Streamlitの画面（http://localhost:8501）にアクセスします。

Step 1でデータソース（API or DB）を選択し、「企業一覧を読み込む」ボタンをクリックします。

企業と分析したい記事をドロップダウンから選択します。

Step 2で「分析を実行」ボタンをクリックすると、AIによる分析が開始されます。

分析完了後、評価スコア、改善提案、そしてAIが推薦する類似記事が表示されます。