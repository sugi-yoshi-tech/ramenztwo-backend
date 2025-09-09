# app_streamlit.py (修正版)

import streamlit as st
import requests
from datetime import datetime, timedelta

# --------------------------------------------------------------------------
# アプリケーションの基本設定
# --------------------------------------------------------------------------
API_BASE_URL = "http://127.0.0.1:8000"
COMPANIES_URL = f"{API_BASE_URL}/companies"
ANALYZE_URL = f"{API_BASE_URL}/analyze"

st.set_page_config(page_title="プレスリリース改善AI", page_icon="🤖", layout="wide")

# --------------------------------------------------------------------------
# API通信を行う関数 (★修正)
# --------------------------------------------------------------------------
@st.cache_data
def get_companies(source="api", keyword=None): # ★修正: sourceとkeyword引数を追加
    try:
        params = {"source": source} # ★追加
        if source == "db" and keyword: # ★追加
            params["keyword"] = keyword
        
        response = requests.get(COMPANIES_URL, params=params, timeout=30) # ★修正: paramsを渡す
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"企業一覧の取得に失敗しました。APIサーバーが起動しているか確認してください。\n\n詳細: {e}")
        return []

@st.cache_data
def get_releases(company_id, from_date, to_date, source="api", keyword=None): # ★修正: sourceとkeyword引数を追加
    if not company_id: return []
    releases_url = f"{API_BASE_URL}/companies/{company_id}/releases"
    
    # ★修正: パラメータの組み立て
    params = {
        "from_date": from_date.strftime('%Y-%m-%d'), 
        "to_date": to_date.strftime('%Y-%m-%d'),
        "source": source
    }
    if source == "db" and keyword:
        params["keyword"] = keyword

    try:
        response = requests.get(releases_url, params=params, timeout=60)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"記事一覧の取得に失敗しました: {e}")
        return []

# --------------------------------------------------------------------------
# セッション管理 (変更なし)
# --------------------------------------------------------------------------
if 'companies' not in st.session_state: st.session_state.companies = []
if 'selected_company_id' not in st.session_state: st.session_state.selected_company_id = None
if 'releases' not in st.session_state: st.session_state.releases = []
if 'selected_release' not in st.session_state: st.session_state.selected_release = None

# --------------------------------------------------------------------------
# UIの定義
# --------------------------------------------------------------------------
st.title("🤖 プレスリリース改善AI アナライザー")
st.markdown("AIがプレスリリースをメディアフックの観点から分析し、具体的な改善点を提案します。")
st.sidebar.info("このアプリを動作させるには、別ターミナルでFastAPIサーバー(`uvicorn main:app --reload`)を起動しておく必要があります。")

st.divider()

# --- ステップ1: 記事のインポート ---
st.header("Step 1: 記事を選択")

# ★追加: データソース選択とキーワード検索
col_a, col_b = st.columns([1, 2])
with col_a:
    source_toggle = st.toggle("データベースから検索", value=False)
    data_source = "db" if source_toggle else "api"
    st.caption(f"現在のデータソース: {'データベース' if data_source == 'db' else 'PR TIMES API'}")
with col_b:
    search_keyword = st.text_input("キーワードで検索 (DB選択時のみ有効)", 
                                   disabled=not source_toggle)

if st.button("企業一覧を読み込む", key="load_companies"):
    with st.spinner("企業一覧を取得中..."):
        # ★修正: 選択されたデータソースとキーワードを渡す
        st.session_state.companies = get_companies(source=data_source, keyword=search_keyword)

if st.session_state.companies:
    selected_company = st.selectbox(
        "分析したい企業を選択してください",
        options=st.session_state.companies,
        format_func=lambda company: f"{company['company_name']} (ID: {company['company_id']})",
        index=None, placeholder="企業を選択...",
    )
    
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
                    # ★修正: 選択されたデータソースとキーワードを渡す
                    st.session_state.releases = get_releases(
                        st.session_state.selected_company_id, 
                        from_date_input, 
                        to_date_input,
                        source=data_source,
                        keyword=search_keyword
                    )
                    st.session_state.selected_release = None

