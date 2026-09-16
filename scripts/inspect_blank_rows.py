import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding='utf-8')
from app.migration.migrate_master import load_category
for c,p in [('완제품','*완제품*Master.xls'),('대여','*대여*Master.xls')]:
    df,_=load_category(next(Path('.').glob(p)),c)
    missing=df[df['모델명'].isna()]
    print(c, missing.notna().sum().to_dict())
    print(missing.head(2).to_dict('records'))
