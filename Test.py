import streamlit as st
import pandas as pd
from datetime import datetime

# 1. 페이지 기본 설정
st.set_page_config(page_title="대학생 팀플 매니저", page_icon="🚀", layout="wide")

# 2. 초기 데이터 세팅
if "roles" not in st.session_state:
    st.session_state.roles = pd.DataFrame(columns=["팀원 이름", "담당 역할"])

# [수정됨] 여러 주제(리스트) 대신 단일 프로젝트 주제와 마감일로 변경
if "project_topic" not in st.session_state:
    st.session_state.project_topic = None
if "project_deadline" not in st.session_state:
    st.session_state.project_deadline = None

if "task_data" not in st.session_state:
    # 단일 주제이므로 '주제' 컬럼을 뺐습니다.
    st.session_state.task_data = pd.DataFrame(columns=["작업명", "담당자", "진행률(%)", "마감일", "완료 근거"])

if "notices" not in st.session_state:
    st.session_state.notices = []

if "meetings" not in st.session_state:
    st.session_state.meetings = []

if "meeting_chats" not in st.session_state:
    st.session_state.meeting_chats = {}

if "evaluations" not in st.session_state:
    st.session_state.evaluations = pd.DataFrame(columns=["대상자", "점수", "코멘트"])

def main():
    st.sidebar.title("📌 메뉴")
    menu = st.sidebar.radio(
        "이동할 페이지를 선택하세요:",
        ["통합 대시보드", "팀원 및 역할 관리", "프로젝트 및 작업 관리", "공지 및 회의록", "기여도 평가"]
    )

    if menu == "통합 대시보드":
        render_dashboard()
    elif menu == "팀원 및 역할 관리":
        render_role_management()
    elif menu == "프로젝트 및 작업 관리":
        render_task_management()
    elif menu == "공지 및 회의록":
        render_notice_meeting()
    elif menu == "기여도 평가":
        render_evaluation()

