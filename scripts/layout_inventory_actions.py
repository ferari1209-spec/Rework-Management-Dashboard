from pathlib import Path
p=Path(__file__).resolve().parents[1]/'app/pages/3_재고현황.py'
s=p.read_text(encoding='utf-8')
a=s.index('def to_xlsx(');b=s.index("if has_permission('inventory','download'):",a)
helper=s[a:b]
download=s[b:]
s=s[:a]
pos=s.index('edited, selected =')
s=s[:pos]+helper+"with st.container(horizontal=True, horizontal_alignment='right'):\n"+'\n'.join('    '+line for line in download.splitlines())+'\n\n'+s[pos:]
s=s.replace("selected_download(selected, f'{category}_재고현황', menu='inventory')\n",'')
pos=s.index('if editable:\n    selected_ids')
s=s[:pos]+'''manage_col, edit_col, complete_col = st.columns(3, gap='medium')
with manage_col, st.container(border=True, key='inventory_manage_card'):
    st.markdown('### :material/checklist: 선택 항목 관리')
    quantity = pd.to_numeric(selected['입고수량'], errors='coerce').fillna(0).sum() if '입고수량' in selected else 0
    st.caption(f'선택 {len(selected):,}건 · 수량 {quantity:,.0f}대')
    selected_download(selected, f'{category}_재고현황', menu='inventory')
    delete_slot = st.container()
'''+s[pos:]
a=s.index("    if 'inventory_delete_notice'");b=s.index('    new_in_date',a)
chunk=s[a:b]
s=s[:a]+'    with delete_slot:\n'+'\n'.join('    '+line for line in chunk.splitlines())+'\n'+s[b:]
a=s.index('    new_in_date');b=s.index('    complete_date',a)
chunk=s[a:b].replace('if st.button("선택 행 입고일 일괄수정",','if st.button("선택 행 입고일 일괄수정", disabled=not selected_ids,')
s=s[:a]+"    with edit_col, st.container(border=True, key='inventory_edit_card'):\n        st.markdown('### :material/edit: 정보 수정')\n"+'\n'.join('    '+line for line in chunk.splitlines())+'\n'+s[b:]
a=s.index('    complete_date');b=s.index('\nelse:',a)
chunk=s[a:b].replace('if st.button("선택 행 완료 처리",','if st.button("선택 행 완료 처리", disabled=not selected_ids,')
s=s[:a]+"    with complete_col, st.container(border=True, key='inventory_complete_card'):\n        st.markdown('### :material/task_alt: 완료 처리')\n"+'\n'.join('    '+line for line in chunk.splitlines())+s[b:]
s=s.replace('else:\n    st.caption("일반 계정은 조회만 가능합니다.")', '''else:
    with edit_col, st.container(border=True, key='inventory_edit_card'):
        st.markdown('### :material/edit: 정보 수정')
        st.caption('수정 권한이 필요합니다.')
    with complete_col, st.container(border=True, key='inventory_complete_card'):
        st.markdown('### :material/task_alt: 완료 처리')
        st.caption('수정 권한이 필요합니다.')''')
p.write_text(s,encoding='utf-8')
