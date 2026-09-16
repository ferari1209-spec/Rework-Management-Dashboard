from datetime import datetime
import streamlit as st
from app.auth import current_user
from app.db import RAW_DIR
from app.browser_login import queue_cookie
from app.services.backup_service import build_backup, inspect_backup, restore_backup


def render_backup_tools(conn):
    user=current_user()
    if not user or user['role']!='관리자' or not user['approved']:
        return
    with st.container(border=True):
        st.markdown('### :material/backup: 전체 백업 및 복원')
        st.caption('사용자·승인·권한·설정·업무 데이터와 서버에 보관된 업로드 원본을 백업합니다. 개인 API 키·로그인 세션·재설정 코드는 제외합니다.')
        st.warning('백업 ZIP은 암호화되지 않은 회사 데이터입니다. 접근이 제한된 PC 폴더에 보관하고 GitHub에 올리지 마세요. 수동 백업 이후의 변경은 보호되지 않습니다.')
        if st.button('전체 백업 파일 만들기',icon=':material/backup:',key='make_full_backup'):
            try:
                with st.spinner('DB와 업로드 원본을 백업하고 있습니다…'):
                    data=build_backup(conn,user['id'],RAW_DIR)
                st.download_button('전체 백업 ZIP 다운로드',data,
                    file_name=f'재작업대시보드_전체백업_{datetime.now():%Y%m%d_%H%M%S}.zip',
                    mime='application/zip',key='full_backup_download',on_click='ignore')
                st.info('다운로드 버튼을 눌러 PC에 저장하세요. 파일 생성만으로 PC에 저장되지는 않습니다. 복원 전에는 다른 사용자 작업을 중단하고 현재 상태를 별도 백업하세요.')
            except (PermissionError,ValueError,OSError) as exc:
                st.error(str(exc))
        with st.expander('백업 ZIP 업로드 및 전체 복원'):
            st.warning('복원은 병합이 아니라 DB 전체 교체입니다. 백업 시점 이후의 가입·수정 내역은 사라집니다. 모든 사용자 작업을 중단한 유지보수 시간에 실행하세요.')
            st.caption('초기화된 서버는 먼저 임시 관리자 계정으로 로그인하세요. 복원 후에는 백업에 있던 계정과 비밀번호를 사용합니다. 서버에만 남아 있는 추가 원본 파일은 삭제하지 않습니다. ZIP 200MB / 압축 해제 512MB까지 지원합니다.')
            uploaded=st.file_uploader('전체 백업 ZIP 선택',type=['zip'],key='restore_backup_zip')
            if uploaded is not None:
                data=uploaded.getvalue()
                try:
                    meta=inspect_backup(conn,user['id'],data)
                except (PermissionError,ValueError,OSError) as exc:
                    st.error(str(exc));return
                st.success('백업 파일 구성·해시·DB 검증을 통과했습니다.')
                st.write('백업 생성 시각(UTC): '+str(meta.get('created_at','미등록')))
                st.write(' · '.join(f'{k} {v:,}건' for k,v in meta['counts'].items())+f' · 원본 파일 {len(meta["files"])-1:,}개')
                st.caption('파일 해시는 손상 확인용입니다. 신뢰할 수 있는 본 시스템의 백업만 사용하세요.')
                # A different upload must receive a separate confirmation.
                import hashlib
                signature=hashlib.sha256(data).hexdigest()[:16]
                with st.form('restore_confirm_'+signature):
                    password=st.text_input('현재 로그인한 관리자 비밀번호',type='password')
                    confirmed=st.checkbox('다른 사용자 작업을 중단했고 현재 상태를 PC에 별도 백업했습니다. 백업 DB로 전체 교체하는 것에 동의합니다.')
                    phrase=st.text_input('확인 문구: 전체 복원',placeholder='전체 복원')
                    if st.form_submit_button('전체 복원 실행',type='primary'):
                        if not confirmed or phrase.strip()!='전체 복원':
                            st.error('백업·교체 확인과 확인 문구를 입력하세요.')
                        else:
                            try:
                                with st.spinner('백업 데이터 복원 중입니다. 창을 닫지 마세요…'):
                                    restore_backup(conn,user['id'],password,data,RAW_DIR)
                            except (PermissionError,ValueError,OSError) as exc:
                                st.error(str(exc))
                            else:
                                st.session_state.clear()
                                st.session_state['_logged_out']=True
                                st.session_state['_backup_restore_notice']=True
                                queue_cookie(remember_email='')
                                st.rerun()
