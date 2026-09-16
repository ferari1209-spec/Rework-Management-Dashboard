"""완료일 또는 마스터 완료수량으로 완료 판정. 공수는 판정에 사용하지 않는다."""
import pandas as pd


def is_completed(row) -> bool:
    work_date = pd.to_datetime(row.get('재작업일'), errors='coerce')
    quantity = pd.to_numeric(row.get('완료수량'), errors='coerce')
    return bool(pd.notna(work_date) or (pd.notna(quantity) and quantity > 0))
