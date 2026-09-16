import io
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
from openpyxl import Workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.auth import can_edit, require_login
from app.data_access import complete_items, fetch_items, update_item_fields, delete_inventory_items
from app.db import get_connection, ensure_schema
from app.services.inventory import annotate_inventory
from app.ui import category_selector, inject_css, render_header
from app.table_ui import search_table, selectable_table, selected_download

st.set_page_config(page_title="재고현황", layout="wide")
inject_css()
user = require_login()
conn = get_connection()
ensure_schema(conn)
from app.auth import require_menu, has_permission
require_menu('inventory')
render_header()
category = category_selector()
editable = can_edit()

df = fetch_items(conn, category)
if df.empty:
    st.warning("데이터가 없습니다.")
    st.stop()
df = annotate_inventory(df, conn)
inv = df[df["is_inventory"]].copy()

with st.container(width=1240, key='compact_filters'):
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        models = ["(전체)"] + sorted([x for x in inv["모델명"].dropna().unique().tolist()])
        model = st.selectbox(':material/inventory_2: 모델명', models)
    with c2:
        managers = ["(전체)"] + sorted([x for x in inv["담당자"].dropna().unique().tolist()])
        manager = st.selectbox(':material/person: 담당자', managers)
    with c3:
        sites = ["(전체)"] + sorted([x for x in inv["site"].dropna().unique().tolist()])
        site = st.selectbox(':material/location_on: SITE', sites)
    with c4:
        teams = ["(전체)"] + sorted([x for x in inv["담당팀"].dropna().unique().tolist()])
        team = st.selectbox(':material/groups: 담당팀', teams)

    with c5:
        gubuns = ["(전체)"] + sorted([x for x in inv["구분"].dropna().unique().tolist()])
        gubun = st.selectbox(':material/filter_list: 구분', gubuns)
    c6, c7, c8, _ = st.columns([1, 1, 1, 2])
    with c6:
        date_from = st.date_input(':material/calendar_month: 입고 시작', value=None)
    with c7:
        date_to = st.date_input(':material/calendar_month: 입고 종료', value=None)
    with c8:
        only_long = st.toggle("장기재고만 보기", value=False)

view = inv.copy()
if model != "(전체)":
    view = view[view["모델명"] == model]
if manager != "(전체)":
    view = view[view["담당자"] == manager]
if site != "(전체)":
    view = view[view["site"] == site]
if team != "(전체)":
    view = view[view["담당팀"] == team]
if gubun != "(전체)":
    view = view[view["구분"] == gubun]
if date_from:
    view = view[pd.to_datetime(view["입고일"], errors="coerce") >= pd.Timestamp(date_from)]
if date_to:
    view = view[pd.to_datetime(view["입고일"], errors="coerce") <= pd.Timestamp(date_to)]
if only_long:
    view = view[view["is_long_term"] == True]

show_cols = [
    "id", "입고일", "담당자", "담당팀", "site", "모델명", "serial",
    "입고수량", "투입공수", "작업주체", "변경모델명", "변경serial", "구분", "재작업내용", "비고_원문", "age_days", "is_long_term",
]
view_show = view[show_cols] if not view.empty else view

def to_xlsx(frame: pd.DataFrame) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "재고현황"
    if frame.empty:
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()
    ws.append(list(frame.columns))
    for rec in frame.itertuples(index=False, name=None):
        ws.append(list(rec))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def filtered_download(filtered):
    if has_permission('inventory','download'):
        st.download_button(
            "필터링된 결과 다운로드",
            data=to_xlsx(filtered[show_cols] if not filtered.empty else filtered),
            file_name=f"{category}_재고현황_필터.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
         icon=':material/download:')

view = search_table(view, f'inv_search_{category}', toolbar_action=filtered_download)
view_show = view[show_cols] if not view.empty else view

edited, selected = selectable_table(view_show, f'inv_editor_{category}',
    editable_columns=[c for c in show_cols if c not in ['id','age_days','is_long_term','비고_원문']] if editable else (),
    column_config={"입고수량": st.column_config.NumberColumn(min_value=0, step=1), "투입공수": st.column_config.NumberColumn(min_value=0, step=0.1)})
