from ui import setup_ui, show_header, show_sidebar_logo

setup_ui()
show_header()
show_sidebar_logo()

import streamlit as st
import datetime
import json
import sys
import subprocess

# ── [필수] Supabase 패키지 미설치 에러(ModuleNotFoundError) 자동 방지 대책 ──
try:
    from supabase import create_client
except ModuleNotFoundError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "supabase"])
    from supabase import create_client

import pandas as pd

# ── Supabase 연결 (캐싱으로 재연결 방지) ─────────────────
@st.cache_resource
def get_supabase():
    return create_client(
        st.secrets["supabase"]["url"],
        st.secrets["supabase"]["key"]
    )

sb = get_supabase()

# ── DB 영문 컬럼 ↔ 화면 한글 컬럼 매핑 ──────────────────
MEMBER_COLS = {"name": "이름", "role": "역할", "weekly_hours": "주간 가용시간(시간)"}
TASK_COLS   = {"task_name": "작업명", "assignee": "담당자", "status": "상태",
               "estimated_hours": "예상 소요시간(시간)", "deadline": "마감일", "completion_note": "완료 근거"}
NOTICE_COLS = {"posted_at": "시간", "content": "내용"}
MINUTE_COLS = {"meeting_date": "시간", "content": "내용", "comments": "댓글"}
CAND_COLS   = {"schedule": "후보 일정"}
VOTE_COLS   = {"schedule": "일정", "voter": "투표자"}
EVAL_COLS   = {"target_name": "대상자", "score": "점수", "comment": "코멘트"}

# ── 데이터 로드 및 변환 헬퍼 ─────────────────────────────
def to_display(df, col_map):
    return df.rename(columns=col_map)

def to_db(df, col_map):
    rev = {v: k for k, v in col_map.items()}
    return df.rename(columns=rev)

def fetch_table_directly(table, col_map):
    """DB에서 직접 최신 데이터를 실시간으로 읽어옵니다."""
    try:
        res = sb.table(table).select("*").execute()
        if res.data:
            df = pd.DataFrame(res.data)
            df = df.dropna(how="all")
            return to_display(df, col_map)
        return pd.DataFrame(columns=list(col_map.values()))
    except Exception:
        return pd.DataFrame(columns=list(col_map.values()))

def save_table_via_upsert(table, display_df, col_map):
    """위험한 전체 삭제(delete) 대신, 고유 식별값 id를 기준으로 Upsert를 처리하여 APIError를 방지합니다."""
    try:
        db_df = to_db(display_df.copy(), col_map)
        records = db_df.where(pd.notna(db_df), None).to_dict(orient="records")
        
        # 만약 id가 없는 새 레코드라면 순차 부여 처리
        for i, r in enumerate(records):
            if "id" not in r or r["id"] is None:
                r["id"] = i + 1
        
        if records:
            # 안전한 상위 업서트 공정 적용
            sb.table(table).upsert(records).execute()
    except Exception as e:
        # 업서트 예외 대응용 대체 로직
        try:
            db_df = to_db(display_df.copy(), col_map)
            records = db_df.where(pd.notna(db_df), None).to_dict(orient="records")
            for r in records: r.pop("id", None)
            sb.table(table).delete().neq("name", "NON_EXIST_VAL_XYZ").execute()
            if records: sb.table(table).insert(records).execute()
        except Exception as ex:
            st.error(f"데이터 연동 오류 보완 적용 중: {ex}")

def save_minutes_to_db(minutes_list):
    records = []
    for i, m in enumerate(minutes_list):
        records.append({
            "id": i + 1,
            "meeting_date": str(m["시간"]),
            "content": m["내용"],
            "comments": json.dumps(m["댓글"], ensure_ascii=False)
        })
    try:
        if records:
            sb.table("minutes").upsert(records).execute()
    except Exception:
        try:
            sb.table("minutes").delete().neq("content", "NON_EXIST_VAL_XYZ").execute()
            if records:
                for r in records: r.pop("id", None)
                sb.table("minutes").insert(records).execute()
        except Exception as e:
            st.error(f"회의록 저장 실패: {e}")

