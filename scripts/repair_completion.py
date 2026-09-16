"""완료수량 표시가 있는 기존 확정 행을 완료로 정정. 원본/공수/날짜 보존."""
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding='utf-8')
from app.db import get_connection, DB_PATH
from app.services.completion import is_completed

conn=get_connection()
rows=[dict(r) for r in conn.execute("SELECT * FROM rework_items WHERE status='확정'")]
targets=[r for r in rows if is_completed(r)]
if targets:
    stamp=datetime.now().strftime('%Y%m%d_%H%M%S')
    backup=DB_PATH.parent/'backups'/f'before_completion_fix_{stamp}.db'
    backup.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(backup) as dest:
        conn.backup(dest)
    with conn:
        for row in targets:
            conn.execute("UPDATE rework_items SET status='완료',updated_at=datetime('now'),updated_by='completion_rule_fix' WHERE id=? AND status='확정'",(row['id'],))
    (backup.parent/f'completion_fix_{stamp}.json').write_text(json.dumps(targets,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'corrected':len(targets),'categories':{c:sum(r['category']==c for r in targets) for c in ['완제품','대여']}},ensure_ascii=False))
conn.close()
