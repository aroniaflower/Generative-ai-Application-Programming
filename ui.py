import streamlit as st


def setup_ui():
    """
    TeamPlay 공통 UI 설정
    """

    st.set_page_config(
        page_title="TeamProject",
        page_icon="🚀",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.markdown("""
    <style>

    /* 전체 레이아웃 */
    .main .block-container{
        padding-top:1rem;
        padding-bottom:2rem;
        max-width:1400px;
    }

    /* 메인 타이틀 */
    .main-title{
        text-align:center;
        font-size:42px;
        font-weight:700;
        color:#2563EB;
        margin-bottom:5px;
    }

    /* 부제목 */
    .sub-title{
        text-align:center;
        color:#6B7280;
        font-size:16px;
        margin-bottom:30px;
    }

    /* 카드 스타일 */
    .custom-card{
        background-color:white;
        padding:20px;
        border-radius:15px;
        border:1px solid #E5E7EB;
        box-shadow:0 2px 8px rgba(0,0,0,0.05);
    }

    /* 사이드바 */
    [data-testid="stSidebar"]{
        background-color:#F8FAFC;
    }

    /* 버튼 */
    .stButton > button{
        width:100%;
        height:45px;
        border-radius:10px;
        font-weight:600;
    }

    /* 데이터프레임 */
    [data-testid="stDataFrame"]{
        border-radius:12px;
    }

    /* 입력창 */
    .stTextInput input{
        border-radius:10px;
    }

    .stTextArea textarea{
        border-radius:10px;
    }

    </style>
    """, unsafe_allow_html=True)


def show_header():
    """
    상단 공통 헤더
    """

    st.markdown("""
    <div class="main-title">
        🚀 Team Project
    </div>

    <div class="sub-title">
        팀 프로젝트 협업 · 일정 관리 · 업무 분배 플랫폼
    </div>
    """, unsafe_allow_html=True)


def show_sidebar_logo():
    """
    사이드바 로고
    """

    st.sidebar.markdown("""
    # 🚀 Team Project

    ### 프로젝트 대시보드
    ---
    """)
