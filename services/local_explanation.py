"""API 호출 없이 계산 결과에만 근거하는 자동 해설."""
import pandas as pd


def explain_locally(result):
    completed = result['completed']
    missing = result['missing_hours']
    period = (f'선택 기간의 입고 기록은 {result["inbound"]:,}건, 완료 기록은 '
              f'{completed:,}건이며, 등록된 투입공수 합계는 {result["hours"]:,.2f}시간입니다. '
              '건수는 데이터 행 기준으로 제품 수량과 다릅니다. 입고와 완료가 같은 대상이라는 보장이 없어 완료율이나 재고 증감으로 해석하지 않습니다.')
    if missing:
        period += f' 완료 기록 중 {missing:,}건({missing / completed * 100:.1f}%)은 공수가 없어 합계에서 제외되었습니다. 실제 작업 공수를 확인해 입력해 주세요.'
    elif not completed:
        period += ' 이 기간에 완료일이 등록된 완료 기록이 없습니다. 기간과 완료일 미등록 내역을 확인해 주세요.'
    else:
        period += ' 기간 내 완료 기록의 공수 미등록은 없습니다.'

    inventory = result['inventory']
    ages = pd.to_numeric(inventory.get('age_days', pd.Series(dtype=float)), errors='coerce')
    stock = f'현재 재고 기록은 {len(inventory):,}건입니다.'
    if not inventory.empty:
        valid = ages[ages.ge(0)]
        if not valid.empty:
            stock += f' 입고일 경과가 가장 긴 항목은 {int(valid.max()):,}일입니다. 재고 우선 확인 탭에서 경과일이 긴 항목의 처리 계획을 확인해 주세요.'
        if ages.isna().any():
            stock += f' 입고일을 확인할 수 없는 {int(ages.isna().sum()):,}건은 경과일 판단 전에 날짜 보완이 필요합니다.'
        if ages.lt(0).any():
            stock += f' 입고일이 미래인 {int(ages.lt(0).sum()):,}건은 날짜가 정확한지 확인해 주세요.'

    count = len(result['anomalies'])
    anomaly = (f'선택 기간에 동일 모델·구분 대비 대당공수가 통계 범위를 벗어난 후보는 {count:,}건입니다. '
               '공수 이상 후보 탭에서 투입공수·완료수량과 실제 작업 난이도를 비교해 주세요. 오류나 비효율로 확정한 결과는 아닙니다.'
               if count else '선택 기간의 비교 가능한 그룹에서 공수 이상 후보가 발견되지 않았습니다. 모든 기록의 정상 여부를 보장하는 결과는 아닙니다.')
    anomaly += f' 비교 자료가 부족하거나 모델명이 없는 {result["insufficient"]:,}건은 통계 비교에서 제외되었습니다. 공수·완료수량 조건을 만족하지 않는 행도 비교 대상이 아닙니다.'

    quality = result['quality']
    checks = quality['확인사항'].value_counts() if '확인사항' in quality else pd.Series(dtype=int)
    data = f'현재 전체 데이터의 품질 확인사항은 {len(quality):,}개입니다. 한 기록에 여러 확인사항이 있을 수 있습니다.'
    if not checks.empty:
        data += ' ' + ', '.join(f'{label} {n:,}건' for label, n in checks.items()) + '. 데이터 품질 탭에서 원본과 대조해 주세요.'
    data += f' 같은 시리얼의 반복 기록은 {len(result["repeated"]):,}행입니다. 실제 반복 작업인지 중복 입력인지 확인한 후 처리해 주세요.'
    return [('기간 내 입고·완료 및 공수', period), ('현재 재고 확인', stock),
            ('공수 이상 후보 해설', anomaly), ('전체 데이터 품질 확인', data)]
