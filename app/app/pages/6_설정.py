import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.auth import require_login
from app.table_ui import selectable_table, search_table
from app.services.manager_service import delete_users, update_user_profile
from app.db import get_connection, ensure_schema
from app.services import settings_service
from app.ui import guard_admin, inject_css, render_header

st.set_page_config(page_title="설정", layout="wide")
inject_css()
actor = require_login()
guard_admin()
conn = get_connection()
ensure_schema(conn)
render_header()

inventory_col, cost_col, category_col = st.columns(3, gap='medium')
with inventory_col, st.container(border=True, key='settings_inventory_card'):
    st.markdown('### :material/inventory_2: 재고 관리 기준')
    c1, c2 = st.columns(2)
    with c1:
        fin = st.number_input('완제품 (일)', min_value=1, value=settings_service.get_threshold_days(conn, '완제품'), width=200)
    with c2:
        rent = st.number_input('대여 (일)', min_value=1, value=settings_service.get_threshold_days(conn, '대여'), width=200)
    all_gubun = settings_service.list_distinct_구분(conn)
    excluded = settings_service.get_excluded_status_values(conn)
    selected = st.multiselect(':material/filter_list: 재고 제외 구분', options=sorted(set(all_gubun + excluded)), default=excluded, placeholder='제외할 구분 선택')
with cost_col, st.container(border=True, key='settings_cost_card'):
    st.markdown('### :material/calculate: 비용 계산 기준')
    rate = st.number_input('분당임율 (원/분)', min_value=0, value=int(settings_service.get_minute_wage_rate(conn)), width=240)
    st.caption('재작업 비용 = 투입공수 × 분당임율 × 60')
    st.caption('투입공수는 시간 단위로 계산합니다.')
with category_col, st.container(border=True, key='settings_category_card'):
    st.markdown('### :material/category: 분류 항목 설정')
    model_opts = st.text_input('MODEL군 (콤마 구분)', value=','.join(settings_service.get_options(conn, 'model_group_options', ['DISPLAY'])))
    work_opts = st.text_input('작업구분 (콤마 구분)', value=','.join(settings_service.get_options(conn, 'work_type_options', ['재작업'])))

with st.container(horizontal=True, horizontal_alignment='right'):
    save_settings = st.button('설정 저장', type='primary', icon=':material/save:')
if save_settings:
    settings_service.set_value(conn, "long_term_threshold_days", str(int(fin)), "완제품")
    settings_service.set_value(conn, "long_term_threshold_days", str(int(rent)), "대여")
    settings_service.set_value(conn, "excluded_status_values", json.dumps(selected, ensure_ascii=False))
    settings_service.set_value(conn, "minute_wage_rate", str(int(rate)))
    settings_service.set_value(conn, "model_group_options", json.dumps([x.strip() for x in model_opts.split(",") if x.strip()], ensure_ascii=False))
    settings_service.set_value(conn, "work_type_options", json.dumps([x.strip() for x in work_opts.split(",") if x.strip()], ensure_ascii=False))
    st.success("저장했습니다. 개요/재고 수치가 다음 조회부터 반영됩니다.")

@st.dialog('선택 항목 삭제 확인')
def confirm_settings_delete(kind, rows):
    st.write(f'{kind} {len(rows)}건을 삭제합니다.')
    st.dataframe(rows, hide_index=True)
    st.caption('담당자 또는 사용자 목록만 삭제하며 기존 재작업 이력은 유지됩니다.')
    if st.button('삭제 확정',type='primary', icon=':material/delete:'):
        try:
            if kind == '사용자':
                delete_users(conn, rows['id'].tolist(), actor['login_id'])
            else:
                conn.executemany('DELETE FROM managers WHERE id=?',[(int(i),) for i in rows['id']])
                conn.commit()
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.rerun()
@st.dialog('선택 사용자 수정')
def edit_selected_user(user_id):
    record = conn.execute('SELECT * FROM users WHERE id=?',(user_id,)).fetchone()
    if record is None:
        st.error('사용자가 존재하지 않습니다.')
        return
    with st.form(f'edit_user_{user_id}'):
        company = st.text_input('회사명', value=record['company'] or '')
        name = st.text_input('이름', value=record['name'] or '')
        team = st.text_input('담당팀', value=record['team'] or '')
        position = st.text_input('직책', value=record['position'] or '')
        email = st.text_input('로그인 아이디 (이메일)', value=record['email'] or '')
        if st.form_submit_button('수정 저장',type='primary', icon=':material/edit:'):
            try:
                update_user_profile(conn,user_id,actor['login_id'],company,name,team,position,email)
            except (ValueError,PermissionError) as exc:
                st.error(str(exc))
            else:
                st.session_state['user_edit_notice'] = '사용자 정보를 수정했습니다.'
                st.rerun()
