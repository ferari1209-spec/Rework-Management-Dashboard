"""원본 2종을 1회 이관한다. 재실행 시 기존 데이터는 보존한다."""
import contextlib
import io
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.stdout.reconfigure(encoding='utf-8')
from app.db import DB_PATH
from app.migration.migrate_master import migrate
with contextlib.redirect_stdout(io.StringIO()):
    report=migrate(next(ROOT.glob('*완제품*Master.xls')),next(ROOT.glob('*대여*Master.xls')),DB_PATH)
summary={c:{k:v for k,v in r.items() if k not in ('sample',)} for c,r in report.items()}
if not all(r.get('skipped') for r in report.values()):
    (DB_PATH.parent/'migration_report.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False))
