import streamlit as st
import requests
import json

# --------------------------------------------------------------------------
# アプリケーションの基本設定
# --------------------------------------------------------------------------

# FastAPIサーバーのエンドポイントURL
API_URL = "http://127.0.0.1:8000/analyze"

# Streamlitページのレイアウト設定
st.set_page_config(
    page_title="プレスリリース改善AI",
    page_icon="🤖",
    layout="wide"
)

# --------------------------------------------------------------------------
# UIの定義
# --------------------------------------------------------------------------

st.title("🤖 プレスリリース改善AI アナライザー")
st.markdown("AIがプレスリリースをメディアフックの観点から分析し、具体的な改善点を提案します。")

# サイドバーに説明を記載
st.sidebar.header("📝 使い方")
st.sidebar.write("""
1.  プレスリリースの**タイトル**と**本文**を入力します。
2.  必要に応じて**詳細オプション**で画像情報やターゲットペルソナを設定します。
3.  **「分析を実行」**ボタンをクリックします。
4.  AIによる分析結果が右側に表示されるのを待ちます。
""")
st.sidebar.info("このアプリを動作させるには、別ターミナルでFastAPIサーバー(`uvicorn main:app --reload`)を起動しておく必要があります。")


# フォームを使用して入力と送信ボタンをグループ化
with st.form("press_release_form"):
    st.header("分析対象のプレスリリースを入力")

    # --- 基本入力 ---
    title = st.text_input(
        "タイトル*",
        value="当社、革新的な新サービス「AIコンシェルジュ」を発表"
    )
    content_markdown = st.text_area(
        "本文 (Markdown形式)*",
        value="""本日、株式会社サンプルは、顧客対応を自動化する画期的な新サービス「AIコンシェルジュ」の提供を開始したことを発表します。

このサービスは、最新の自然言語処理技術を活用しており、24時間365日、人間のような自然な対話で問い合わせに応じます。初期費用は無料で、月額5万円から利用可能です。""",
        height=300
    )

    # --- 詳細オプション（折りたたみ）---
    with st.expander("詳細オプション（画像情報・ペルソナなど）"):
        st.subheader("トップ画像の情報")
        image_url = st.text_input(
            "画像URL",
            value="https://example.com/images/ai-concierge.jpg"
        )
        image_alt_text = st.text_input(
            "画像の代替テキスト (alt)",
            value="AIコンシェルジュのイメージ画像"
        )

        st.subheader("メタデータ")
        metadata_persona = st.text_input(
            "ターゲットペルソナ",
            value="中小企業のカスタマーサポート部門長"
        )

    # 送信ボタン
    st.markdown("---")
    submitted = st.form_submit_button("分析を実行 →", type="primary")

# --------------------------------------------------------------------------
# API連携と結果表示のロジック
# --------------------------------------------------------------------------

# ボタンが押されたら処理を実行
if submitted:
    # 入力チェック
    if not title.strip() or not content_markdown.strip():
        st.warning("必須項目であるタイトルと本文の両方を入力してください。")
    else:
        with st.spinner("AIが分析中です... しばらくお待ちください..."):
            # APIに送信するデータを作成（入力欄から値を取得）
            payload = {
                "title": title,
                "content_markdown": content_markdown,
                "top_image": {
                    "url": image_url if image_url.strip() else None,
                    "alt_text": image_alt_text if image_alt_text.strip() else None
                },
                "metadata": {
                    "persona": metadata_persona if metadata_persona.strip() else "指定なし"
                }
            }

            try:
                # APIにPOSTリクエストを送信
                response = requests.post(API_URL, json=payload, timeout=120)
                response.raise_for_status() # エラーがあれば例外を発生させる

                results = response.json()
                st.success("分析が完了しました！")

                st.divider()

                # ----------------- 結果表示セクション -----------------
                
                # 2カラムレイアウトを作成
                col1, col2 = st.columns([1, 1])

                # --- 左カラム: 全体評価 ---
                with col1:
                    st.subheader("📊 全体評価サマリー")
                    assessment = results["overall_assessment"]
                    
                    st.metric("総合スコア", f"{assessment['total_score']:.1f} / 5.0")
                    
                    st.info(f"**📈 期待される効果:** {assessment['estimated_impact']}")
                    
                    with st.expander("👍 強み", expanded=True):
                        for strength in assessment["strengths"]:
                            st.write(f"・ {strength}")

                    with st.expander("⚠️ 改善が必要な点", expanded=True):
                        for weakness in assessment["weaknesses"]:
                            st.write(f"・ {weakness}")
                    
                    st.error("**🔥 最優先の改善推奨事項**")
                    for rec in assessment["top_recommendations"]:
                        st.markdown(f"**- {rec}**")

                # --- 右カラム: メディアフック評価 ---
                with col2:
                    st.subheader("🎣 9つのメディアフック評価")
                    for hook in sorted(results["media_hook_evaluations"], key=lambda x: x['score']):
                        score = hook['score']
                        # スコアに応じて色分け
                        if score <= 2:
                            emoji = "🔻"
                        elif score == 3:
                            emoji = "🔸"
                        else:
                            emoji = "🔼"
                        
                        with st.expander(f"{emoji} **{hook['hook_name_ja']}** (スコア: **{score}** / 5)"):
                            st.markdown(f"**評価:** {hook['description']}")
                            if hook['improve_examples']:
                                st.markdown(f"**改善例:**")
                                for ex in hook['improve_examples']:
                                    st.markdown(f"- `{ex}`")
                            if hook['current_elements']:
                                st.markdown(f"**現在の該当箇所:** {', '.join(hook['current_elements'])}")
                
                st.divider()

                # --- 段落ごとの改善提案 ---
                st.subheader("📝 段落ごとの改善提案")
                for p in results["paragraph_improvements"]:
                    st.markdown(f"#### 段落 {p['paragraph_index'] + 1} (改善優先度: `{p['priority']}`)")
                    
                    p_col1, p_col2 = st.columns(2)
                    with p_col1:
                        st.markdown("**元の文章**")
                        st.text_area("Original", value=p['original_text'], height=150, disabled=True, label_visibility="collapsed")
                    with p_col2:
                        st.markdown("**改善後の文章案**")
                        st.text_area("Improved", value=p.get('improved_text', '具体的な改善案はありません。'), height=150, disabled=True, label_visibility="collapsed")
                    
                    st.markdown("**改善点のポイント:**")
                    for point in p['improvements']:
                        st.markdown(f"- {point}")
                    st.markdown("---")


            except requests.exceptions.RequestException as e:
                st.error(f"APIサーバーへの接続に失敗しました。FastAPIサーバーが起動しているか確認してください。\n\n詳細: {e}")
            except Exception as e:
                st.error(f"分析中に予期せぬエラーが発生しました: {e}")