manager_list_col, manager_add_col = st.columns([3,1], gap='medium')
with manager_list_col, st.container(border=True, key='settings_manager_list'):
    st.markdown('### :material/groups: 담당자명 목록')
    managers = pd.DataFrame([dict(r) for r in conn.execute("SELECT id, name, team, is_active FROM managers ORDER BY name").fetchall()], columns=['id','name','team','is_active'])
    managers = search_table(managers, 'settings_managers_search')
    st.caption('이름으로 담당팀을 자동 반영합니다. 마스터에 담당팀이 이미 있으면 유지하고, 빈 담당팀만 채웁니다.')
    edited, manager_selected = selectable_table(managers, 'settings_managers', editable_columns=['name','team','is_active'], column_config={'name':'담당자명','team':'담당팀','is_active':st.column_config.NumberColumn('사용 여부 (1/0)',min_value=0,max_value=1,step=1)})
    manager_actions = st.container(horizontal=True, gap='small')
    if manager_actions.button("담당자 목록 저장", icon=':material/save:'):
        names = edited['name'].fillna('').astype(str).str.strip()
        if names.eq('').any() or names.duplicated().any():
            st.error('담당자명은 빈칸 또는 중복으로 저장할 수 없습니다.')
            st.stop()
        for row in edited.to_dict(orient="records"):
            name = str(row.get("name") or "").strip()
            if not name:
                continue
            active = 1 if row.get("is_active") in (1, True, "1") else 0
            if row.get("id") and not pd.isna(row.get("id")):
                team = '' if pd.isna(row.get('team')) else str(row.get('team') or '').strip()
                conn.execute("UPDATE managers SET name=?, team=?, is_active=? WHERE id=?", (name, team, active, int(row["id"])))
            else:
                conn.execute(
                    "INSERT INTO managers (name, is_active) VALUES (?, ?) ON CONFLICT(name) DO UPDATE SET is_active=excluded.is_active",
                    (name, active),
                )
        conn.execute("""UPDATE rework_items SET 담당팀=(SELECT team FROM managers WHERE TRIM(managers.name)=TRIM(rework_items.담당자) AND is_active=1 AND TRIM(COALESCE(team,''))<>'') WHERE TRIM(COALESCE(담당팀,''))='' AND EXISTS(SELECT 1 FROM managers WHERE TRIM(managers.name)=TRIM(rework_items.담당자) AND is_active=1 AND TRIM(COALESCE(team,''))<>'')""")
        conn.commit()
        st.success("담당자 목록과 기존 마스터의 빈 담당팀을 반영했습니다.")

    if manager_actions.button('선택 담당자 삭제',disabled=manager_selected.empty, icon=':material/delete:'):
        confirm_settings_delete('담당자',manager_selected)
with manager_add_col, st.container(border=True, key='settings_manager_add'):
    st.markdown('### :material/person_add: 담당자 추가')
    st.caption('목록에서 이름·담당팀을 직접 수정한 뒤 저장할 수 있습니다.')
    with st.form('add_manager', border=False):
        new_name = st.text_input('추가 담당자명')
        new_team = st.text_input('추가 담당팀')
        if st.form_submit_button('담당자 추가', icon=':material/person_add:'):
            if not new_name.strip():
                st.error('담당자명을 입력하세요.')
            elif conn.execute('SELECT 1 FROM managers WHERE name=?',(new_name.strip(),)).fetchone():
                st.error('이미 등록된 담당자명입니다.')
            else:
                conn.execute('INSERT INTO managers(name,team,is_active) VALUES(?,?,1)',(new_name.strip(),new_team.strip()))
                conn.commit()
                st.rerun()

with st.container(border=True, key='settings_user_list'):
    st.markdown('### :material/verified_user: 사용자 승인')
    users = pd.DataFrame([dict(r) for r in conn.execute(
        "SELECT id, company, name, team, position, login_id, email, role, approved, can_upload, created_at FROM users ORDER BY id"
    ).fetchall()])
    approval_filter = st.selectbox(
        ':material/filter_list: 승인 상태', ['전체', '승인 완료', '승인 대기'],
        key='settings_user_approval_filter', width=240)
    approved_count = int(users['approved'].eq(1).sum())
    st.caption(f'전체 {len(users):,}명 · 승인 완료 {approved_count:,}명 · 승인 대기 {len(users)-approved_count:,}명')
    if approval_filter != '전체':
        users = users[users['approved'].eq(1 if approval_filter == '승인 완료' else 0)].copy()
    users['approved'] = users['approved'].map({1: '승인 완료', 0: '승인 대기'})
    users = search_table(users, 'settings_users_search')
    _, user_selected = selectable_table(users, 'settings_users', column_config={'approved': '승인 상태'})
    user_actions = st.container(horizontal=True, gap='small')
    if user_actions.button('선택 사용자 삭제',disabled=user_selected.empty, icon=':material/delete:'):
        confirm_settings_delete('사용자',user_selected)
    if user_actions.button('선택 사용자 승인',disabled=user_selected.empty, icon=':material/verified_user:'):
        conn.executemany('UPDATE users SET approved=1 WHERE id=?',[(int(i),) for i in user_selected['id']])
        conn.commit()
        st.rerun()
    if 'user_edit_notice' in st.session_state:
        st.success(st.session_state.pop('user_edit_notice'))
    st.caption('수정할 사용자 한 명을 선택하세요. 역할과 업로드 권한은 아래 권한 설정에서 변경할 수 있습니다.')
    if user_actions.button('선택 사용자 수정',disabled=len(user_selected)!=1, icon=':material/edit:'):
        edit_selected_user(int(user_selected.iloc[0]['id']))

