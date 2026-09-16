"""Administrator-only portable backups and validated, transactional DB restore."""
import hashlib
import io
import json
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from threading import RLock
from contextlib import closing

from app.db import ensure_schema

LOCK = RLock()
MAX_BYTES = 200 * 1024 * 1024
MAX_EXPANDED = 512 * 1024 * 1024
TABLES = {'rework_items','settings','managers','site_flags','users','upload_logs',
          'import_batches','password_resets','login_sessions','deleted_item_logs','sqlite_sequence'}
README = '''재작업 대시보드 전체 백업 / 형식 1
data/rework.db: 사용자, 비밀번호 해시, 승인/권한, 업무 데이터, 설정 및 이력
data/raw/: 서버에 남아 있는 업로드 원본
manifest.json: 생성 시각, 건수, 파일 SHA-256
로그인 세션과 비밀번호 재설정 코드는 제외합니다. 개인 API 키는 포함하지 않습니다.
백업은 암호화되지 않습니다. 회사 승인 사용자만 접근 가능한 PC 폴더에 보관하고 GitHub에 올리지 마세요.

복원: 같은 버전 또는 호환되는 앱의 설정 > 전체 백업 및 복원에서 ZIP을 선택하세요.
초기화된 서버에서는 먼저 임시 관리자 계정을 만들어 로그인해야 합니다.
검증 결과 확인 > 현재 상태를 별도 백업하여 PC에 저장 > 관리자 비밀번호 입력 > 교체 확인 > 복원 실행.
복원 후 임시 계정 대신 백업에 있는 승인된 관리자 계정으로 로그인하세요.
DB 전체를 교체하므로 백업 시점 이후 가입/수정 내역은 사라집니다. 병합 기능이 아닙니다.
원본 파일은 백업 파일로 복원하며 서버에만 있는 추가 원본 파일은 삭제하지 않습니다.
복원 중 다른 사용자의 작업을 중단시키세요. 유지보수 시간에 실행해야 합니다.
사라진 서버 파일은 백업에 포함될 수 없습니다. 수동 백업은 영구 DB를 대체하지 않습니다.
'''


def authorize(conn, user_id, password=None):
    row = conn.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
    if row is None or row['role'] != '관리자' or not row['approved']:
        raise PermissionError('승인된 관리자만 백업·복원할 수 있습니다.')
    if password is not None:
        import bcrypt
        try:
            valid = bcrypt.checkpw(password.encode(), row['password_hash'].encode())
        except (ValueError, TypeError):
            valid = False
        if not valid:
            raise PermissionError('현재 관리자 비밀번호가 올바르지 않습니다.')


def clear_sessions(conn):
    for table in ('login_sessions', 'password_resets'):
        if conn.execute('SELECT 1 FROM sqlite_master WHERE type=? AND name=?', ('table',table)).fetchone():
            conn.execute(f'DELETE FROM {table}')
    conn.commit()


def summary(conn):
    return {key: conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
            for key,table in [('사용자','users'),('업무 항목','rework_items'),('담당자','managers')]}


def build_backup(conn, user_id, raw_dir):
    authorize(conn, user_id)
    with LOCK, tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp)/'rework.db'
        with closing(sqlite3.connect(path)) as dest:
            conn.backup(dest)
            clear_sessions(dest)
            counts = summary(dest)
        files = {'data/rework.db': path.read_bytes()}
        root = Path(raw_dir).resolve()
        for p in sorted(root.rglob('*')) if root.exists() else []:
            if p.is_symlink() or not p.is_file() or not p.resolve().is_relative_to(root):
                continue
            files['data/raw/'+p.relative_to(root).as_posix()] = p.read_bytes()
            if sum(map(len,files.values())) > MAX_EXPANDED:
                raise ValueError('백업 원본이 512MB를 넘습니다. 운영 관리자에게 별도 백업을 요청하세요.')
        if len(files)>5000 or sum(map(len,files.values()))>MAX_EXPANDED:
            raise ValueError('지원 백업 크기 또는 파일 수를 초과했습니다.')
        manifest = dict(format='rework-dashboard-backup',version=1,
                        created_at=datetime.now(timezone.utc).isoformat(), counts=counts,
                        raw_files=len(files)-1, files={k:hashlib.sha256(v).hexdigest() for k,v in files.items()})
        data=io.BytesIO()
        with zipfile.ZipFile(data,'w',zipfile.ZIP_DEFLATED) as z:
            for name,body in files.items(): z.writestr(name,body)
            z.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
            z.writestr('복원안내.txt',README)
        if data.tell()>MAX_BYTES: raise ValueError('ZIP이 200MB를 초과하여 화면 복원을 지원하지 않습니다.')
        return data.getvalue()


