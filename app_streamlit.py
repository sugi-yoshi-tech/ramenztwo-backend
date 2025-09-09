import streamlit as st
import requests
from datetime import datetime, timedelta

# --------------------------------------------------------------------------
# アプリケーションの基本設定
# --------------------------------------------------------------------------

# FastAPIサーバーのエンドポイントURL
API_BASE_URL = "http://127.0.0.1:8000"
COMPANIES_URL = f"{API_BASE_URL}/companies"
ANALYZE_URL = f"{API_BASE_URL}/analyze"

# Streamlitページのレイアウト設定
st.set_page_config(
    page_title="プレスリリース改善AI",
    page_icon="🤖",
    layout="wide"
)

# --------------------------------------------------------------------------
# API通信を行う関数
# --------------------------------------------------------------------------

@st.cache_data
def get_companies():
    """企業一覧を取得する"""
    try:
        response = requests.get(COMPANIES_URL, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"企業一覧の取得に失敗しました。APIサーバーが起動しているか確認してください。\n\n詳細: {e}")
        return []

# 日付範囲もキャッシュのキーに含めるため、引数に追加
@st.cache_data
def get_releases(company_id, from_date, to_date):
    """指定された企業のプレスリリース一覧を、指定された期間で取得する"""
    if not company_id:
        return []
    
    releases_url = f"{API_BASE_URL}/companies/{company_id}/releases"
    # 引数で受け取った日付を文字列に変換してパラメータとして使用
    params = {
        "from_date": from_date.strftime('%Y-%m-%d'),
        "to_date": to_date.strftime('%Y-%m-%d')
    }
    
    try:
        response = requests.get(releases_url, params=params, timeout=60)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"記事一覧の取得に失敗しました: {e}")
        return []

# --------------------------------------------------------------------------
# セッション管理
# --------------------------------------------------------------------------
if 'companies' not in st.session_state:
    st.session_state.companies = []
if 'selected_company_id' not in st.session_state:
    st.session_state.selected_company_id = None
if 'releases' not in st.session_state:
    st.session_state.releases = []
if 'selected_release' not in st.session_state:
    st.session_state.selected_release = None

# --------------------------------------------------------------------------
# UIの定義
# --------------------------------------------------------------------------

st.title("🤖 プレスリリース改善AI アナライザー")
st.markdown("AIがプレスリリースをメディアフックの観点から分析し、具体的な改善点を提案します。")
st.sidebar.info("このアプリを動作させるには、別ターミナルでFastAPIサーバー(`uvicorn main:app --reload`)を起動しておく必要があります。")

st.divider()

# --- ステップ1 & 2: 記事のインポート ---
st.header("Step 1: PR TIMESから記事を選択")

if st.button("企業一覧を読み込む", key="load_companies"):
    with st.spinner("企業一覧を取得中..."):
        st.session_state.companies = get_companies()

if st.session_state.companies:
    selected_company = st.selectbox(
        "分析したい企業を選択してください",
        options=st.session_state.companies,
        format_func=lambda company: f"{company['company_name']} (ID: {company['company_id']})",
        index=None,
        placeholder="企業を選択...",
    )
    
    # 企業が選択されたら、日付選択UIを表示
    if selected_company:
        st.session_state.selected_company_id = selected_company['company_id']

        col1, col2 = st.columns(2)
        with col1:
            from_date_input = st.date_input("検索開始日", value=datetime.now() - timedelta(days=365))
        with col2:
            to_date_input = st.date_input("検索終了日", value=datetime.now())

        if st.button("この期間の記事を検索する", type="secondary", use_container_width=True):
            if from_date_input > to_date_input:
                st.error("検索開始日は終了日より前の日付に設定してください。")
            else:
                with st.spinner(f"{selected_company['company_name']}の記事を読み込んでいます..."):
                    # 選択された日付を渡して記事を取得
                    st.session_state.releases = get_releases(
                        st.session_state.selected_company_id, 
                        from_date_input, 
                        to_date_input
                    )
                    st.session_state.selected_release = None

# リリース一覧が読み込まれたら、選択肢を表示
if st.session_state.releases:
    st.session_state.selected_release = st.selectbox(
        "分析したい記事を選択してください",
        options=st.session_state.releases,
        format_func=lambda release: f"[{release['created_at'][:10]}] {release['title']}",
        index=None,
        placeholder="記事を選択...",
    )
elif st.session_state.selected_company_id:
    st.info("条件に合う記事が見つかりませんでした。期間を変えて再検索してください。")


st.divider()

# --- ステップ3: 分析の実行 ---
st.header("Step 2: プレスリリースの分析を実行")

title_default = ""
content_default = ""
if st.session_state.selected_release:
    title_default = st.session_state.selected_release.get('title', '')
    content_default = st.session_state.selected_release.get('body', '')

with st.form("press_release_form"):
    title = st.text_input("タイトル*", value=title_default)
    content_markdown = st.text_area("本文*", value=content_default, height=300)
    with st.expander("詳細オプション（画像情報・ペルソナなど）"):
        metadata_persona = st.text_input("ターゲットペルソナ", value="中小企業のカスタマーサポート部門長")
    submitted = st.form_submit_button("分析を実行 →", type="primary", use_container_width=True)

# --- 分析結果の表示 (変更なし) ---
if submitted:
    if not title.strip() or not content_markdown.strip():
        st.warning("タイトルと本文の両方を入力してください。")
    else:
        with st.spinner("AIが分析中です... しばらくお待ちください..."):
            # (以下、結果表示のロジックは変更ありません)
            payload = {
                "title": title,
                "content_markdown": content_markdown,
                "metadata": {"persona": metadata_persona if metadata_persona.strip() else "指定なし"}
            }
            try:
                response = requests.post(ANALYZE_URL, json=payload, timeout=120)
                response.raise_for_status()
                results = response.json()
                st.success("分析が完了しました！")
                
                st.divider()
                col1, col2 = st.columns([1, 1])
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
                with col2:
                    st.subheader("🎣 9つのメディアフック評価")
                    for hook in sorted(results["media_hook_evaluations"], key=lambda x: x['score']):
                        score = hook['score']
                        emoji = "🔻" if score <= 2 else ("🔸" if score == 3 else "🔼")
                        with st.expander(f"{emoji} **{hook['hook_name_ja']}** (スコア: **{score}** / 5)"):
                            st.markdown(f"**評価:** {hook['description']}")
                            if hook['improve_examples']:
                                st.markdown(f"**改善例:**")
                                for ex in hook['improve_examples']:
                                    st.markdown(f"- `{ex}`")
                            if hook['current_elements']:
                                st.markdown(f"**現在の該当箇所:** {', '.join(hook['current_elements'])}")
                st.divider()
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