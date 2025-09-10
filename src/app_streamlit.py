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
# カテゴリー定義（main.pyと同期）
# --------------------------------------------------------------------------
CATEGORIES = {
    1: "商品サービス",
    2: "経営・人事",
    3: "企業動向・業績",
    4: "技術・研究開発",
    5: "マーケティング・リサーチ",
    6: "イベント・セミナー",
    7: "キャンペーン",
    8: "提携・M&A",
    9: "ファイナンス",
    10: "アワード・表彰",
    11: "CSR",
    12: "その他"
}

# ID→名前、名前→IDのマッピング用
CATEGORY_ID_TO_NAME = CATEGORIES
CATEGORY_NAME_TO_ID = {v: k for k, v in CATEGORIES.items()}

# --------------------------------------------------------------------------
# API通信を行う関数
# --------------------------------------------------------------------------
@st.cache_data
def get_companies():
    try:
        response = requests.get(COMPANIES_URL, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"企業一覧の取得に失敗しました。APIサーバーが起動しているか確認してください。\n\n詳細: {e}")
        return []

@st.cache_data
def get_releases(company_id, from_date, to_date):
    if not company_id:
        return []
    releases_url = f"{API_BASE_URL}/companies/{company_id}/releases"
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
# UI
# --------------------------------------------------------------------------
st.title("🤖 プレスリリース改善AI アナライザー")
st.markdown("AIがプレスリリースをメディアフックの観点から分析し、具体的な改善点を提案します。")
st.sidebar.info("このアプリを動作させるには、別ターミナルで FastAPI (`uvicorn src.main:app --reload --port 8000`) を起動しておく必要があります。")

st.divider()

# --- ステップ1: 記事のインポート ---
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
                    st.session_state.releases = get_releases(
                        st.session_state.selected_company_id,
                        from_date_input,
                        to_date_input
                    )
                    st.session_state.selected_release = None

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

# --- 記事プレビュー ---
if st.session_state.selected_release:
    with st.expander("選択された記事のプレビュー", expanded=True):
        release = st.session_state.selected_release
        st.subheader(release.get('title', ''))
        st.caption(f"企業: {release.get('company_name', '')} | 公開日: {release.get('created_at', '')[:10]}")

        if release.get('main_image'):
            st.image(release['main_image'], caption="サムネイル画像")

        st.markdown("---")
        st.markdown("##### 本文プレビュー")
        if release.get('body'):
            st.markdown(release['body'], unsafe_allow_html=True)
        else:
            st.write("本文データがありません。")

st.divider()

# --- ステップ2: 分析の実行 ---
st.header("Step 2: プレスリリースの分析を実行")

title_default = ""
content_default = ""
image_url_default = ""
default_category_id = 5

if st.session_state.selected_release:
    sel = st.session_state.selected_release
    title_default = sel.get('title', '')
    content_default = sel.get('body', '')
    image_url_default = sel.get('main_image', '')
    default_category_id = int(sel.get('main_category_id', 5))

results = None

with st.form("press_release_form"):
    title = st.text_input("タイトル*", value=title_default)
    content_markdown = st.text_area("本文*", value=content_default, height=300)

    with st.expander("詳細オプション（画像URL・ペルソナ・RAG設定）"):
        image_url = st.text_input("画像URL", value=image_url_default)
        metadata_persona = st.text_input("ターゲットペルソナ", value="中小企業のカスタマーサポート部門長")
        
        st.markdown("**RAG文脈設定**")
        st.caption("同一カテゴリの過去のプレスリリースを参考にして分析を行います")
        
        # カテゴリー選択（業種名で選択可能）
        default_category_name = CATEGORY_ID_TO_NAME.get(default_category_id, "マーケティング・リサーチ")
        
        selected_category_name = st.selectbox(
            "参考カテゴリ", 
            options=list(CATEGORY_NAME_TO_ID.keys()),
            index=list(CATEGORY_NAME_TO_ID.keys()).index(default_category_name),
            help="同一カテゴリの過去のプレスリリースを参考にします"
        )
        
        # 選択されたカテゴリ名からIDを取得
        selected_category_id = CATEGORY_NAME_TO_ID[selected_category_name]
        
        # カテゴリ情報を表示
        st.info(f"選択カテゴリ: {selected_category_name} (ID: {selected_category_id})")
        
        context_window_days = st.slider(
            "文脈取得期間（日）", 
            min_value=1, 
            max_value=180, 
            value=30,
            help="この期間内の過去のプレスリリースを参考にします"
        )
        
        context_top_k = st.slider(
            "RAG参照件数 (Top-K)", 
            min_value=1, 
            max_value=30, 
            value=12,
            help="いいね数が多い上位何件を参考にするか"
        )

    submitted = st.form_submit_button("分析を実行 →", type="primary", use_container_width=True)