def unpack_checked(data, directory):
    if len(data)>MAX_BYTES: raise ValueError('ZIP은 200MB 이하만 지원합니다.')
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            items=z.infolist(); names=[i.filename for i in items]
            if len(items)>5002 or sum(i.file_size for i in items)>MAX_EXPANDED:
                raise ValueError('지원 백업 크기 또는 파일 수를 초과했습니다.')
            if len(set(n.casefold() for n in names))!=len(names): raise ValueError('중복 파일이 있는 ZIP입니다.')
            for n in names:
                p=PurePosixPath(n)
                if p.is_absolute() or '..' in p.parts or '\\' in n or ':' in n:
                    raise ValueError('안전하지 않은 파일 경로입니다.')
                if n not in ('manifest.json','복원안내.txt','data/rework.db') and not n.startswith('data/raw/'):
                    raise ValueError('백업 대상 외 파일이 포함되어 있습니다.')
            manifest=json.loads(z.read('manifest.json'))
            if manifest.get('format')!='rework-dashboard-backup' or manifest.get('version')!=1:
                raise ValueError('지원하지 않는 백업 형식입니다.')
            files=manifest['files']
            if not isinstance(files,dict) or 'data/rework.db' not in files:
                raise ValueError('DB 정보가 없습니다.')
            if set(files)!=set(names)-{'manifest.json','복원안내.txt'}:
                raise ValueError('파일 목록이 일치하지 않습니다.')
            for n,checksum in files.items():
                body=z.read(n)
                if hashlib.sha256(body).hexdigest()!=checksum: raise ValueError('손상되거나 변경된 백업 파일입니다.')
                target=Path(directory)/n
                target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(body)
            return manifest
    except (zipfile.BadZipFile,KeyError,TypeError,UnicodeError,json.JSONDecodeError,RuntimeError) as exc:
        raise ValueError('올바른 대시보드 백업 ZIP이 아닙니다.') from None


def validate_db(path):
    db=sqlite3.connect(path);db.row_factory=sqlite3.Row
    try:
        db.execute('PRAGMA trusted_schema=OFF')
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok': raise ValueError('DB 무결성 검사에 실패했습니다.')
        schema=db.execute("SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchall()
        if any(r['type'] not in ('table','index') or (r['type']=='table' and r['name'] not in TABLES) for r in schema):
            raise ValueError('지원하지 않는 DB 구조입니다.')
        required={'users':{'id','name','login_id','password_hash','role','approved','email','permissions'},
                  'rework_items':{'id','category','입고일','재작업일','완료수량','투입공수'},
                  'settings':{'key','value'},'managers':{'id','name','team'}}
        for table,fields in required.items():
            if not fields.issubset({r['name'] for r in db.execute(f'PRAGMA table_info({table})')}):
                raise ValueError('필수 데이터 구조가 없거나 호환되지 않습니다.')
        with closing(sqlite3.connect(':memory:')) as reference:
            reference.row_factory=sqlite3.Row
            ensure_schema(reference)
            for row in reference.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
                table=row['name']
                expected={r['name'] for r in reference.execute(f'PRAGMA table_info({table})')}
                actual={r['name'] for r in db.execute(f'PRAGMA table_info({table})')}
                if not expected.issubset(actual):
                    raise ValueError('현재 앱과 호환되지 않는 DB 구조입니다.')
        if db.execute('PRAGMA foreign_key_check').fetchone(): raise ValueError('DB 참조 검사에 실패했습니다.')
        if not db.execute("SELECT 1 FROM users WHERE role='관리자' AND approved=1").fetchone():
            raise ValueError('백업에 승인된 관리자가 없어 복원할 수 없습니다.')
        return summary(db)
    except sqlite3.DatabaseError:
        raise ValueError('백업 DB를 읽을 수 없습니다.') from None
    finally: db.close()


def inspect_backup(conn,user_id,data):
    authorize(conn,user_id)
    with tempfile.TemporaryDirectory() as tmp:
        meta=unpack_checked(data,tmp)
        meta['counts']=validate_db(Path(tmp)/'data/rework.db')
        return meta


def restore_backup(conn,user_id,password,data,raw_dir):
    authorize(conn,user_id,password)
    with LOCK, tempfile.TemporaryDirectory() as tmp:
        meta=unpack_checked(data,tmp)
        path=Path(tmp)/'data/rework.db';validate_db(path)
        root=Path(raw_dir).resolve();root.mkdir(parents=True,exist_ok=True)
        originals=[]
        try:
            # Prepare original files first; failures leave the live DB untouched.
            for name in meta['files']:
                if not name.startswith('data/raw/'): continue
                target=root/Path(name).relative_to('data/raw')
                if target.is_symlink() or not target.resolve().is_relative_to(root):
                    raise ValueError('복원 대상 경로가 안전하지 않습니다.')
                previous=target.read_bytes() if target.exists() else None
                originals.append((target,previous))
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes((Path(tmp)/name).read_bytes())
            authorize(conn,user_id,password)
            with closing(sqlite3.connect(path)) as source:
                clear_sessions(source)
                # SQLite backup replaces the destination in one DB transaction.
                source.backup(conn)
        except Exception:
            for target,previous in reversed(originals):
                if previous is None: target.unlink(missing_ok=True)
                else: target.write_bytes(previous)
            raise
        return meta