permission_col, reset_col = st.columns([2,1], gap='medium')
with permission_col, st.container(border=True, key='settings_permissions'):
    st.markdown('### :material/admin_panel_settings: 사용자별 역할 / 메뉴 권한')
    from app.services.permissions import MENUS, allowed
    all_users = [dict(r) for r in conn.execute('SELECT * FROM users ORDER BY name')]
    labels = {r['id']:f"{r['name']} · {r['email'] or r['login_id']}" for r in all_users}
    uid = st.selectbox(':material/filter_list: 권한 설정 대상',list(labels),format_func=labels.get)
    target_user = next(r for r in all_users if r['id']==uid)
    roles = ['관리자','담당자','일반']
    role = st.selectbox(':material/admin_panel_settings: 역할',roles,index=roles.index(target_user['role']),key=f'role_{uid}')
    reset_defaults = st.checkbox('역할 기본값 적용 (기존 개별 권한 초기화)',key=f'defaults_{uid}')
    st.caption('관리자: 모든 권한 · 담당자: 조회 및 다운로드 · 일반: 조회만. 개별 권한으로 변경할 수 있습니다.')
    base = dict(target_user)
    base['role'] = role
    if reset_defaults or role != target_user['role']:
        base.update(permissions='{}',can_upload=0)
    rows = [{'메뉴':label,'조회':allowed(base,key),'다운로드':allowed(base,key,'download'),'등록·수정·삭제':allowed(base,key,'edit') if key in ('upload','inventory') else False} for key,label in MENUS.items()]
    permission_table = st.data_editor(pd.DataFrame(rows),hide_index=True,disabled=True if role=='관리자' else ['메뉴'],key=f'permissions_{uid}_{role}_{reset_defaults}')
    st.caption('등록·수정·삭제는 업로드·검수 및 재고현황에 적용됩니다. 조회를 해제하면 해당 메뉴의 모든 작업이 제한됩니다.')
    if st.button('권한 저장', icon=':material/save:'):
        if target_user['role']=='관리자' and role!='관리자' and conn.execute("SELECT COUNT(*) FROM users WHERE role='관리자' AND approved=1").fetchone()[0]<=1:
            st.error('최소 한 명의 승인된 관리자가 필요합니다.')
        else:
            permissions = {key:{'view':bool(row['조회']),'download':bool(row['다운로드']),'edit':bool(row['등록·수정·삭제']) if key in ('upload','inventory') else False} for key,row in zip(MENUS,permission_table.to_dict('records'))}
            conn.execute('UPDATE users SET role=?,permissions=?,can_upload=? WHERE id=?',(role,json.dumps(permissions,ensure_ascii=False),int(permissions['upload']['edit']),uid))
            conn.commit()
            st.success('권한을 저장했습니다. 다음 화면 실행부터 적용됩니다.')
with reset_col, st.container(border=True, key='settings_reset'):
    st.markdown('### :material/key: 비밀번호 재설정')
    st.caption('요청자의 신원을 직접 확인한 뒤 코드를 발급하세요. 코드는 30분 동안 한 번만 유효하며, 재발급 시 이전 코드는 무효화됩니다.')
    reset_users=conn.execute('SELECT id,name,email FROM users WHERE approved=1 AND email IS NOT NULL ORDER BY name').fetchall()
    if reset_users:
        labels={r['id']:f"{r['name']} · {r['email']}" for r in reset_users}
        with st.form('admin_reset_issue', border=False):
            target_id=st.selectbox(':material/filter_list: 재설정 대상',list(labels),format_func=labels.get)
            verified=st.checkbox('요청자 본인임을 확인했습니다.')
            admin_password=st.text_input('관리자 본인 비밀번호',type='password')
            if st.form_submit_button('일회용 코드 발급', icon=':material/key:'):
                if not verified:
                    st.error('요청자 본인 확인 후 발급하세요.')
                else:
                    from app.auth import current_user
                    from app.services.account_service import issue_reset
                    try:
                        code=issue_reset(conn,current_user()['id'],admin_password,target_id)
                    except (PermissionError,ValueError) as exc:
                        st.error(str(exc))
                    else:
                        st.success(f'{labels[target_id]} 계정의 재설정 코드입니다. 본인에게 직접 전달하세요.')
                        st.code(code,language=None)
    else:
        st.info('이메일을 등록하고 승인된 계정이 없습니다. 사용자 정보에서 이메일을 확인하세요.')

from app.backup_ui import render_backup_tools
render_backup_tools(conn)
