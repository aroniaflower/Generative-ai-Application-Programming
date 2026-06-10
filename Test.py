import streamlit as st
import pandas as pd
import datetime
import json
from streamlit_gsheets import GSheetsConnection

# ---------------------------------------------------------------
# [필수 설정] .streamlit/secrets.toml 파일에 아래 내용이 있어야 합니다:
#
# [connections.gsheets]
# spreadsheet = "https://docs.google.com/spreadsheets/d/1inkNacK53youxmmJWqu6eCYKliwRnYqdBh4EEfjAn3g"
# type = "service_account"
# project_id = "YOUR_PROJECT_ID"
# private_key_id = "YOUR_KEY_ID"
# private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
# client_email = "YOUR_SERVICE_ACCOUNT_EMAIL"
# client_id = "YOUR_CLIENT_ID"
# auth_uri = "https://accounts.google.com/o/oauth2/auth"
# token_uri = "https://oauth2.googleapis.com/token"
#
# 또한 구글 시트에 서비스 계정 이메일을 편집자로 공유해야 합니다.
# 구글 시트에 다음 탭(워크시트)이 미리 만들어져 있어야 합니다:
#   프로젝트개요 / 팀원목록 / 작업목록 / 공지사항 / 회의록 / 투표후보 / 투표결과 / 기여도평가
# ---------------------------------------------------------------

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1inkNacK53youxmmJWqu6eCYKliwRnYqdBh4EEfjAn3g"


# --- [수정 1] 커넥션을 캐싱하여 매 rerun마다 재연결 방지 ---
@st.cache_resource
def get_connection():
    return st.connection("gsheets", type=GSheetsConnection)

conn = get_connection()


# --- 구글 시트 데이터 안전하게 로드하기 위한 헬퍼 함수 ---
def load_worksheet(worksheet_name, default_columns):
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0)
        df = df.dropna(how='all')
        # 읽어온 컬럼이 비어 있으면 기본 컬럼으로 반환
        if df.empty:
            return pd.DataFrame(columns=default_columns)
        return df
    except Exception as e:
        # 시트가 없거나 읽기 실패 시 빈 DataFrame 반환
        return pd.DataFrame(columns=default_columns)


# --- [수정 2] 빈 DataFrame을 안전하게 conn.update()에 넘기는 헬퍼 함수 ---
def safe_update(worksheet_name, data, default_columns):
    """data가 빈 리스트/DataFrame이어도 컬럼을 유지하며 업데이트"""
    if isinstance(data, list):
        if len(data) == 0:
            df = pd.DataFrame(columns=default_columns)
        else:
            df = pd.DataFrame(data)
    else:
        df = data
    conn.update(worksheet=worksheet_name, data=df)


# --- 초기 데이터 세팅 및 구글 시트 데이터 불러오기 ---

# 1. 프로젝트 주제 및 마감일 로드
if 'topic' not in st.session_state or 'final_deadline' not in st.session_state:
    meta_df = load_worksheet("프로젝트개요", ["주제", "최종마감일"])
    if not meta_df.empty and "주제" in meta_df.columns:
        st.session_state.topic = str(meta_df.iloc[0]["주제"]) if pd.notna(meta_df.iloc[0]["주제"]) else ""
        deadline_str = meta_df.iloc[0]["최종마감일"]
        if pd.notna(deadline_str) and str(deadline_str).strip() != "":
            try:
                st.session_state.final_deadline = datetime.datetime.strptime(
                    str(deadline_str).split()[0], "%Y-%m-%d"
                ).date()
            except Exception:
                st.session_state.final_deadline = None
        else:
            st.session_state.final_deadline = None
    else:
        st.session_state.topic = ""
        st.session_state.final_deadline = None

# 2. 팀원 명단 로드
if 'team_members' not in st.session_state:
    st.session_state.team_members = load_worksheet("팀원목록", ["이름", "역할", "주간 가용시간(시간)"])

# 3. 세부 작업 목록 로드
if 'tasks' not in st.session_state:
    tasks_df = load_worksheet("작업목록", ["작업명", "담당자", "상태", "예상 소요시간(시간)", "마감일", "완료 근거"])
    if "마감일" in tasks_df.columns:
        # [수정 3] 날짜 변환 시 NaT → None 처리
        tasks_df["마감일"] = pd.to_datetime(tasks_df["마감일"], errors='coerce').dt.date
    st.session_state.tasks = tasks_df