if st.session_state.releases:
    st.session_state.selected_release = st.selectbox(
        "分析したい記事を選択してください",
        options=st.session_state.releases,
        format_func=lambda release: f"[{release['created_at'][:10]}] {release['title']}",
        index=None, placeholder="記事を選択...",
    )
elif st.session_state.selected_company_id:
    st.info("条件に合う記事が見つかりませんでした。期間を変えて再検索してください。")

# --- ★★★ 新機能: 記事プレビュー ★★★ ---
if st.session_state.selected_release:
    with st.expander("選択された記事のプレビュー", expanded=True):
        release = st.session_state.selected_release
        
        st.subheader(release.get('title', ''))
        st.caption(f"企業: {release.get('company_name', '')} | 公開日: {release.get('created_at', '')[:10]}")

        # サムネイル画像を表示
        if release.get('main_image'):
            st.image(release['main_image'], caption="サムネイル画像")
        
        st.markdown("---")
        
        # 本文をHTMLとして表示
        st.markdown("##### 本文プレビュー")
        if release.get('body'):
            # unsafe_allow_html=TrueでHTMLタグを解釈して表示
            st.markdown(release['body'], unsafe_allow_html=True)
        else:
            st.write("本文データがありません。")

st.divider()

# --- ステップ2: 分析の実行 ---
st.header("Step 2: プレスリリースの分析を実行")

title_default = ""
content_default = ""
image_url_default = ""

if st.session_state.selected_release:
    title_default = st.session_state.selected_release.get('title', '')
    content_default = st.session_state.selected_release.get('body', '')
    image_url_default = st.session_state.selected_release.get('main_image', '')

with st.form("press_release_form"):
    title = st.text_input("タイトル*", value=title_default)
    content_markdown = st.text_area("本文*", value=content_default, height=300)
    
    with st.expander("詳細オプション（画像URL・ペルソナなど）"):
        # 画像URL入力欄を追加
        image_url = st.text_input("画像URL", value=image_url_default)
        metadata_persona = st.text_input("ターゲットペルソナ", value="中小企業のカスタマーサポート部門長")

    submitted = st.form_submit_button("分析を実行 →", type="primary", use_container_width=True)

# --- 分析結果の表示 ---
if submitted:
    if not title.strip() or not content_markdown.strip():
        st.warning("タイトルと本文の両方を入力してください。")
    else:
        with st.spinner("AIが分析中です... しばらくお待ちください..."):
            
            # ★修正: ペイロードにrelease_idを追加
            release_id_to_send = None
            if st.session_state.selected_release:
                release_id_to_send = st.session_state.selected_release.get('release_id')
            
            payload = {
                "release_id": release_id_to_send, # ★追加
                "title": title,
                "content_html": content_markdown, # ★修正: content_markdownをcontent_htmlとして送信
                "top_image": {"url": image_url if image_url.strip() else None},
                "metadata": {"persona": metadata_persona if metadata_persona.strip() else "指定なし"}
            }
            try:
                response = requests.post(ANALYZE_URL, json=payload, timeout=180) # タイムアウトを延長
                response.raise_for_status()
                results = response.json()
                st.success("分析が完了しました！")
                
                
                st.divider()
                
                # ★★★★★ ここから追加 ★★★★★
                # --- 類似記事の表示 ---
                if "similar_releases" in results and results["similar_releases"]:
                    st.subheader("🤖 AIが推薦する類似記事")
                    st.info("分析した記事のタイトルに基づき、データベース内から類似した記事を推薦します。")
                    for release in results["similar_releases"]:
                        with st.container(border=True):
                            st.markdown(f"**{release['title']}**")
                            st.caption(f"リリースID: {release['release_id']}")
                    st.divider()
                # ★★★★★ ここまで追加 ★★★★★

                # (以降の結果表示部分は元のコードと同じ)
                # ... (結果表示のコードは変更ないため省略) ...

            except requests.exceptions.RequestException as e:
                st.error(f"APIサーバーへの接続に失敗しました。FastAPIサーバーが起動しているか確認してください。\n\n詳細: {e}")
            except Exception as e:
                st.error(f"分析中に予期せぬエラーが発生しました: {e}")