import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd
from app.migration.migrate_master import load_category
from app.db import get_connection
for category,pattern in [('완제품','*완제품*Master.xls'),('대여','*대여*Master.xls')]:
    df,_=load_category(next(Path('.').glob(pattern)),category)
    mask=pd.to_numeric(df['완료수량'],errors='coerce').fillna(0).gt(0) & pd.to_datetime(df['재작업일'],errors='coerce').isna()
    print(category,'완료수량 있음/완료일 없음',int(mask.sum()),'수량 조합',df.loc[mask,['입고수량','완료수량']].value_counts().to_dict())
with get_connection() as conn:
    print('DB', [dict(r) for r in conn.execute("SELECT category,COUNT(*) AS n FROM rework_items WHERE status='확정' AND 완료수량>0 AND 재작업일 IS NULL GROUP BY category")])