# 4. 공지사항 로드
if 'notices' not in st.session_state:
    notices_df = load_worksheet("공지사항", ["시간", "내용"])
    st.session_state.notices = notices_df.to_dict(orient="records") if not notices_df.empty else []

# 5. 회의록 로드
if 'minutes' not in st.session_state:
    minutes_df = load_worksheet("회의록", ["시간", "내용", "댓글"])
    minutes_list = []
    for _, row in minutes_df.iterrows():
        try:
            comments = json.loads(row["댓글"]) if pd.notna(row.get("댓글")) and str(row["댓글"]).strip() != "" else []
        except Exception:
            comments = []
        minutes_list.append({
            "시간": str(row.get("시간", "")),
            "내용": str(row.get("내용", "")),
            "댓글": comments
        })
    st.session_state.minutes = minutes_list

# 6. 일정 투표 후보 로드
if 'candidates' not in st.session_state:
    candidates_df = load_worksheet("투표후보", ["후보 일정"])
    # [수정 4] 컬럼 존재 여부 확인 후 tolist()
    if "후보 일정" in candidates_df.columns:
        st.session_state.candidates = candidates_df["후보 일정"].dropna().tolist()
    else:
        st.session_state.candidates = []

# 7. 투표 결과 로드
if 'votes' not in st.session_state:
    votes_df = load_worksheet("투표결과", ["일정", "투표자"])
    st.session_state.votes = votes_df.to_dict(orient="records") if not votes_df.empty else []

# 8. 기여도 평가 로드
if 'evaluations' not in st.session_state:
    eval_df = load_worksheet("기여도평가", ["대상자", "점수", "코멘트"])
    st.session_state.evaluations = eval_df.to_dict(orient="records") if not eval_df.empty else []


# --- [수정 5] 회의록 구글 시트 저장 헬퍼 ---
def save_minutes_to_sheet():
    save_minutes = []
    for m in st.session_state.minutes:
        save_minutes.append({
            "시간": m["시간"],
            "내용": m["내용"],
            "댓글": json.dumps(m["댓글"], ensure_ascii=False)
        })
    conn.update(worksheet="회의록", data=pd.DataFrame(save_minutes))


# --- 작업 목록 저장 시 날짜 직렬화 헬퍼 ---
def serialize_tasks(tasks_df):
    save_df = tasks_df.copy()
    save_df["마감일"] = save_df["마감일"].apply(
        lambda x: str(x) if pd.notna(x) and x is not None else ""
    )
    # 완료 근거 NaN → 빈 문자열
    if "완료 근거" in save_df.columns:
        save_df["완료 근거"] = save_df["완료 근거"].fillna("")
    return save_df


# ===========================
# --- 사이드바 메뉴 ---
# ===========================
st.sidebar.title("📌 메뉴")
page = st.sidebar.radio(
    "이동할 페이지를 선택하세요:",
    ["통합 대시보드", "팀원 및 역할 관리", "프로젝트 및 작업 관리", "공지·회의록 및 투표", "기여도 평가"]
)


