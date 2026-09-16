"""ERP 및 마스터 양식을 읽고 전체 업무 항목을 검수 화면에 보존한다."""
from pathlib import Path
import pandas as pd
from app.excel_io import excel_sheet_names, read_xls_sheet, read_xlsx_sheet
from app.migration.mapping_config import COLUMN_MAPPING
from app.migration.migrate_master import INSERT_COLUMNS, cut_trailing_empty_rows, is_fully_empty_row
from app.services.parsing import split_remark
from app.services.import_service import clean, review_rows


def normalize(name):
    return str(name).replace('\r', '').replace('\n', '').replace(' ', '').strip()


def detect_and_parse(path: Path, category: str, conn) -> tuple[pd.DataFrame, str]:
    names = excel_sheet_names(path)
    cfg = COLUMN_MAPPING[category]
    read = read_xls_sheet if path.suffix.lower() == '.xls' else read_xlsx_sheet
    master_names = {c['sheet_name'] for c in COLUMN_MAPPING.values()}
    if master_names.intersection(names) and cfg['sheet_name'] not in names:
        raise ValueError('선택한 카테고리와 마스터 시트가 다릅니다.')
    kind = 'master' if cfg['sheet_name'] in names else 'erp'
    sheet = cfg['sheet_name'] if kind == 'master' else names[0]
    if kind == 'master':
        df = read(path, sheet, header_row=cfg['header_row'])
    else:
        df = None
        for header in range(10):
            candidate = read(path, sheet, header_row=header)
            cols = {normalize(c) for c in candidate.columns}
            if ('품목' in cols or '모델명' in cols) and '비고' in cols:
                df = candidate
                break
        if df is None:
            raise ValueError('지원하는 입고 장표가 아닙니다. 품목(모델명), 입고수량, 비고 열이 필요합니다.')
    aliases = {normalize(k): v for k, v in cfg['columns'].items() if v}
    aliases.update({'품목': '모델명', '시리얼번호': 'serial', 'SITE': 'site'})
    work = cut_trailing_empty_rows(df).rename(columns={c: aliases.get(normalize(c), normalize(c)) for c in df.columns})
    records = []
    for row in work.to_dict('records'):
        rec = {c: clean(row.get(c)) for c in INSERT_COLUMNS if c not in ('category','status')}
        if is_fully_empty_row(pd.Series({k:v for k,v in rec.items() if k != 'source_no'})):
            continue
        if kind == 'erp':
            parsed = split_remark(rec.get('비고_원문'))
            for col in ('site','담당자','serial'):
                rec[col] = rec.get(col) or parsed[col]
        records.append(rec)
    return review_rows(pd.DataFrame(records), conn), kind
