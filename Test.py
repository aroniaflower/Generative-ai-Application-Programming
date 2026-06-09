import streamlit as st
import pandas as pd
import datetime

# --- 초기 데이터 세팅 (Session State) ---
if 'topic' not in st.session_state:
    st.session_state.topic = ""
if 'final_deadline' not in st.session_state:
    st.session_state.final_deadline = None

if 'team_members' not in st.session_state:
    st.session_state.team_members = pd.DataFrame(columns=["이름", "역할"])

if 'tasks' not in st.session_state:
    st.session_state.tasks = pd.DataFrame(columns=["작업명", "담당자", "진행률(%)", "마감일", "완료 근거"])

if 'notices' not in st.session_state:
    st.session_state.notices = []
if 'minutes' not in st.session_state:
    st.session_state.minutes = []
if 'evaluations' not in st.session_state:
    st.session_state.evaluations = []

# --- 사이드바 메뉴 ---
st.sidebar.title("📌 메뉴")
page = st.sidebar.radio(
    "이동할 페이지를 선택하세요:",
    ["통합 대시보드", "팀원 및 역할 관리", "프로젝트 및 작업 관리", "공지 및 회의록", "기여도 평가"]
)

# --- 1. 통합 대시보드 ---
if page == "통합 대시보드":
    st.title("📊 통합 대시보드")
    
    if st.session_state.topic:
        st.subheader(f"🎯 현재 프로젝트 주제: {st.session_state.topic}")
        
        # 최상단: D-Day 및 평균 진행률 (NFR-001 대응)
        col1, col2 = st.columns(2)
        with col1:
            if st.session_state.final_deadline:
                today = datetime.date.today()
                d_day = (st.session_state.final_deadline - today).days
                if d_day > 0:
                    st.info(f"⏳ 최종 마감일까지 **D-{d_day}** 남았습니다!")
                elif d_day == 0:
                    st.warning("🚨 오늘이 최종 마감일입니다!")
                else:
                    st.error(f"💥 마감일이 {abs(d_day)}일 지났습니다.")
        
        with col2:
            if not st.session_state.tasks.empty:
                avg_progress = st.session_state.tasks["진행률(%)"].mean()
            else:
                avg_progress = 0
            st.metric(label="팀 전체 평균 진행률", value=f"{avg_progress:.1f}%")

        st.markdown("---")
        
        # 복구됨: 과부하 경고 로직 (FR-005, FR-006 대응)
        st.markdown("### 🚨 팀원 업무 부하 상태")
        if not st.session_state.tasks.empty:
            incomplete_tasks = st.session_state.tasks[st.session_state.tasks["진행률(%)"] < 100]
            if not incomplete_tasks.empty:
                task_counts = incomplete_tasks["담당자"].value_counts()
                overloaded_members = task_counts[task_counts >= 3].index.tolist() # 3개 이상 미완료 시 과부하로 판정
                
                if overloaded_members:
                    for member in overloaded_members:
                        st.warning(f"⚠️ **{member}**님에게 현재 진행 중인 작업이 몰려있습니다! (미완료 작업: {task_counts[member]}개)")
                else:
                    st.success("✅ 현재 업무가 팀원들에게 균형 있게 분배되어 있습니다.")
            else:
                st.success("🎉 모든 작업이 완료되었습니다!")
        else:
            st.write("배정된 작업이 없습니다.")

        st.markdown("---")
        
        # 복구됨: 최근 공지 및 회의록 요약 (FR-014 대응)
        col_notice, col_minute = st.columns(2)
        with col_notice:
            st.markdown("#### 📢 최근 공지")
            if st.session_state.notices:
                latest_notice = st.session_state.notices[-1]
                st.info(f"**[{latest_notice['시간']}]**\n\n{latest_notice['내용']}")
            else:
                st.write("등록된 공지가 없습니다.")
                
        with col_minute:
            st.markdown("#### 📝 최근 회의록")
            if st.session_state.minutes:
                latest_minute = st.session_state.minutes[-1]
                content_preview = latest_minute['내용'][:20] + "..." if len(latest_minute['내용']) > 20 else latest_minute['내용']
                st.success(f"**[{latest_minute['시간']}]**\n\n{content_preview}")
            else:
                st.write("등록된 회의록이 없습니다.")

        st.markdown("---")

        # 작업 현황 표
        st.markdown("### 📋 현재 작업 현황")
        st.dataframe(st.session_state.tasks, use_container_width=True)
        
    else:
        st.warning("프로젝트 주제가 아직 설정되지 않았습니다. '프로젝트 및 작업 관리' 탭에서 주제를 먼저 설정해주세요.")

# --- 2. 팀원 및 역할 관리 ---
elif page == "팀원 및 역할 관리":
    st.title("👥 팀원 및 역할 관리")
    st.markdown("팀원의 이름과 주요 역할을 등록하고 관리하세요.")
    
    edited_members = st.data_editor(
        st.session_state.team_members,
        num_rows="dynamic",
        use_container_width=True
    )
    
    if st.button("💾 팀원 목록 저장"):
        st.session_state.team_members = edited_members
        st.success("팀원 목록이 저장되었습니다!")