# ===========================
# --- 1. 통합 대시보드 ---
# ===========================
if page == "통합 대시보드":
    st.title("📊 통합 대시보드")

    if st.session_state.topic:
        st.subheader(f"🎯 현재 프로젝트 주제: {st.session_state.topic}")

        col1, col2 = st.columns(2)
        with col1:
            if st.session_state.final_deadline:
                today = datetime.date.today()
                f_deadline = st.session_state.final_deadline
                if isinstance(f_deadline, str):
                    f_deadline = datetime.datetime.strptime(f_deadline, "%Y-%m-%d").date()
                d_day = (f_deadline - today).days
                if d_day > 0:
                    st.info(f"⏳ 최종 마감일까지 **D-{d_day}** 남았습니다!")
                elif d_day == 0:
                    st.warning("🚨 오늘이 최종 마감일입니다!")
                else:
                    st.error(f"💥 마감일이 {abs(d_day)}일 지났습니다.")

        with col2:
            if not st.session_state.tasks.empty and "상태" in st.session_state.tasks.columns:
                total_tasks = len(st.session_state.tasks)
                completed_tasks = len(st.session_state.tasks[st.session_state.tasks["상태"] == "완료"])
                completion_rate = (completed_tasks / total_tasks) * 100
            else:
                completion_rate = 0
            st.metric(label="팀 전체 작업 완료율", value=f"{completion_rate:.1f}%")

        st.markdown("---")
        st.markdown("### 🚨 팀원 업무 부하 상태")

        if not st.session_state.tasks.empty and not st.session_state.team_members.empty:
            incomplete_tasks = st.session_state.tasks[st.session_state.tasks["상태"] != "완료"].copy()
            incomplete_tasks["예상 소요시간(시간)"] = pd.to_numeric(
                incomplete_tasks["예상 소요시간(시간)"], errors='coerce'
            ).fillna(0)
            member_hours = incomplete_tasks.groupby("담당자")["예상 소요시간(시간)"].sum().to_dict()

            overload_found = False
            for _, member in st.session_state.team_members.iterrows():
                name = member.get("이름", "")
                try:
                    avail_hours = float(member.get("주간 가용시간(시간)", 0) or 0)
                except Exception:
                    avail_hours = 0
                assigned_hours = member_hours.get(name, 0)

                if avail_hours > 0:
                    if assigned_hours > avail_hours:
                        st.error(f"⚠️ **{name}**님 과부하 상태! (가용: {avail_hours}시간 / 배정: {assigned_hours}시간)")
                        overload_found = True
                    elif assigned_hours > (avail_hours * 0.8):
                        st.warning(f"⚡ **{name}**님 업무 포화 근접 (가용: {avail_hours}시간 / 배정: {assigned_hours}시간)")
                        overload_found = True

            if not overload_found:
                st.success("✅ 현재 모든 팀원의 업무 부하가 가용 시간 내로 안전합니다.")
        else:
            st.write("배정된 작업이나 등록된 팀원이 없습니다.")

        st.markdown("---")
        st.markdown("### ⏰ 마감 임박 미완료 작업")

        if not st.session_state.tasks.empty:
            today = datetime.date.today()
            danger_tasks = []
            for _, row in st.session_state.tasks.iterrows():
                if row.get("상태") != "완료" and pd.notna(row.get("마감일")):
                    t_date = row["마감일"]
                    if isinstance(t_date, str):
                        try:
                            t_date = datetime.datetime.strptime(t_date, "%Y-%m-%d").date()
                        except Exception:
                            continue
                    if isinstance(t_date, datetime.date) and (t_date - today).days <= 2:
                        danger_tasks.append(row)

            if danger_tasks:
                st.dataframe(
                    pd.DataFrame(danger_tasks)[["작업명", "담당자", "마감일", "상태"]],
                    use_container_width=True
                )
            else:
                st.success("✅ 2일 이내에 마감이 임박한 미완료 작업이 없습니다.")
        else:
            st.write("등록된 작업이 없습니다.")

        st.markdown("---")
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
                content_preview = (
                    latest_minute['내용'][:40] + "..."
                    if len(latest_minute['내용']) > 40
                    else latest_minute['내용']
                )
                st.success(f"**[{latest_minute['시간']}]**\n\n{content_preview}")
            else:
                st.write("등록된 회의록이 없습니다.")

        st.markdown("---")
        st.markdown("### 📋 전체 작업 현황")
        st.dataframe(st.session_state.tasks, use_container_width=True)

    else:
        st.warning("프로젝트 주제가 아직 설정되지 않았습니다. '프로젝트 및 작업 관리' 탭에서 주제를 먼저 설정해주세요.")