manage_col, edit_col, complete_col = st.columns(3, gap='medium')
with manage_col, st.container(border=True, key='inventory_manage_card'):
    st.markdown('### :material/checklist: 선택 항목 관리')
    quantity = pd.to_numeric(selected['입고수량'], errors='coerce').fillna(0).sum() if '입고수량' in selected else 0
    st.caption(f'선택 {len(selected):,}건 · 수량 {quantity:,.0f}대')
    selected_download(selected, f'{category}_재고현황', menu='inventory')
    delete_slot = st.container()
if editable:
    selected_ids = selected['id'].tolist() if not selected.empty else []

    @st.dialog('선택 재고 삭제 확인', width='large')
    def confirm_delete(ids):
        targets = view_show[view_show['id'].isin(ids)]
        st.write(f'잘못 입력한 재고 **{len(ids)}건**을 삭제합니다.')
        st.dataframe(targets, hide_index=True, use_container_width=True)
        st.caption('삭제한 항목은 재고·집계·마스터 다운로드에서 제외됩니다. 삭제 전 데이터와 사유는 삭제 이력에 보관됩니다.')
        reason = st.text_input('삭제 사유', placeholder='예: 중복 입력, 잘못 등록한 품목')
        confirmed = st.checkbox('위 항목의 삭제를 확인했습니다.')
        if st.button('삭제 확정', type='primary', disabled=not confirmed or not reason.strip(), icon=':material/delete:'):
            try:
                count = delete_inventory_items(conn, ids, category, user['login_id'], reason)
            except (ValueError, PermissionError) as exc:
                st.error(str(exc))
            else:
                st.session_state['inventory_delete_notice'] = f'{count}건을 삭제했습니다.'
                st.rerun()

    with delete_slot:
        if 'inventory_delete_notice' in st.session_state:
            st.success(st.session_state.pop('inventory_delete_notice'))
        if st.button('선택 항목 삭제', disabled=not selected_ids, icon=':material/delete:'):
            confirm_delete(selected_ids)
    with edit_col, st.container(border=True, key='inventory_edit_card'):
        st.markdown('### :material/edit: 정보 수정')
        new_in_date = st.date_input(':material/calendar_month: 입고일 일괄수정 값', value=date.today())
        if st.button("선택 행 입고일 일괄수정", disabled=not selected_ids, icon=':material/edit:'):
            for item_id in selected_ids:
                update_item_fields(conn, int(item_id), {"입고일": new_in_date.isoformat()}, user["login_id"])
            conn.commit()
            st.success(f"{len(selected_ids)}건 입고일 수정")
            st.rerun()
        if st.button("편집 내용 저장", icon=':material/save:'):
            original = view_show.set_index("id")
            for row in edited.to_dict(orient="records"):
                item_id = int(row["id"])
                fields = {}
                for col in ["입고일", "담당자", "담당팀", "site", "모델명", "serial", "입고수량", "투입공수", "작업주체", "변경모델명", "변경serial", "구분", "재작업내용"]:
                    new_val = row.get(col)
                    old_val = original.loc[item_id, col] if item_id in original.index else None
                    if str(new_val) != str(old_val):
                        fields[col] = None if pd.isna(new_val) else new_val
                if fields:
                    update_item_fields(conn, item_id, fields, user["login_id"])
            conn.commit()
            st.success("저장했습니다.")
            st.rerun()
    
    with complete_col, st.container(border=True, key='inventory_complete_card'):
        st.markdown('### :material/task_alt: 완료 처리')
        complete_date = st.date_input(':material/calendar_month: 완료일', value=date.today(), key="complete_date")
        complete_gubun = st.text_input("완료 시 구분 값 (비우면 기존 유지)")
        if st.button("선택 행 완료 처리", disabled=not selected_ids, type="primary", icon=':material/task_alt:'):
            n = complete_items(
                conn,
                [int(x) for x in selected_ids],
                complete_date,
                complete_gubun.strip() or None,
                user["login_id"],
            )
            st.success(f"{n}건 완료 처리 (이력 보존, 재고에서만 제외)")
            st.rerun()
else:
    with edit_col, st.container(border=True, key='inventory_edit_card'):
        st.markdown('### :material/edit: 정보 수정')
        st.caption('수정 권한이 필요합니다.')
    with complete_col, st.container(border=True, key='inventory_complete_card'):
        st.markdown('### :material/task_alt: 완료 처리')
        st.caption('수정 권한이 필요합니다.')


