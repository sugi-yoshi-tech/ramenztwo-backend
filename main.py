import os
import base64
import json
from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from pydantic import BaseModel, Field
from openai import AsyncOpenAI
from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
load_dotenv()

# FastAPIアプリケーションのインスタンスを作成
app = FastAPI(
    title="Image Analysis API with FastAPI",
    description="画像とテキストを受け取り、ChatGPT(gpt-4o)で分析してJSON形式で返すAPI",
    version="2.0.0",
)

# OpenAI APIキーを環境変数から取得
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("環境変数 `OPENAI_API_KEY` が設定されていません。")

# 非同期対応のOpenAIクライアントを初期化
client = AsyncOpenAI(api_key=api_key)


# --- APIエンドポイントの作成 ---
@app.post("/analyze_image")
async def analyze_image(
    text: str = Form(..., description="画像に対して行う指示や質問を記述します。"),
    image: UploadFile = File(..., description="分析対象の画像ファイル。")
):
    """
    画像とテキストを受け取り、分析結果をJSON形式で返すエンドポイント
    """
    # アップロードされたファイルが画像かどうかの簡単なチェック
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="アップロードされたファイルは画像形式ではありません。")

    # 画像ファイルを読み込み、Base64にエンコード
    image_bytes = await image.read()
    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    base64_image_url = f"data:{image.content_type};base64,{base64_image}"

    # サーバー側でプロンプトを定義
    # ここでChatGPTの役割と、返すJSONの構造を厳密に指示します
    SYSTEM_PROMPT = """
あなたは優秀な画像分析AIです。ユーザーから送られてくる画像とテキストに基づき、以下のタスクを実行してください。
レスポンスは必ず指定されたJSON形式で、他のテキストは一切含めずに返してください。

{
  "description": "画像の内容を詳細に説明してください。",
  "objects": ["画像に写っている主要なオブジェクトをリスト形式で列挙してください。"],
  "analysis": "ユーザーからの指示や質問に対する分析結果や回答をここに記述してください。"
}
"""
    try:
        # ChatGPT API (Visionモデル) を非同期で呼び出す
        completion = await client.chat.completions.create(
            # 画像入力に対応したモデルを指定 (gpt-4oが推奨)
            model="gpt-4o",
            # ★レスポンス形式をJSONに固定する設定
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        # ユーザーからのテキスト指示
                        {"type": "text", "text": text},
                        # Base64エンコードされた画像
                        {
                            "type": "image_url",
                            "image_url": {"url": base64_image_url}
                        }
                    ]
                }
            ],
            max_tokens=1500,
        )

        response_content = completion.choices[0].message.content

        if response_content is None:
             raise HTTPException(status_code=500, detail="APIから有効なレスポンスが得られませんでした。")

        # 文字列として返ってきたJSONをパースして辞書型に変換
        # FastAPIが自動で辞書をJSONレスポンスに変換してくれます
        return json.loads(response_content)

    except Exception as e:
        print(f"エラーが発生しました: {e}")
        raise HTTPException(status_code=500, detail="処理中にサーバーエラーが発生しました。")

# サーバーの動作確認用エンドポイント
@app.get("/")
def read_root():
    return {"message": "サーバーは正常に起動しています。"}