# ===========================
# --- 2. 팀원 및 역할 관리 ---
# ===========================
elif page == "팀원 및 역할 관리":
    st.title("👥 팀원 및 역할 관리")

    st.markdown("### 📨 팀원 초대 링크 생성")
    if st.button("🔗 초대 링크 발급하기"):
        project_slug = st.session_state.topic if st.session_state.topic else "new-project"
        invite_url = f"https://teamplay-app.streamlit.app/invite?project={project_slug}"
        st.success(f"팀원 초대 링크가 생성되었습니다. 카카오톡이나 메신저로 공유하세요!\n\n`{invite_url}`")

    st.markdown("---")
    st.markdown("### ✍️ 팀원 명단 및 가용 시간 설정")
    st.caption("팀원의 이름, 역할 및 주간 협업 가능한 가용 시간을 입력해 주세요. (과부하 계산의 기준이 됩니다.)")

    edited_members = st.data_editor(
        st.session_state.team_members,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "주간 가용시간(시간)": st.column_config.NumberColumn(
                "주간 가용시간(시간)", min_value=1, max_value=168, step=1,
                help="일주일 동안 이 팀플에 쏟을 수 있는 순수 시간"
            )
        }
    )

    if st.button("💾 팀원 목록 저장"):
        st.session_state.team_members = edited_members
        conn.update(worksheet="팀원목록", data=edited_members)
        st.success("팀원 목록과 가용 시간이 구글 시트에 실시간으로 저장되었습니다!")


# ===========================
# --- 3. 프로젝트 및 작업 관리 ---
# ===========================
elif page == "프로젝트 및 작업 관리":
    st.title("📂 프로젝트 및 작업 관리")

    if not st.session_state.topic:
        st.markdown("### 1️⃣ 프로젝트 주제 및 최종 마감일 설정")
        new_topic = st.text_input("프로젝트의 큰 주제를 입력하세요:")
        final_date = st.date_input("최종 마감일을 선택하세요:")

        if st.button("주제 확정하기"):
            if new_topic:
                st.session_state.topic = new_topic
                st.session_state.final_deadline = final_date
                meta_df = pd.DataFrame([{"주제": new_topic, "최종마감일": str(final_date)}])
                conn.update(worksheet="프로젝트개요", data=meta_df)
                st.success("프로젝트 주제가 확정되어 구글 시트에 동기화되었습니다!")
                st.rerun()
            else:
                st.warning("주제를 입력해주세요!")
    else:
        st.info(f"⏰ 최종 마감일: {st.session_state.final_deadline} (💡 주제는 하나만 지정할 수 있습니다.)")

        st.markdown("### 2️⃣ 세부 작업 배정")

        with st.form("add_task_form", clear_on_submit=True):
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                task_name = st.text_input("세부 작업명")
            with col2:
                if not st.session_state.team_members.empty and "이름" in st.session_state.team_members.columns:
                    assignee_list = st.session_state.team_members["이름"].dropna().tolist()
                    assignee = st.selectbox("담당자", assignee_list) if assignee_list else st.text_input("담당자")
                else:
                    assignee = st.text_input("담당자 (팀원 우선 등록 필요)")
            with col3:
                task_hours = st.number_input("예상 소요시간(시간)", min_value=1, max_value=50, value=3)
            with col4:
                task_deadline = st.date_input("작업 마감일")

            submit_button = st.form_submit_button("➕ 작업 배정하기")

            if submit_button:
                if task_name and assignee:
                    new_task = pd.DataFrame({
                        "작업명": [task_name],
                        "담당자": [assignee],
                        "상태": ["미시작"],
                        "예상 소요시간(시간)": [task_hours],
                        "마감일": [str(task_deadline)],
                        "완료 근거": [""]
                    })
                    updated_tasks = pd.concat([st.session_state.tasks, new_task], ignore_index=True)
                    st.session_state.tasks = updated_tasks
                    conn.update(worksheet="작업목록", data=serialize_tasks(updated_tasks))
                    st.success(f"'{task_name}' 작업이 배정되어 구글 시트에 기록되었습니다!")
                    st.rerun()
                else:
                    st.warning("작업명과 담당자를 모두 입력해주세요.")

        st.markdown("#### 📋 세부 작업 목록 및 상태 업데이트")
        st.caption("💡 작업을 '완료'로 변경할 때는 반드시 '완료 근거'(구글드링크, 메모 등)를 작성해야 저장됩니다.")

        edited_tasks = st.data_editor(
            st.session_state.tasks,
            num_rows="dynamic",
            column_config={
                "상태": st.column_config.SelectboxColumn(
                    "상태", options=["미시작", "진행 중", "완료"], required=True
                ),
                "예상 소요시간(시간)": st.column_config.NumberColumn("예상 소요시간(시간)", min_value=1),
                "마감일": st.column_config.DateColumn("마감일"),
                "완료 근거": st.column_config.TextColumn("완료 근거 (링크 또는 진행 내용)")
            },
            use_container_width=True
        )

        if st.button("💾 작업 목록 저장"):
            # [수정 6] 완료 근거 NaN 처리 후 비교
            check_df = edited_tasks.copy()
            check_df["완료 근거"] = check_df["완료 근거"].fillna("").astype(str)

            invalid_completed_tasks = check_df[
                (check_df["상태"] == "완료") &
                (check_df["완료 근거"].str.strip() == "")
            ]

            if not invalid_completed_tasks.empty:
                st.error("🚨 저장 실패! 상태가 '완료'인 작업은 무임승차 방지를 위해 반드시 '완료 근거'(링크/파일/메모 등)를 입력해야 합니다.")
                st.info(f"근거가 누락된 작업: {', '.join(invalid_completed_tasks['작업명'].tolist())}")
            else:
                st.session_state.tasks = edited_tasks
                conn.update(worksheet="작업목록", data=serialize_tasks(edited_tasks))
                st.success("작업 목록과 상태가 구글 시트에 성공적으로 동기화되었습니다!")


