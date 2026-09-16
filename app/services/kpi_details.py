"""전월 말 재고 재구성 및 상세 엑셀 출력."""
from io import BytesIO
import pandas as pd


def previous_inventory(df, month, threshold, excluded):
    cutoff = month.start_time - pd.Timedelta(days=1)
    inbound = pd.to_datetime(df['입고일'], errors='coerce')
    done = pd.to_datetime(df['재작업일'], errors='coerce')
    quantity = pd.to_numeric(df['완료수량'], errors='coerce').fillna(0)
    eligible = ~df['구분'].astype(str).isin(excluded) & df['status'].ne('검수대기')
    unknown = eligible & (inbound.isna() | (inbound.le(cutoff) & done.isna() & quantity.gt(0)))
    mask = eligible & inbound.le(cutoff) & (done.gt(cutoff) | (done.isna() & quantity.le(0)))
    inventory = df.loc[mask].copy()
    long_term = df.loc[mask & (cutoff-inbound).dt.days.ge(threshold)].copy()
    return inventory, long_term, int(unknown.sum())


def detail_frame(df):
    columns = ['id','담당자','담당팀','site','품목분류','모델명','serial','입고일','재작업일','입고수량','완료수량','구분','재작업내용','status']
    return df[[c for c in columns if c in df]].rename(columns={'id':'관리번호','site':'SITE','serial':'시리얼','status':'현재 상태'})


def detail_excel(current, previous, note):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for name, frame in [('현재 상세', detail_frame(current)), ('전월 상세', detail_frame(previous)), ('집계 기준', pd.DataFrame({'안내':[note]}))]:
            frame.to_excel(writer, sheet_name=name, index=False)
            sheet = writer.sheets[name]
            sheet.freeze_panes = 'A2'
            sheet.auto_filter.ref = sheet.dimensions
            for row in sheet:
                for cell in row:
                    if cell.data_type == 'f':
                        cell.data_type = 's'
            for column in sheet.columns:
                sheet.column_dimensions[column[0].column_letter].width = 22
    return output.getvalue()
