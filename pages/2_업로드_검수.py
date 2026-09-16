import hashlib
import sys
from datetime import date
from pathlib import Path
import pandas as pd
import streamlit as st
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.auth import can_upload, require_login
from app.db import RAW_DIR, get_connection, ensure_schema
from app.services.upload_parser import detect_and_parse
from app.services.import_service import commit_import, review_rows, editable_import_frame
from app.ui import category_selector, inject_css, render_header

st.set_page_config(page_title='업로드·검수', layout='wide')
inject_css()
user = require_login()
conn = get_connection()
ensure_schema(conn)
from app.auth import require_menu, has_permission
require_menu('upload')
render_header()
category = category_selector()
st.subheader('엑셀 업로드·검수')
if 'import_sync_notice' in st.session_state:
    st.success(st.session_state.pop('import_sync_notice'))
st.caption('ERP 입고 장표의 입고일 기본값은 업로드일이며 검수 표에서 변경할 수 있습니다. 마스터 파일은 기존 날짜와 완료 이력을 보존합니다.')
logs = pd.read_sql_query('SELECT file_name AS 파일명, row_count AS 반영행수, status AS 상태, uploaded_by AS 업로더, created_at AS 기록시간, note AS 반영내역 FROM upload_logs WHERE category=? ORDER BY id DESC LIMIT 50', conn, params=[category])
with st.expander('업로드 이력', expanded=False):
    st.dataframe(logs, hide_index=True, use_container_width=True)
    from app.table_ui import selected_download
    selected_download(logs, '업로드이력', menu='upload')
if not can_upload():
    st.info('조회 전용입니다. 업로드·검수 실행 권한은 관리자에게 요청하세요.')
    st.stop()
upload = st.file_uploader('마스터 또는 ERP 입고 장표', type=['xls','xlsx'], key=f'file_{category}')
if upload is None:
    st.info('파일을 선택하면 내용을 확인하고 수정할 수 있습니다.')
    st.stop()
digest = hashlib.sha256(upload.getvalue()).hexdigest()
key = f'import_{category}_{digest}'
if conn.execute('SELECT 1 FROM import_batches WHERE digest=? AND category=?', (digest,category)).fetchone():
    st.success('이 파일은 이미 반영되었습니다. 다른 파일을 선택하세요.')
    st.stop()
if key not in st.session_state:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    source = RAW_DIR / f'{digest}{Path(upload.name).suffix.lower()}'
    if not source.exists():
        source.write_bytes(upload.getvalue())
    try:
        frame, kind = detect_and_parse(source, category, conn)
    except Exception as exc:
        st.error(f'파일을 읽을 수 없습니다: {exc}')
        st.stop()
    st.session_state[key] = {'frame':frame,'kind':kind,'day':date.today()}
state = st.session_state[key]
with st.expander('담당자 등록'):
    name = st.text_input('신규 담당자명', key=f'manager_{key}')
    if st.button('담당자 등록', icon=':material/add_circle:') and name.strip():
        conn.execute('INSERT INTO managers(name,is_active) VALUES(?,1) ON CONFLICT(name) DO UPDATE SET is_active=1', (name.strip(),))
        conn.commit()
        st.success('등록되었습니다.')
st.caption('검수 표의 모든 업무 항목을 수정할 수 있습니다. 날짜는 YYYY-MM-DD, 숫자는 숫자로 입력하세요. 투입공수의 - 또는 빈칸은 공수 미등록으로 반영합니다. 원본 업로드 파일은 별도 보존하며 확인사항은 아래에서 자동 계산합니다.')
editable = editable_import_frame(state['frame'], state['kind'], state['day'])
edited = st.data_editor(editable, num_rows='dynamic', hide_index=True, use_container_width=True,
    column_config={col:st.column_config.TextColumn(col) for col in editable.columns}, key=f'editor_v2_{key}')
reviewed = review_rows(edited, conn)
issues = reviewed[reviewed['has_issue']]
st.write(f'검수 대상 {len(reviewed):,}건 · 확인 필요 {len(issues):,}건')
if not issues.empty:
    st.dataframe(issues.style.set_properties(**{'background-color':'#FCEBEB'}), hide_index=True, use_container_width=True)
checked = st.checkbox('수정 내용과 확인 필요 항목을 검수했습니다.', key=f'check_{key}')
sync_ok=True
if state['kind']=='master':
    st.caption('누적 마스터: 기존 번호와 시리얼·모델명·입고일로 대상을 확인합니다. 동일 항목은 건너뛰고 변경값만 갱신합니다. 빈칸과 공수 -는 기존 값을 지우지 않습니다. 기존 중복·식별 충돌은 먼저 정리해야 합니다.')
    try:
        summary=commit_import(conn,reviewed,category,digest,upload.name,state['day'],user['login_id'],state['kind'],reviewed_dates=True,preview=True)
        st.info(f'반영 예정: 신규 {summary["신규"]:,}건 · 변경 {summary["변경"]:,}건 · 동일 건너뜀 {summary["동일"]:,}건')
    except (ValueError,PermissionError) as exc:
        sync_ok=False
        st.error(str(exc))
if st.button('검수 완료 · 마스터 반영', type='primary', disabled=not checked or not sync_ok, icon=':material/task_alt:'):
    try:
        stats = commit_import(conn, reviewed, category, digest, upload.name, state['day'], user['login_id'], state['kind'], reviewed_dates=True,return_summary=True)
    except (ValueError, PermissionError) as exc:
        st.error(str(exc))
    else:
        st.session_state.pop(key, None)
        st.session_state['import_sync_notice']=f'신규 {stats["신규"]:,}건 · 변경 {stats["변경"]:,}건 반영 / 동일 {stats["동일"]:,}건 건너뜀'
        st.rerun()