# ===========================
# --- 4. 공지·회의록 및 투표 ---
# ===========================
elif page == "공지·회의록 및 투표":
    st.title("📢 공지·회의록 및 투표")
    tab1, tab2, tab3 = st.tabs(["📌 공지사항", "📝 회의록", "🗳️ 일정 투표"])

    # ---------- 공지사항 탭 ----------
    with tab1:
        new_notice = st.text_area("새로운 공지사항을 입력하세요:")
        if st.button("공지 올리기"):
            if new_notice:
                st.session_state.notices.append({
                    "시간": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "내용": new_notice
                })
                safe_update("공지사항", st.session_state.notices, ["시간", "내용"])
                st.success("공지가 등록되고 구글 시트에 저장되었습니다.")
                st.rerun()

        st.markdown("---")
        for notice in reversed(st.session_state.notices):
            st.info(f"**[{notice['시간']}]**\n\n{notice['내용']}")

    # ---------- 회의록 탭 ----------
    with tab2:
        st.markdown("### ✍️ 구조화된 회의록 작성")
        with st.form("structured_meeting_form", clear_on_submit=True):
            m_date = st.date_input("회의 일시", value=datetime.date.today())
            m_attendees = st.text_input("참석자 (예: 홍길동, 김철수)")
            m_discussion = st.text_area("💡 주요 논의 내용")
            m_decision = st.text_area("✅ 결정 사항 및 다음 행동 조치(Action Item)")
            submit_meeting = st.form_submit_button("회의록 저장")

            if submit_meeting:
                if m_discussion and m_decision:
                    structured_content = (
                        f"👥 **참석자:** {m_attendees}\n\n"
                        f"💬 **주요 논의:**\n{m_discussion}\n\n"
                        f"📌 **결정 사항:**\n{m_decision}"
                    )
                    st.session_state.minutes.append({
                        "시간": m_date.strftime("%Y-%m-%d"),
                        "내용": structured_content,
                        "댓글": []
                    })
                    save_minutes_to_sheet()
                    st.success("구조화된 회의록이 구글 시트에 저장되었습니다.")
                    st.rerun()
                else:
                    st.warning("논의 내용과 결정 사항을 입력해주세요.")

        st.markdown("---")
        for i, minute in enumerate(reversed(st.session_state.minutes)):
            with st.expander(f"🗓️ 회의록 일자: {minute['시간']}"):
                st.markdown(minute['내용'])
                st.markdown("#### 💬 관련 대화")
                for comment in minute['댓글']:
                    st.write(f"- {comment}")

                comment_input = st.text_input("댓글 입력", key=f"comment_{i}")
                if st.button("댓글 달기", key=f"btn_{i}"):
                    if comment_input:
                        actual_index = len(st.session_state.minutes) - 1 - i
                        st.session_state.minutes[actual_index]['댓글'].append(comment_input)
                        save_minutes_to_sheet()
                        st.rerun()

    # ---------- 일정 투표 탭 ----------
    with tab3:
        st.markdown("### 🗳️ 팀플 회의 일정 투표")

        col_v1, col_v2 = st.columns([2, 1])
        with col_v1:
            new_candidate = st.text_input("새로운 후보 일정 입력 (예: 6/15(월) 18:00)")
        with col_v2:
            st.write(" ")
            st.write(" ")
            if st.button("후보 추가") and new_candidate:
                if new_candidate not in st.session_state.candidates:
                    st.session_state.candidates.append(new_candidate)
                    safe_update("투표후보", pd.DataFrame({"후보 일정": st.session_state.candidates}), ["후보 일정"])
                    st.rerun()

        if st.session_state.candidates:
            st.markdown("#### 🗓️ 내 투표 제출")
            with st.form("vote_form"):
                voter = st.text_input("내 이름 입력")
                selected_options = st.multiselect(
                    "참여 가능한 일정을 모두 선택하세요 (복수 선택 가능)",
                    st.session_state.candidates
                )
                submit_vote = st.form_submit_button("투표하기")

                if submit_vote and voter and selected_options:
                    # 기존 투표자 제거 후 재투표
                    st.session_state.votes = [v for v in st.session_state.votes if v["투표자"] != voter]
                    for opt in selected_options:
                        st.session_state.votes.append({"일정": opt, "투표자": voter})
                    safe_update("투표결과", st.session_state.votes, ["일정", "투표자"])
                    st.success("투표가 성공적으로 반영되어 시트에 저장되었습니다!")
                    st.rerun()

            if st.session_state.votes:
                st.markdown("#### 📊 투표 결과 (가장 적합한 일정 추출)")
                vote_df = pd.DataFrame(st.session_state.votes)
                # [수정 7] pandas 버전 호환 value_counts 처리
                result = vote_df["일정"].value_counts().reset_index()
                result.columns = ["후보 일정", "득표 수"]

                st.dataframe(result, use_container_width=True)
                best_schedule = result.iloc[0]["후보 일정"]
                st.info(f"🎯 **현재 최적의 일정:** 가장 많은 팀원이 선택한 시간은 **[{best_schedule}]** 입니다!")
        else:
            st.info("아직 등록된 후보 일정이 없습니다. 회의 조율을 위해 상단에서 후보를 추가해 보세요.")


