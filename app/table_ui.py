"""부분 검색과 행 선택을 제공하는 공통 테이블 UI."""
from io import BytesIO
import hashlib
import pandas as pd
import streamlit as st


def partial_filter(frame, query):
    query = query.strip()
    if not query or frame.empty:
        return frame
    matches = frame.fillna('').astype(str).apply(lambda col: col.str.contains(query, case=False, regex=False))
    return frame.loc[matches.any(axis=1)]


def search_table(frame, key, count_label=None, toolbar_action=None):
    with st.container(horizontal=True, vertical_alignment='bottom', gap='small'):
        select_all = st.button('전체 선택', key=f'{key}_all', disabled=frame.empty, icon=':material/select_all:')
        clear_all = st.button('전체 해제', key=f'{key}_none', disabled=frame.empty, icon=':material/deselect:')
        st.caption('현재 검색·필터 결과에 적용')
        query = st.text_input('부분값 검색', key=key, placeholder='이름·모델·SITE 등 일부 입력', width=380, icon=':material/search:')
        result = partial_filter(frame, query).copy()
        if count_label:
            st.caption(f'{count_label}: {len(result):,}　 ·　 표시 행 수: {len(result):,}')
        else:
            st.caption(f'표시 행 수: {len(result):,}')
        if toolbar_action is not None:
            toolbar_action(result)
    result.attrs['selection_toolbar'] = (select_all, clear_all)
    return result


def selectable_table(frame, key, editable_columns=(), column_config=None):
    data = frame.copy()
    data.insert(0, '선택', False)
    # 조회 결과가 달라지면 이전 행 위치에 있던 체크/편집 상태를 재사용하지 않는다.
    signature = hashlib.sha256(pd.util.hash_pandas_object(frame.astype(str), index=True).values.tobytes()).hexdigest()[:16]
    state_key = f'{key}_selection_state'
    state = st.session_state.get(state_key)
    if state is None or state['signature'] != signature:
        state = {'signature': signature, 'base': data, 'latest': data, 'revision': 0}
        st.session_state[state_key] = state
    if 'selection_toolbar' in frame.attrs:
        select_all, clear_all = frame.attrs['selection_toolbar']
    else:
        with st.container(horizontal=True, vertical_alignment='center', gap='small'):
            select_all = st.button('전체 선택', key=f'{key}_select_all', disabled=frame.empty, icon=':material/select_all:')
            clear_all = st.button('전체 해제', key=f'{key}_clear_all', disabled=frame.empty, icon=':material/deselect:')
            st.caption('현재 검색·필터 결과에 적용')
    if select_all or clear_all:
        # 저장 전 편집값을 유지하면서 체크 상태만 교체한다.
        state['base'] = state['latest'].copy()
        state['base']['선택'] = bool(select_all)
        state['revision'] += 1
    config = {'선택': st.column_config.CheckboxColumn('선택', default=False)}
    config.update(column_config or {})
    edited = st.data_editor(state['base'], hide_index=True, use_container_width=True,
        disabled=[c for c in frame.columns if c not in editable_columns],
        column_config=config, key=f"{key}_{signature}_{state['revision']}")
    state['latest'] = edited.copy()
    selected = edited.loc[edited['선택']].drop(columns='선택')
    st.caption(f'조회 {len(frame):,}건 · 선택 {len(selected):,}건')
    return edited.drop(columns='선택'), selected


def selected_download(frame, name, menu):
    from app.auth import has_permission
    if not has_permission(menu, 'download'):
        return
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        frame.to_excel(writer, index=False, sheet_name='선택내역')
        for row in writer.sheets['선택내역']:
            for cell in row:
                if cell.data_type == 'f':
                    cell.data_type = 's'
    st.download_button('선택 항목 다운로드', output.getvalue(), file_name=f'{name}_선택.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', disabled=frame.empty, icon=':material/download:')
