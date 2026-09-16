from pathlib import Path
p=Path(__file__).resolve().parents[1]/'app/pages/6_설정.py'
s=p.read_text(encoding='utf-8')
def indent(block): return '\n'.join('    '+line if line else '' for line in block.rstrip().splitlines())+'\n'
# 팝업 정의는 카드 밖에 유지한다.
dialogs=[]
for marker,end in [("@st.dialog('선택 항목 삭제 확인')","if st.button('선택 담당자 삭제'"),("@st.dialog('선택 사용자 수정')","if 'user_edit_notice'")]:
 a=s.index(marker);b=s.index(end,a);dialogs.append(s[a:b]);s=s[:a]+s[b:]
start=s.index('st.subheader("담당자명 목록")')
prefix=s[:start]+''.join(dialogs)
rest=s[start:]
a=rest.index('st.subheader("사용자 승인")');b=rest.index('st.subheader("사용자별 역할 / 메뉴 권한")');c=rest.index("st.subheader('비밀번호 재설정 코드 발급')")
manager=rest[:a];users=rest[a:b];permissions=rest[b:c];reset=rest[c:]
a=manager.index("with st.form('add_manager'):");b=manager.index('if st.button("담당자 목록 저장"',a)
addition=manager[a:b];manager=manager[:a]+manager[b:]
manager=manager.replace('st.subheader("담당자명 목록")',"st.markdown('### :material/groups: 담당자명 목록')")
addition="st.markdown('### :material/person_add: 담당자 추가')\nst.caption('목록에서 이름·담당팀을 직접 수정한 뒤 저장할 수 있습니다.')\n"+addition.replace("st.form('add_manager')","st.form('add_manager', border=False)")
# 선택 작업 버튼을 같은 줄에 모으고 기존 중복 승인 UI 제거
users=users.replace('st.subheader("사용자 승인")',"st.markdown('### :material/verified_user: 사용자 승인')")
a=users.index('pending_ids =');users=users[:a]
users=users.replace("if st.button('선택 사용자 삭제',", "if user_actions.button('선택 사용자 삭제',").replace("if st.button('선택 사용자 승인',", "if user_actions.button('선택 사용자 승인',").replace("if st.button('선택 사용자 수정',", "if user_actions.button('선택 사용자 수정',")
users=users.replace("_, user_selected = selectable_table(users, 'settings_users')", "_, user_selected = selectable_table(users, 'settings_users')\nuser_actions = st.container(horizontal=True, gap='small')")
permissions=permissions.replace('st.subheader("사용자별 역할 / 메뉴 권한")',"st.markdown('### :material/admin_panel_settings: 사용자별 역할 / 메뉴 권한')")
reset=reset.replace("st.subheader('비밀번호 재설정 코드 발급')","st.markdown('### :material/key: 비밀번호 재설정')").replace("st.form('admin_reset_issue')","st.form('admin_reset_issue', border=False)")
s=prefix+"manager_list_col, manager_add_col = st.columns([3,1], gap='medium')\nwith manager_list_col, st.container(border=True, key='settings_manager_list'):\n"+indent(manager)+"with manager_add_col, st.container(border=True, key='settings_manager_add'):\n"+indent(addition)
s+="\nwith st.container(border=True, key='settings_user_list'):\n"+indent(users)
s+="\npermission_col, reset_col = st.columns([2,1], gap='medium')\nwith permission_col, st.container(border=True, key='settings_permissions'):\n"+indent(permissions)+"with reset_col, st.container(border=True, key='settings_reset'):\n"+indent(reset)
p.write_text(s,encoding='utf-8')