# ===========================
# --- 5. 기여도 평가 ---
# ===========================
elif page == "기여도 평가":
    st.title("🤝 익명 기여도 평가")
    st.markdown("프로젝트 종료 후, 익명으로 서로의 기여도를 평가합니다.")

    if st.session_state.topic and not st.session_state.team_members.empty:
        col1, col2 = st.columns(2)
        with col1:
            eval_target = st.selectbox(
                "평가할 팀원 선택",
                st.session_state.team_members["이름"].dropna().tolist()
            )
        with col2:
            score = st.slider("기여도 점수 (1점~5점)", min_value=1, max_value=5, value=3)

        eval_comment = st.text_area("익명 코멘트 남기기 (선택사항)")

        if st.button("평가 제출하기 (익명)"):
            st.session_state.evaluations.append({
                "대상자": eval_target,
                "점수": score,
                "코멘트": eval_comment
            })
            safe_update("기여도평가", st.session_state.evaluations, ["대상자", "점수", "코멘트"])
            st.success(f"{eval_target}님에 대한 평가가 익명으로 안전하게 제출되었습니다!")
            # [수정 8] 평가 제출 후 rerun 추가
            st.rerun()

        st.markdown("---")
        st.markdown("### 📊 현재까지의 평균 평가 점수")

        if st.session_state.evaluations:
            eval_df = pd.DataFrame(st.session_state.evaluations)
            avg_scores = eval_df.groupby("대상자")["점수"].mean().reset_index()
            avg_scores.rename(columns={"점수": "평균 점수"}, inplace=True)
            # [수정 9] 점수 소수점 1자리 포맷
            avg_scores["평균 점수"] = avg_scores["평균 점수"].round(1)
            st.dataframe(avg_scores, use_container_width=True)
        else:
            st.info("아직 제출된 평가가 없습니다.")
    else:
        st.warning("먼저 '팀원 및 역할 관리'에서 팀원을 등록하고, '프로젝트 관리'에서 주제를 설정해주세요.")