# --- 3. 프로젝트 및 작업 관리 ---
elif page == "프로젝트 및 작업 관리":
    st.title("📂 프로젝트 및 작업 관리")
    
    # 단일 주제 제한 유지
    if not st.session_state.topic:
        st.markdown("### 1️⃣ 프로젝트 주제 및 최종 마감일 설정")
        new_topic = st.text_input("프로젝트의 큰 주제를 입력하세요:")
        final_date = st.date_input("최종 마감일을 선택하세요:")
        
        if st.button("주제 확정하기"):
            if new_topic:
                st.session_state.topic = new_topic
                st.session_state.final_deadline = final_date
                st.rerun()
            else:
                st.warning("주제를 입력해주세요!")
    else:
        st.info(f"⏰ 최종 마감일: {st.session_state.final_deadline} (💡 주제는 하나만 지정할 수 있어 다른 주제를 추가할 수 없습니다.)")
        
        st.markdown("### 2️⃣ 세부 작업 배정")
        
        # 달력 선택 폼 유지
        with st.form("add_task_form", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                task_name = st.text_input("세부 작업명")
            with col2:
                if not st.session_state.team_members.empty:
                    assignee_list = st.session_state.team_members["이름"].tolist()
                    assignee = st.selectbox("담당자", assignee_list)
                else:
                    assignee = st.text_input("담당자 (팀원을 먼저 등록하면 선택 가능합니다)")
            with col3:
                task_deadline = st.date_input("작업 마감일")
                
            submit_button = st.form_submit_button("➕ 작업 배정하기")
            
            if submit_button:
                if task_name and assignee:
                    new_task = pd.DataFrame({
                        "작업명": [task_name],
                        "담당자": [assignee],
                        "진행률(%)": [0], 
                        "마감일": [task_deadline],
                        "완료 근거": [""]
                    })
                    st.session_state.tasks = pd.concat([st.session_state.tasks, new_task], ignore_index=True)
                    st.success(f"'{task_name}' 작업이 배정되었습니다!")
                    st.rerun()
                else:
                    st.warning("작업명과 담당자를 모두 입력해주세요.")
        
        # 0~100 숫자 제한 유지
        st.markdown("#### 📋 세부 작업 목록 및 진행률 업데이트")
        edited_tasks = st.data_editor(
            st.session_state.tasks,
            num_rows="dynamic",
            column_config={
                "진행률(%)": st.column_config.NumberColumn(
                    "진행률(%)",
                    help="0에서 100 사이의 숫자를 입력하세요.",
                    min_value=0,
                    max_value=100,
                    step=1
                ),
                "마감일": st.column_config.DateColumn("마감일")
            },
            use_container_width=True
        )
        
        if st.button("💾 작업 목록 저장"):
            st.session_state.tasks = edited_tasks
            st.success("작업 목록과 진행률이 성공적으로 업데이트되었습니다!")

# --- 4. 공지 및 회의록 ---
elif page == "공지 및 회의록":
    st.title("📢 공지 및 회의록")
    tab1, tab2 = st.tabs(["📌 공지사항", "📝 회의록"])
    
    with tab1:
        new_notice = st.text_area("새로운 공지사항을 입력하세요:")
        if st.button("공지 올리기"):
            if new_notice:
                st.session_state.notices.append({"시간": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "내용": new_notice})
                st.success("공지가 등록되었습니다.")
                st.rerun()
                
        st.markdown("---")
        for notice in reversed(st.session_state.notices):
            st.info(f"**[{notice['시간']}]**\n\n{notice['내용']}")
            
    with tab2:
        new_minute = st.text_area("회의 내용을 기록하세요:")
        if st.button("회의록 저장"):
            if new_minute:
                st.session_state.minutes.append({"시간": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "내용": new_minute, "댓글": []})
                st.success("회의록이 저장되었습니다.")
                st.rerun()
                
        st.markdown("---")
        for i, minute in enumerate(reversed(st.session_state.minutes)):
            with st.expander(f"🗓️ 회의록: {minute['시간']}"):
                st.write(minute['내용'])
                st.markdown("#### 💬 관련 대화")
                for comment in minute['댓글']:
                    st.write(f"- {comment}")
                
                comment_input = st.text_input(f"댓글 입력", key=f"comment_{i}")
                if st.button("댓글 달기", key=f"btn_{i}"):
                    if comment_input:
                        actual_index = len(st.session_state.minutes) - 1 - i
                        st.session_state.minutes[actual_index]['댓글'].append(comment_input)
                        st.rerun()

# --- 5. 기여도 평가 ---
elif page == "기여도 평가":
    st.title("🤝 익명 기여도 평가")
    st.markdown("프로젝트 종료 후, 익명으로 서로의 기여도를 평가합니다.")
    
    if st.session_state.topic and not st.session_state.team_members.empty:
        col1, col2 = st.columns(2)
        with col1:
            eval_target = st.selectbox("평가할 팀원 선택", st.session_state.team_members["이름"].tolist())
        with col2:
            score = st.slider("기여도 점수 (1점~5점)", min_value=1, max_value=5, value=3)
            
        eval_comment = st.text_area("익명 코멘트 남기기 (선택사항)")
        
        if st.button("평가 제출하기 (익명)"):
            st.session_state.evaluations.append({
                "대상자": eval_target,
                "점수": score,
                "코멘트": eval_comment
            })
            st.success(f"{eval_target}님에 대한 평가가 익명으로 안전하게 제출되었습니다!")
            
        st.markdown("---")
        st.markdown("### 📊 현재까지의 평균 평가 점수")
        
        if st.session_state.evaluations:
            eval_df = pd.DataFrame(st.session_state.evaluations)
            avg_scores = eval_df.groupby("대상자")["점수"].mean().reset_index()
            avg_scores.rename(columns={"점수": "평균 점수"}, inplace=True)
            st.dataframe(avg_scores, use_container_width=True)
        else:
            st.info("아직 제출된 평가가 없습니다.")
    else:
        st.warning("먼저 '팀원 및 역할 관리'에서 팀원을 등록하고, '프로젝트 관리'에서 주제를 설정해주세요.")