# 팀원 및 역할 관리
def render_role_management():
    st.title("👥 팀원 및 역할 관리")
    with st.form("add_role_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            new_member = st.text_input("팀원 이름")
        with col2:
            new_role = st.text_input("담당 역할")
        if st.form_submit_button("➕ 역할 등록하기") and new_member:
            new_row = pd.DataFrame([{"팀원 이름": new_member, "담당 역할": new_role}])
            st.session_state.roles = pd.concat([st.session_state.roles, new_row], ignore_index=True)
            st.success(f"'{new_member}' 팀원의 역할이 등록되었습니다!")
            st.rerun()

    st.divider()
    st.subheader("현재 등록된 역할 목록")
    if not st.session_state.roles.empty:
        edited_roles = st.data_editor(st.session_state.roles, num_rows="dynamic", use_container_width=True, hide_index=True)
        if st.button("💾 역할 목록 저장"):
            st.session_state.roles = edited_roles
            st.success("수정사항이 반영되었습니다.")

# 통합 대시보드
def render_dashboard():
    st.title("📊 팀 프로젝트 대시보드")
    
    # [수정됨] 대시보드 상단에 단일 프로젝트 주제를 강조
    if st.session_state.project_topic:
        st.markdown(f"### 🎯 현재 프로젝트: **{st.session_state.project_topic}**")
    else:
        st.markdown("### 🎯 현재 프로젝트: `아직 설정되지 않았습니다.`")

    st.divider()
    
    # [수정됨] 남은 일수(D-Day) 계산 로직
    d_day_text = "미정"
    if st.session_state.project_deadline:
        today = datetime.now().date()
        diff = (st.session_state.project_deadline - today).days
        if diff > 0:
            d_day_text = f"D-{diff}"
        elif diff == 0:
            d_day_text = "D-Day"
        else:
            d_day_text = f"D+{abs(diff)}"

    total_tasks = len(st.session_state.task_data)
    if total_tasks > 0:
        st.session_state.task_data["진행률(%)"] = pd.to_numeric(st.session_state.task_data["진행률(%)"], errors='coerce').fillna(0)
        avg_progress = int(st.session_state.task_data["진행률(%)"].mean())
    else:
        avg_progress = 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("팀 전체 진행률 (평균)", f"{avg_progress}%")
    col2.metric("등록된 총 작업 수", f"{total_tasks}개")
    col3.metric("최종 마감일까지", d_day_text)
    col4.metric("등록된 평가 수", f"{len(st.session_state.evaluations)}건")
    
    st.divider()
    st.subheader("🔥 내 작업 및 마감 임박 작업")
    if total_tasks == 0:
        st.info("아직 등록된 작업이 없습니다.")
    else:
        edited_df = st.data_editor(
            st.session_state.task_data, num_rows="dynamic", use_container_width=True, hide_index=True,
            column_config={"진행률(%)": st.column_config.NumberColumn("진행률(%)", min_value=0, max_value=100, step=10, format="%d%%")}
        )
        if st.button("💾 변경 사항 저장하기"):
            st.session_state.task_data = edited_df
            st.rerun()

# 프로젝트 및 작업 관리
def render_task_management():
    st.title("📝 프로젝트 및 작업 관리")
    
    # [수정됨] 단일 주제 및 마감일 설정 (한 번 정하면 고정됨)
    st.subheader("1️⃣ 프로젝트 주제 및 최종 마감일 설정")
    if st.session_state.project_topic is None:
        with st.form("set_project_form"):
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                new_topic = st.text_input("프로젝트 메인 주제")
            with col_t2:
                new_deadline = st.date_input("최종 마감일")
            
            if st.form_submit_button("➕ 주제 및 마감일 확정하기") and new_topic:
                st.session_state.project_topic = new_topic
                st.session_state.project_deadline = new_deadline
                st.rerun()
    else:
        st.success(f"🎯 **현재 프로젝트 주제:** {st.session_state.project_topic}")
        st.info(f"⏰ **최종 마감일:** {st.session_state.project_deadline} (💡 주제는 하나만 지정할 수 있어 다른 주제를 추가할 수 없습니다.)")
    
    st.divider()
    
    st.subheader("2️⃣ 세부 작업 배정")
    if st.session_state.project_topic:
        member_list = st.session_state.roles["팀원 이름"].tolist() if not st.session_state.roles.empty else ["등록된 팀원 없음"]
        with st.form("add_task_form", clear_on_submit=True):
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                new_task_name = st.text_input("세부 작업명")
            with col2:
                new_assignee = st.selectbox("담당자", member_list)
            with col3:
                task_deadline = st.date_input("작업 마감일")
            
            if st.form_submit_button("➕ 작업 배정하기") and new_task_name:
                new_row = pd.DataFrame([{"작업명": new_task_name, "담당자": new_assignee, "진행률(%)": 0, "마감일": task_deadline.strftime("%Y-%m-%d"), "완료 근거": ""}])
                st.session_state.task_data = pd.concat([st.session_state.task_data, new_row], ignore_index=True)
                st.rerun()
    else:
        st.warning("위에서 프로젝트 주제와 최종 마감일을 먼저 확정해 주세요.")

    st.divider()
    if len(st.session_state.task_data) > 0:
        edited_df = st.data_editor(st.session_state.task_data, num_rows="dynamic", use_container_width=True, hide_index=True)
        if st.button("💾 작업 목록 저장"):
            st.session_state.task_data = edited_df
            st.rerun()

# 공지 및 회의록
def render_notice_meeting():
    st.title("📢 공지 및 회의록")
    tab1, tab2 = st.tabs(["📌 공지사항", "📋 회의록 및 논의"])
    
    with tab1:
        st.subheader("새 공지 올리기")
        with st.form("notice_form", clear_on_submit=True):
            notice_text = st.text_area("팀원들에게 알릴 내용을 작성하세요.")
            if st.form_submit_button("공지 등록") and notice_text:
                st.session_state.notices.insert(0, {"작성자": "나", "내용": notice_text, "시간": datetime.now().strftime("%Y-%m-%d %H:%M")})
                st.rerun()
        
        st.divider()
        if not st.session_state.notices:
            st.info("등록된 공지사항이 없습니다.")
        else:
            for notice in st.session_state.notices:
                st.info(f"**[{notice['시간']}] {notice['작성자']}**\n\n{notice['내용']}")

    with tab2:
        st.subheader("회의록 등록하기")
        with st.form("meeting_form", clear_on_submit=True):
            m_title = st.text_input("회의 주제")
            m_attendees = st.text_input("참석자")
            m_content = st.text_area("회의 주요 논의 및 결정 사항")
            if st.form_submit_button("회의록 저장") and m_title:
                new_id = len(st.session_state.meetings) + 1
                st.session_state.meetings.insert(0, {"id": new_id, "제목": m_title, "참석자": m_attendees, "내용": m_content})
                st.session_state.meeting_chats[new_id] = []
                st.rerun()
                
        st.divider()
        if not st.session_state.meetings:
            st.info("등록된 회의록이 없습니다.")
        else:
            for meeting in st.session_state.meetings:
                with st.expander(f"📁 {meeting['제목']} (참석자: {meeting['참석자']})"):
                    st.markdown(f"**회의 내용:**\n\n{meeting['내용']}")
                    st.divider()
                    
                    st.markdown("💬 **이 회의에 대한 대화 나누기**")
                    m_id = meeting["id"]
                    
                    for chat in st.session_state.meeting_chats.get(m_id, []):
                        st.chat_message("user" if chat["user"] == "나" else "assistant").write(f"**{chat['user']}**: {chat['msg']}")
                    
                    chat_input_key = f"chat_input_{m_id}"
                    new_msg = st.chat_input("메시지를 입력하세요...", key=chat_input_key)
                    if new_msg:
                        st.session_state.meeting_chats[m_id].append({"user": "나", "msg": new_msg})
                        st.rerun()

# 기여도 평가
def render_evaluation():
    st.title("🤝 기여도 평가 (익명)")
    st.info("이 평가는 익명으로 진행되며, 팀원 간의 피드백 및 참고용 데이터로만 활용됩니다.")
    
    if st.session_state.project_topic is None or st.session_state.roles.empty:
        st.warning("⚠️ '프로젝트 주제'와 '팀원'이 모두 등록되어야 평가를 진행할 수 있습니다.")
        return

    st.subheader("✍️ 팀원 평가하기")
    with st.form("evaluation_form", clear_on_submit=True):
        # 단일 주제이므로 주제 선택창 제거
        eval_target = st.selectbox("평가할 대상을 선택하세요", st.session_state.roles["팀원 이름"].tolist())
        eval_score = st.slider(f"{eval_target}님의 기여도 점수 (5점 만점)", min_value=1, max_value=5, value=5)
        eval_comment = st.text_area("익명 코멘트를 남겨주세요 (선택사항)")
        
        submit_eval = st.form_submit_button("보내기 (익명)")
        if submit_eval:
            new_eval = pd.DataFrame([{
                "대상자": eval_target, "점수": eval_score, "코멘트": eval_comment
            }])
            st.session_state.evaluations = pd.concat([st.session_state.evaluations, new_eval], ignore_index=True)
            st.success("평가가 제출되었습니다!")
            st.rerun()

    st.divider()
    st.subheader("📊 팀원별 평균 기여도")
    if st.session_state.evaluations.empty:
        st.caption("아직 제출된 평가가 없습니다.")
    else:
        avg_scores = st.session_state.evaluations.groupby("대상자")["점수"].mean().round(1).reset_index()
        avg_scores.columns = ["팀원 이름", "평균 점수 (5점 만점)"]
        st.dataframe(avg_scores, hide_index=True, use_container_width=True)

        st.divider()
        st.subheader("💬 익명 피드백 모아보기")
        for idx, row in st.session_state.evaluations.iterrows():
            if row["코멘트"].strip() != "":
                st.markdown(f"**{row['대상자']} 팀원에게:**")
                st.caption(f"⭐ {row['점수']}점 - {row['코멘트']}")
                st.write("---")

if __name__ == "__main__":
    main()
