"""Conservative row matching for cumulative master uploads."""
from app.migration.migrate_master import INSERT_COLUMNS
from app.services.completion import is_completed


def plan_master(existing, incoming):
    actions=[]; used=set(); numbers=set()
    def text(v): return str(v).strip() if v is not None else ''
    for n,rec in enumerate(incoming,1):
        no=rec['source_no']
        if no is not None:
            if no in numbers: raise ValueError(f'{n}행: 업로드 파일 안에 같은 원본 번호 {no:g}가 여러 번 있습니다.')
            numbers.add(no)
        numbered=[r for r in existing if no is not None and r['source_no']==no]
        key=('serial','모델명','입고일')
        exact=[r for r in existing if all(text(rec[k]) and text(rec[k])==text(r[k]) for k in key)]
        if len(numbered)>1:
            candidates=[r for r in numbered if r in exact]
        else: candidates=numbered or exact
        if len(candidates)>1 or (len(numbered)>1 and not candidates):
            raise ValueError(f'{n}행: 기존 중복 항목으로 대상을 결정할 수 없습니다. 원본 번호·시리얼을 확인하세요.')
        if not candidates:
            actions.append(('신규',None,rec));continue
        old=candidates[0]
        if old['id'] in used:
            raise ValueError(f'{n}행: 여러 업로드 행이 같은 기존 항목을 가리킵니다. 중복 행을 확인하세요.')
        used.add(old['id'])
        if numbered and any(text(old[k]) and text(rec[k]) and text(old[k])!=text(rec[k]) for k in key):
            raise ValueError(f'{n}행: 원본 번호는 같지만 시리얼·모델명·입고일이 다릅니다. 다른 작업인지 확인 후 해당 항목은 재고현황에서 수정하세요.')
        if old['status']=='검수대기':
            raise ValueError(f'{n}행: 기존 검수대기 항목과 일치합니다. 해당 항목을 먼저 검수하세요.')
        merged={k:rec[k] if rec[k] is not None else old[k] for k in INSERT_COLUMNS}
        # A partial/older master must not silently undo an existing completion.
        if is_completed(old) and not is_completed(merged):
            raise ValueError(f'{n}행: 기존 완료 항목을 미완료로 되돌리는 값입니다. 완료수량을 확인하세요.')
        merged['status']='완료' if is_completed(merged) else '확정'
        changed=any(merged[k]!=old[k] for k in INSERT_COLUMNS)
        actions.append(('변경' if changed else '동일',old['id'],merged))
    return actions