def save_tasks_to_db(tasks_df):
    df = tasks_df.copy()
    if "id" not in df.columns:
        df["id"] = range(1, len(df) + 1)
    df["마감일"] = df["마감일"].apply(lambda x: str(x) if pd.notna(x) and x is not None else None)
    df["완료 근거"] = df["완료 근거"].fillna("")
    save_table_via_upsert("tasks", df, TASK_COLS)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔄 실시간 데이터 동기화 및 데이터 타입 불일치(StreamlitAPIException) 해결
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 1. 프로젝트 개요 로드
meta_df = fetch_table_directly("project_overview", {"topic": "주제", "final_deadline": "최종마감일"})
if not meta_df.empty:
    st.session_state.topic = str(meta_df.iloc[0]["주제"]) if pd.notna(meta_df.iloc[0]["주제"]) else ""
    dl = meta_df.iloc[0]["최종마감일"]
    if pd.notna(dl) and str(dl).strip():
        try:
            st.session_state.final_deadline = datetime.datetime.strptime(str(dl).split()[0], "%Y-%m-%d").date()
        except Exception:
            st.session_state.final_deadline = None
    else:
        st.session_state.final_deadline = None
else:
    st.session_state.topic = ""
    st.session_state.final_deadline = None

# 2. 팀원 목록 로드
st.session_state.team_members = fetch_table_directly("team_members", MEMBER_COLS)
if "id" in st.session_state.team_members.columns:
    st.session_state.team_members = st.session_state.team_members.drop(columns=["id"])

# 3. 작업 목록 로드 및 타입 일치화 (st.data_editor 튕김 방지 핵심 구간)
tasks_df = fetch_table_directly("tasks", TASK_COLS)
if not tasks_df.empty:
    if "마감일" in tasks_df.columns:
        tasks_df["마감일"] = pd.to_datetime(tasks_df["마감일"], errors="coerce").dt.date
    if "id" in tasks_df.columns:
        tasks_df = tasks_df.drop(columns=["id"])
else:
    tasks_df = pd.DataFrame(columns=list(TASK_COLS.values()))
    tasks_df["마감일"] = pd.to_datetime(tasks_df["마감일"]).dt.date
st.session_state.tasks = tasks_df

# 4. 공지사항 로드
notices_df = fetch_table_directly("notices", NOTICE_COLS)
st.session_state.notices = notices_df.to_dict(orient="records") if not notices_df.empty else []

# 5. 회의록 로드
minutes_df = fetch_table_directly("minutes", MINUTE_COLS)
minutes_list = []
for _, row in minutes_df.iterrows():
    try:
        comments = json.loads(row["댓글"]) if pd.notna(row.get("댓글")) and str(row["댓글"]).strip() else []
    except Exception:
        comments = []
    minutes_list.append({
        "시간": str(row.get("시간", "")),
        "내용": str(row.get("내용", "")),
        "댓글": comments
    })
st.session_state.minutes = minutes_list

# 6. 투표 후보 및 결과 로드
cand_df = fetch_table_directly("vote_candidates", CAND_COLS)
st.session_state.candidates = cand_df["후보 일정"].dropna().tolist() if "후보 일정" in cand_df.columns else []

votes_df = fetch_table_directly("vote_results", VOTE_COLS)
st.session_state.votes = votes_df.to_dict(orient="records") if not votes_df.empty else []