if submitted:
    if not title.strip() or not content_markdown.strip():
        st.warning("タイトルと本文の両方を入力してください。")
    else:
        with st.spinner("AIが分析中です... しばらくお待ちください..."):
            # 修正されたpayload構造（FastAPI側と一致）
            payload = {
                "title": title,
                "content_markdown": content_markdown,
                "top_image": {"url": image_url if image_url.strip() else None},
                "metadata": {"persona": metadata_persona if metadata_persona.strip() else "指定なし"},
                # RAG設定（選択されたカテゴリIDを使用）
                "context_category_id": (
                    st.session_state.selected_release.get("main_category_id")
                    if st.session_state.selected_release else selected_category_id
                ),
                "context_window_days": int(context_window_days),
                "context_top_k": int(context_top_k)
            }
            
            try:
                response = requests.post(ANALYZE_URL, json=payload, timeout=180)
                response.raise_for_status()
                results = response.json()
                st.success("分析が完了しました！")
                
                # RAGの動作確認を表示
                rag_info_col1, rag_info_col2, rag_info_col3 = st.columns(3)
                with rag_info_col1:
                    st.metric("RAG使用", "有効" if results.get('rag_used', False) else "無効")
                with rag_info_col2:
                    st.metric("参考文脈件数", results.get('rag_context_count', 0))
                with rag_info_col3:
                    st.metric("処理時間", f"{results.get('processing_time_ms', 0)}ms")
                
            except requests.exceptions.RequestException as e:
                st.error(f"APIサーバーへの接続に失敗しました。FastAPIが起動中か確認してください。\n\n詳細: {e}")
                st.stop()

