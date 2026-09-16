"""읽기 전용 분석. 네트워크 호출 없이 근거 행을 반환한다."""
from datetime import date
import pandas as pd
from app.services.permissions import allowed
from app.services.inventory import annotate_inventory
from app.services.completion import is_completed
from app.data_access import fetch_items


def analyze(conn, user_id, category, start, end):
    row = conn.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
    user = dict(row) if row else None
    if not all(allowed(user, menu) for menu in ('analysis','inventory','history','cost')):
        raise PermissionError('분석 및 재고현황·완료이력·비용리포트 조회 권한이 필요합니다.')
    if start > end:
        raise ValueError('시작일은 종료일보다 늦을 수 없습니다.')
    frame = fetch_items(conn,category)
    if frame.empty:
        return None
    frame = annotate_inventory(frame,conn)
    done = frame.apply(is_completed,axis=1)
    dates = pd.to_datetime(frame['재작업일'],errors='coerce')
    inbound = pd.to_datetime(frame['입고일'],errors='coerce')
    hours = pd.to_numeric(frame['투입공수'],errors='coerce')
    qty = pd.to_numeric(frame['완료수량'],errors='coerce')
    period = dates.between(pd.Timestamp(start),pd.Timestamp(end)) & done
    quality = []
    for label,mask in [('입고일 미등록',inbound.isna()),('완료일 미등록',done & dates.isna()),('완료 공수 미등록',done & hours.isna()),('완료수량 미등록/0',done & (qty.isna() | qty.le(0))),('완료일이 입고일보다 빠름',dates.lt(inbound))]:
        rows=frame.loc[mask].copy();rows['확인사항']=label;quality.append(rows)
    work=frame.loc[period & hours.notna() & hours.ge(0) & qty.gt(0)].copy()
    work['대당공수']=hours.loc[work.index]/qty.loc[work.index]
    work['모델비교키']=work['모델명'].fillna('').astype(str).str.strip()
    work['작업비교키']=work['구분'].fillna('').astype(str).str.strip()
    anomalies=[];insufficient=0
    for _,group in work.groupby(['모델비교키','작업비교키']):
        if len(group)<5 or not group.iloc[0]['모델비교키']:
            insufficient+=len(group);continue
        q1,q3=group['대당공수'].quantile([.25,.75]);spread=q3-q1
        upper=q3+1.5*spread;lower=max(0,q1-1.5*spread)
        flagged=group[(group['대당공수']>upper)|(group['대당공수']<lower)].copy()
        flagged['비교건수']=len(group);flagged['중앙대당공수']=group['대당공수'].median()
        flagged['하한']=lower;flagged['상한']=upper
        anomalies.append(flagged)
    serial=frame['serial'].fillna('').astype(str).str.strip()
    repeated=frame[serial.ne('') & serial.duplicated(keep=False)].copy()
    return dict(total=len(frame),completed=int(period.sum()),hours=float(hours[period].sum()),
        missing_hours=int((period & hours.isna()).sum()),
        inbound=int(inbound.between(pd.Timestamp(start),pd.Timestamp(end)).sum()),
        inventory=frame[frame['is_inventory']].sort_values('age_days',ascending=False,na_position='last'),
        quality=pd.concat(quality),anomalies=pd.concat(anomalies) if anomalies else work.iloc[:0],
        insufficient=insufficient,repeated=repeated,as_of=date.today().isoformat())