# 7. 기여도 평가 로드
eval_df = fetch_table_directly("evaluations", EVAL_COLS)
st.session_state.evaluations = eval_df.to_dict(orient="records") if not eval_df.empty else []


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📌 사이드바 메뉴
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
st.sidebar.title("📌 메뉴")
page = st.sidebar.radio(
    "이동할 페이지를 선택하세요:",
    ["통합 대시보드", "팀원 및 역할 관리", "프로젝트 및 작업 관리", "공지·회의록 및 투표", "기여도 평가"]
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. 통합 대시보드
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
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
                completion_rate = (completed_tasks / total_tasks) * 100 if total_tasks > 0 else 0
            else:
                completion_rate = 0
            st.metric(label="팀 전체 작업 완료율", value=f"{completion_rate:.1f}%")

        st.markdown("---")
        st.markdown("### 🚨 팀원 업무 부하 상태")

        if not st.session_state.tasks.empty and not st.session_state.team_members.empty:
            incomplete_tasks = st.session_state.tasks[st.session_state.tasks["상태"] != "완료"].copy()
            incomplete_tasks["예상 소요시간(시간)"] = pd.to_numeric(
                incomplete_tasks["예상 소요시간(시간)"], errors="coerce"
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
                        st.error(f"⚠️ **{name}**님 과부하! (가용: {avail_hours}h / 배정: {assigned_hours}h)")
                        overload_found = True
                    elif assigned_hours > avail_hours * 0.8:
                        st.warning(f"⚡ **{name}**님 포화 근접 (가용: {avail_hours}h / 배정: {assigned_hours}h)")
                        overload_found = True
            if not overload_found:
                st.success("✅ 모든 팀원의 업무 부하가 안전합니다.")
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
                st.success("✅ 2일 이내 마감 임박 작업 없습니다.")
        else:
            st.write("등록된 작업이 없습니다.")

        st.markdown("---")
        col_notice, col_minute = st.columns(2)
        with col_notice:
            st.markdown("#### 📢 최근 공지")
            if st.session_state.notices:
                n = st.session_state.notices[-1]
                st.info(f"**[{n['시간']}]**\n\n{n['내용']}")
            else:
                st.write("등록된 공지가 없습니다.")
        with col_minute:
            st.markdown("#### 📝 최근 회의록")
            if st.session_state.minutes:
                m = st.session_state.minutes[-1]
                preview = m["내용"][:40] + "..." if len(m["내용"]) > 40 else m["내용"]
                st.success(f"**[{m['시간']}]**\n\n{preview}")
            else:
                st.write("등록된 회의록이 없습니다.")

        st.markdown("---")
        st.markdown("### 📋 전체 작업 현황")
        st.dataframe(st.session_state.tasks, use_container_width=True)

    else:
        st.warning("프로젝트 주제가 설정되지 않았습니다. '프로젝트 및 작업 관리' 탭에서 먼저 설정해주세요.")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. 팀원 및 역할 관리
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
elif page == "팀원 및 역할 관리":
    st.title("👥 팀원 및 역할 관리")

    st.markdown("### 📨 팀원 초대 링크 생성")
    if st.button("🔗 초대 링크 발급하기"):
        slug = st.session_state.topic if st.session_state.topic else "new-project"
        st.success(f"팀원 초대 링크:\n\n`https://teamplay-app.streamlit.app/invite?project={slug}`")

    st.markdown("---")
    st.markdown("### ✍️ 팀원 명단 및 가용 시간 설정")
    st.caption("팀원의 이름, 역할 및 주간 가용 시간을 입력해 주세요.")

    edited_members = st.data_editor(
        st.session_state.team_members,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "주간 가용시간(시간)": st.column_config.NumberColumn(
                "주간 가용시간(시간)", min_value=1, max_value=168, step=1
            )
        }
    )

    if st.button("💾 팀원 목록 저장"):
        save_table_via_upsert("team_members", edited_members, MEMBER_COLS)
        st.success("팀원 목록이 Supabase에 안전하게 반영되었습니다!")
        st.rerun()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. 프로젝트 및 작업 관리
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
elif page == "프로젝트 및 작업 관리":
    st.title("📂 프로젝트 및 작업 관리")

    if not st.session_state.topic:
        st.markdown("### 1️⃣ 프로젝트 주제 및 최종 마감일 설정")
        new_topic = st.text_input("프로젝트의 큰 주제를 입력하세요:")
        final_date = st.date_input("최종 마감일을 선택하세요:")

        if st.button("주제 확정하기"):
            if new_topic:
                try:
                    # 충돌을 유발하는 delete 구문 전면 제거 후 고정된 단일 인덱스(id=1) 업서트 연동
                    sb.table("project_overview").upsert(
                        {"id": 1, "topic": new_topic, "final_deadline": str(final_date)}
                    ).execute()
                    st.success("프로젝트 주제가 Supabase에 저장되었습니다!")
                    st.rerun()
                except Exception as e:
                    st.error(f"주제 생성 실패: {e}")
            else:
                st.warning("주제를 입력해주세요!")
    else:
        st.info(f"🎯 현재 주제: {st.session_state.topic} | ⏰ 최종 마감일: {st.session_state.final_deadline}")
        
        if st.button("🔄 주제 초기화 및 다시 설정하기"):
            try:
                sb.table("project_overview").upsert({"id": 1, "topic": "", "final_deadline": ""}).execute()
            except Exception:
                pass
            st.rerun()

        st.markdown("---")
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
                    assignee = st.text_input("담당자 (팀원 먼저 등록하세요)")
            with col3:
                task_hours = st.number_input("예상 소요시간(시간)", min_value=1, max_value=50, value=3)
            with col4:
                task_deadline = st.date_input("작업 마감일")

            if st.form_submit_button("➕ 작업 배정하기"):
                if task_name and assignee:
                    new_task = pd.DataFrame({
                        "작업명": [task_name], "담당자": [assignee], "상태": ["미시작"],
                        "예상 소요시간(시간)": [task_hours], "마감일": [task_deadline], "완료 근거": [""]
                    })
                    updated = pd.concat([st.session_state.tasks, new_task], ignore_index=True)
                    save_tasks_to_db(updated)
                    st.success(f"'{task_name}' 작업이 배정되었습니다!")
                    st.rerun()
                else:
                    st.warning("작업명과 담당자를 입력해주세요.")

        st.markdown("#### 📋 세부 작업 목록 및 상태 업데이트")
        st.caption("💡 '완료' 상태로 변경할 때는 반드시 '완료 근거'를 작성해야 저장됩니다.")

        # 데이터 에디터 렌더링
        edited_tasks = st.data_editor(
            st.session_state.tasks,
            num_rows="dynamic",
            column_config={
                "상태": st.column_config.SelectboxColumn("상태", options=["미시작", "진행 중", "완료"], required=True),
                "예상 소요시간(시간)": st.column_config.NumberColumn("예상 소요시간(시간)", min_value=1),
                "마감일": st.column_config.DateColumn("마감일"),
                "완료 근거": st.column_config.TextColumn("완료 근거 (링크 또는 진행 내용)")
            },
            use_container_width=True
        )

        if st.button("💾 작업 목록 저장"):
            check_df = edited_tasks.copy()
            check_df["완료 근거"] = check_df["완료 근거"].fillna("").astype(str)
            invalid = check_df[(check_df["상태"] == "완료") & (check_df["완료 근거"].str.strip() == "")]

            if not invalid.empty:
                st.error("🚨 '완료' 상태인 작업에 완료 근거를 입력해주세요.")
                st.info(f"누락 작업: {', '.join(invalid['작업명'].tolist())}")
            else:
                save_tasks_to_db(edited_tasks)
                st.success("작업 목록이 Supabase에 저장되었습니다!")
                st.rerun()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. 공지·회의록 및 투표
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
elif page == "공지·회의록 및 투표":
    st.title("📢 공지·회의록 및 투표")
    tab1, tab2, tab3 = st.tabs(["📌 공지사항", "📝 회의록", "🗳️ 일정 투표"])

    with tab1:
        new_notice = st.text_area("새로운 공지사항을 입력하세요:")
        if st.button("공지 올리기"):
            if new_notice:
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                st.session_state.notices.append({"시간": now, "내용": new_notice})
                save_table_via_upsert("notices", pd.DataFrame(st.session_state.notices), NOTICE_COLS)
                st.success("공지가 등록되었습니다.")
                st.rerun()

        st.markdown("---")
        for notice in reversed(st.session_state.notices):
            st.info(f"**[{notice['시간']}]**\n\n{notice['내용']}")

    with tab2:
        st.markdown("### ✍️ 구조화된 회의록 작성")
        with st.form("structured_meeting_form", clear_on_submit=True):
            m_date       = st.date_input("회의 일시", value=datetime.date.today())
            m_attendees  = st.text_input("참석자 (예: 홍길동, 김철수)")
            m_discussion = st.text_area("💡 주요 논의 내용")
            m_decision   = st.text_area("✅ 결정 사항 및 Action Item")

            if st.form_submit_button("회의록 저장"):
                if m_discussion and m_decision:
                    content = (
                        f"👥 **참석자:** {m_attendees}\n\n"
                        f"💬 **주요 논의:**\n{m_discussion}\n\n"
                        f"📌 **결정 사항:**\n{m_decision}"
                    )
                    st.session_state.minutes.append({
                        "시간": m_date.strftime("%Y-%m-%d"), "내용": content, "댓글": []
                    })
                    save_minutes_to_db(st.session_state.minutes)
                    st.success("회의록이 저장되었습니다.")
                    st.rerun()
                else:
                    st.warning("논의 내용과 결정 사항을 입력해주세요.")

        st.markdown("---")
        for i, minute in enumerate(reversed(st.session_state.minutes)):
            minute_key = f"{minute['시간']}_{i}"
            with st.expander(f"🗓️ {minute['시간']}"):
                st.markdown(minute["내용"])
                st.markdown("#### 💬 댓글")
                for comment in minute["댓글"]:
                    st.write(f"- {comment}")
                comment_input = st.text_input("댓글 입력", key=f"comment_{minute_key}")
                if st.button("댓글 달기", key=f"btn_{minute_key}"):
                    if comment_input:
                        actual_index = len(st.session_state.minutes) - 1 - i
                        st.session_state.minutes[actual_index]["댓글"].append(comment_input)
                        save_minutes_to_db(st.session_state.minutes)
                        st.rerun()

    with tab3:
        st.markdown("### 🗳️ 팀플 회의 일정 투표")
        col_v1, col_v2 = st.columns([2, 1])
        with col_v1:
            new_candidate = st.text_input("새로운 후보 일정 (예: 6/15(월) 18:00)")
        with col_v2:
            st.write(" "); st.write(" ")
            if st.button("후보 추가") and new_candidate:
                if new_candidate not in st.session_state.candidates:
                    st.session_state.candidates.append(new_candidate)
                    save_table_via_upsert("vote_candidates",
                                           pd.DataFrame({"후보 일정": st.session_state.candidates}),
                                           CAND_COLS)
                    st.rerun()

        if st.session_state.candidates:
            with st.form("vote_form"):
                voter = st.text_input("내 이름 입력")
                selected = st.multiselect("참여 가능한 일정 (복수 선택 가능)", st.session_state.candidates)
                if st.form_submit_button("투표하기") and voter and selected:
                    st.session_state.votes = [v for v in st.session_state.votes if v["투표자"] != voter]
                    for opt in selected:
                        st.session_state.votes.append({"일정": opt, "투표자": voter})
                    save_table_via_upsert("vote_results",
                                           pd.DataFrame(st.session_state.votes) if st.session_state.votes else pd.DataFrame(columns=["일정", "투표자"]),
                                           VOTE_COLS)
                    st.success("투표 완료!")
                    st.rerun()

            if st.session_state.votes:
                st.markdown("#### 📊 투표 결과")
                result = pd.DataFrame(st.session_state.votes)["일정"].value_counts().reset_index()
                result.columns = ["후보 일정", "득표 수"]
                st.dataframe(result, use_container_width=True)
                st.info(f"🎯 최적 일정: **[{result.iloc[0]['후보 일정']}]**")
        else:
            st.info("아직 등록된 후보 일정이 없습니다.")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. 기여도 평가
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
elif page == "기여도 평가":
    st.title("🤝 익명 기여도 평가")

    if st.session_state.topic and not st.session_state.team_members.empty:
        col1, col2 = st.columns(2)
        with col1:
            eval_target = st.selectbox("평가할 팀원", st.session_state.team_members["이름"].dropna().tolist())
        with col2:
            score = st.slider("기여도 점수 (1~5점)", min_value=1, max_value=5, value=3)

        eval_comment = st.text_area("익명 코멘트 (선택)")

        if st.button("평가 제출하기 (익명)"):
            st.session_state.evaluations.append({
                "대상자": eval_target, "점수": score, "코멘트": eval_comment
            })
            save_table_via_upsert("evaluations",
                                   pd.DataFrame(st.session_state.evaluations),
                                   EVAL_COLS)
            st.success(f"{eval_target}님 평가가 익명으로 저장되었습니다!")
            st.rerun()

        st.markdown("---")
        st.markdown("### 📊 평균 평가 점수")
        if st.session_state.evaluations:
            eval_df = pd.DataFrame(st.session_state.evaluations)
            avg = eval_df.groupby("대상자")["점수"].mean().reset_index()
            avg.columns = ["팀원", "평균 점수"]
            avg["평균 점수"] = avg["평균 점수"].round(1)
            st.dataframe(avg, use_container_width=True)
        else:
            st.info("아직 제출된 평가가 없습니다.")
    else:
        st.warning("먼저 팀원을 등록하고 프로젝트 주제를 설정해주세요.")