# --- 分析結果の表示 ---
if results:
    st.divider()

    # ====== 総合評価 ======
    oa = results.get("overall_assessment", {}) or {}
    cols = st.columns(3)
    with cols[0]:
        total_score = oa.get('total_score', 0)
        if isinstance(total_score, (int, float)):
            st.metric("総合スコア", f"{total_score:.1f} / 5")
        else:
            st.metric("総合スコア", "N/A")
            
    with cols[1]:
        st.markdown("**強み**")
        strengths = oa.get("strengths", [])
        if strengths:
            for s in strengths:
                st.write("・", s)
        else:
            st.write("・ 評価データなし")
            
    with cols[2]:
        st.markdown("**弱み**")
        weaknesses = oa.get("weaknesses", [])
        if weaknesses:
            for w in weaknesses:
                st.write("・", w)
        else:
            st.write("・ 評価データなし")

    st.markdown("**推奨事項（上位）**")
    recommendations = oa.get("top_recommendations", [])
    if recommendations:
        for r in recommendations:
            st.write("・", r)
    else:
        st.write("・ 推奨事項なし")

    if "estimated_impact" in oa:
        st.caption(f"推定インパクト: {oa['estimated_impact']}")

    st.divider()

 # ====== メディアフック評価 ======
    st.subheader("メディアフック評価")
    
    # 全項目の定義
    EXPECTED_HOOKS = [
        {"hook_type": "trending_seasonal", "hook_name_ja": "トレンド・季節性"},
        {"hook_type": "unexpectedness", "hook_name_ja": "意外性"},
        {"hook_type": "paradox_conflict", "hook_name_ja": "パラドックス・対立構造"},
        {"hook_type": "regional", "hook_name_ja": "地域性"},
        {"hook_type": "topicality", "hook_name_ja": "話題性"},
        {"hook_type": "social_public", "hook_name_ja": "社会性・公共性"},
        {"hook_type": "novelty_uniqueness", "hook_name_ja": "新規性・独自性"},
        {"hook_type": "superlative_rarity", "hook_name_ja": "最上級・希少性"},
        {"hook_type": "visual_impact", "hook_name_ja": "ビジュアルインパクト"},
    ]
    
    media_hooks = results.get("media_hook_evaluations", [])
    hooks_by_type = {hook.get("hook_type"): hook for hook in media_hooks}
    
    # 全項目を順序通りに表示
    for expected_hook in EXPECTED_HOOKS:
        hook_type = expected_hook["hook_type"]
        hook_name = expected_hook["hook_name_ja"]
        
        if hook_type in hooks_by_type:
            item = hooks_by_type[hook_type]
            score = item.get("score", 0)
        else:
            # データが不足している場合のフォールバック
            item = {
                "hook_type": hook_type,
                "hook_name_ja": hook_name,
                "score": 0,
                "description": "データが取得できませんでした",
                "improve_examples": [],
                "current_elements": []
            }
            score = 0
        
        with st.expander(f"{hook_name}（{score}/5）", expanded=False):
            # スコアバー表示
            if isinstance(score, (int, float)) and score > 0:
                st.progress(min(max(score / 5.0, 0), 1))
            else:
                st.progress(0)
                
            # 説明
            desc = item.get("description")
            if desc:
                st.write(desc)
                
            # 現状の要素
            current = item.get("current_elements") or []
            if current:
                st.markdown("**現状で満たしている要素**")
                for c in current:
                    st.write("・", c)
            else:
                st.markdown("**現状で満たしている要素**")
                st.write("・ 特に該当なし")
                
            # 改善アイデア
            tips = item.get("improve_examples") or []
            if tips:
                st.markdown("**改善アイデア**")
                for t in tips:
                    st.write("・", t)
            else:
                st.markdown("**改善アイデア**")
                st.write("・ 改善案を生成できませんでした")
    
    # 評価完了度の表示
    evaluated_count = len([h for h in EXPECTED_HOOKS if h["hook_type"] in hooks_by_type])
    st.caption(f"評価完了: {evaluated_count}/{len(EXPECTED_HOOKS)} 項目")
    # ====== 段落改善提案 ======
    paragraph_improvements = results.get("paragraph_improvements", [])
    if paragraph_improvements:
        st.divider()
        st.subheader("段落改善提案")
        for i, improvement in enumerate(paragraph_improvements, 1):
            with st.expander(f"改善提案 {i}: {improvement.get('where', '場所不明')}", expanded=False):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**改善前**")
                    st.code(improvement.get('before', ''), language=None)
                with col2:
                    st.markdown("**改善後**")
                    st.code(improvement.get('after', ''), language=None)

    # ====== RAG文脈情報 ======
    if results.get("rag_used"):
        st.divider()
        st.subheader("🔗 RAG分析情報")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            # カテゴリIDと名前を表示
            category_id = payload.get('context_category_id', 'N/A')
            category_name = CATEGORY_ID_TO_NAME.get(category_id, '不明') if isinstance(category_id, int) else 'N/A'
            st.metric("参考カテゴリ", f"{category_name} (ID: {category_id})")
        with col2:
            st.metric("取得期間", f"{payload.get('context_window_days', 'N/A')}日間")
        with col3:
            st.metric("AIモデル", results.get('ai_model_used', 'N/A'))
            
        st.caption("同一カテゴリの過去のプレスリリースを参考にして分析を行いました。")
        
        # 詳細なRAGデバッグ情報
        with st.expander("RAG詳細情報（デバッグ用）", expanded=False):
            st.json({
                "rag_used": results.get('rag_used'),
                "rag_context_count": results.get('rag_context_count'),
                "ai_model_used": results.get('ai_model_used'),
                "processing_time_ms": results.get('processing_time_ms'),
                "analyzed_at": results.get('analyzed_at'),
                "request_id": results.get('request_id'),
                "selected_category": {
                    "id": category_id,
                    "name": category_name
                }
            })
    else:
        st.divider()
        st.warning("RAG機能が使用されませんでした。カテゴリIDや期間設定を確認してください。")

# サイドバーに追加情報
with st.sidebar:
    st.markdown("### カテゴリ一覧")
    st.markdown("**利用可能なカテゴリ:**")
    for cat_id, cat_name in CATEGORIES.items():
        st.markdown(f"{cat_id}. {cat_name}")
    
    if results:
        st.markdown("### 最新分析結果")
        st.caption(f"リクエストID: {results.get('request_id', 'N/A')}")
        st.caption(f"分析時刻: {results.get('analyzed_at', 'N/A')}")
        
        # 使用されたカテゴリ情報も表示
        if payload:
            used_category_id = payload.get('context_category_id')
            used_category_name = CATEGORY_ID_TO_NAME.get(used_category_id, '不明')
            st.caption(f"使用カテゴリ: {used_category_name}")