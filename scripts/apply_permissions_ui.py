from pathlib import Path
root = Path(__file__).resolve().parents[1]
p=root/'app/main.py'
s=p.read_text(encoding='utf-8')
a=s.index('if user["role"] == "관리자" or')
b=s.index('if user["role"] == "관리자":',a)
s=s[:a]+'''from app.services.permissions import allowed
for menu, path, title in [('upload','2_업로드_검수.py','업로드·검수'),('inventory','3_재고현황.py','재고현황'),('history','4_완료이력.py','완료이력'),('cost','5_비용리포트.py','비용리포트'),('master','7_마스터다운로드.py','마스터 다운로드')]:
    if allowed(user, menu):
        pages.append(st.Page('pages/'+path,title=title))
'''+s[b:]
p.write_text(s,encoding='utf-8')
for name,menu in [('2_업로드_검수.py','upload'),('3_재고현황.py','inventory'),('4_완료이력.py','history'),('5_비용리포트.py','cost'),('7_마스터다운로드.py','master')]:
 p=root/'app/pages'/name
 s=p.read_text(encoding='utf-8')
 s=s.replace('render_header()','from app.auth import require_menu, has_permission\nrequire_menu('+repr(menu)+')\nrender_header()',1)
 if menu=='upload':
  a=s.index('if not can_upload():');b=s.index("st.subheader",a)
  s=s[:a]+s[b:]
  s=s.replace("upload = st.file_uploader", "if not can_upload():\n    st.info('조회 전용입니다. 업로드·검수 실행 권한은 관리자에게 요청하세요.')\n    st.stop()\nupload = st.file_uploader")
 if menu=='inventory':
  s=s.replace('selected_download(selected,', "selected_download(selected,",1)
  a=s.index('st.download_button(')
  s=s[:a]+"if has_permission('inventory','download'):\n"+'\n'.join('    '+line for line in s[a:].splitlines())+'\n'
 if menu=='cost':
  s=s.replace('if st.button("리포트 생성 및 다운로드", type="primary"):', 'if has_permission("cost","download") and st.button("리포트 생성 및 다운로드", type="primary"):')
 if menu=='master':
  s=s.replace('data = build_master_xlsx', "if not has_permission('master','download'):\n    st.info('조회 전용 계정입니다. 다운로드 권한은 관리자에게 요청하세요.')\n    st.stop()\ndata = build_master_xlsx")
 s=s.replace('selected_download(selected,',f"selected_download(selected,")
 # 공통 다운로드 함수의 메뉴 인자
 lines=s.splitlines()
 for i,line in enumerate(lines):
  if 'selected_download(selected,' in line:
   lines[i]=line[:-1]+f", menu='{menu}')"
 p.write_text('\n'.join(lines)+'\n',encoding='utf-8')
p=root/'app/pages/6_설정.py';s=p.read_text(encoding='utf-8')
a=s.index('st.subheader("역할 / 업로드 권한")');b=s.index("st.subheader('비밀번호",a)
s=s[:a]+'''st.subheader("사용자별 역할 / 메뉴 권한")
from app.services.permissions import MENUS, allowed
all_users = [dict(r) for r in conn.execute('SELECT * FROM users ORDER BY name')]
labels = {r['id']:f"{r['name']} · {r['email'] or r['login_id']}" for r in all_users}
uid = st.selectbox('권한 설정 대상',list(labels),format_func=labels.get)
target_user = next(r for r in all_users if r['id']==uid)
roles = ['관리자','담당자','일반']
role = st.selectbox('역할',roles,index=roles.index(target_user['role']),key=f'role_{uid}')
reset_defaults = st.checkbox('역할 기본값 적용 (기존 개별 권한 초기화)',key=f'defaults_{uid}')
st.caption('관리자: 모든 권한 · 담당자: 조회 및 다운로드 · 일반: 조회만. 개별 권한으로 변경할 수 있습니다.')
base = dict(target_user)
base['role'] = role
if reset_defaults or role != target_user['role']:
    base.update(permissions='{}',can_upload=0)
rows = [{'메뉴':label,'조회':allowed(base,key),'다운로드':allowed(base,key,'download'),'등록·수정·삭제':allowed(base,key,'edit') if key in ('upload','inventory') else False} for key,label in MENUS.items()]
permission_table = st.data_editor(pd.DataFrame(rows),hide_index=True,disabled=True if role=='관리자' else ['메뉴'],key=f'permissions_{uid}_{role}_{reset_defaults}')
st.caption('등록·수정·삭제는 업로드·검수 및 재고현황에 적용됩니다. 조회를 해제하면 해당 메뉴의 모든 작업이 제한됩니다.')
if st.button('권한 저장'):
    if target_user['role']=='관리자' and role!='관리자' and conn.execute("SELECT COUNT(*) FROM users WHERE role='관리자' AND approved=1").fetchone()[0]<=1:
        st.error('최소 한 명의 승인된 관리자가 필요합니다.')
    else:
        permissions = {key:{'view':bool(row['조회']),'download':bool(row['다운로드']),'edit':bool(row['등록·수정·삭제']) if key in ('upload','inventory') else False} for key,row in zip(MENUS,permission_table.to_dict('records'))}
        conn.execute('UPDATE users SET role=?,permissions=?,can_upload=? WHERE id=?',(role,json.dumps(permissions,ensure_ascii=False),int(permissions['upload']['edit']),uid))
        conn.commit()
        st.success('권한을 저장했습니다. 다음 화면 실행부터 적용됩니다.')

'''+s[b:];p.write_text(s,encoding='utf-8')
