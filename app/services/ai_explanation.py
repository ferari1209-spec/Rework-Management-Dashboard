"""Optional personal-key explanations; no keys, rows or responses are persisted."""
import json
import urllib.request
import urllib.error

FOCUSES = ('종합 해설', '공수 이상 원인 가설', '재고 관리 개선 제안', '데이터 품질 개선 제안')


def aggregate_summary(result, start, end):
    # Explicit allowlist: never include raw records or free-text identifiers.
    return {
        '기간': f'{start} ~ {end}', '전체기준일': result['as_of'],
        '기간내입고건수': int(result['inbound']),
        '기간내완료건수': int(result['completed']),
        '기간내투입공수_시간': round(float(result['hours']), 2),
        '기간내완료공수미등록건수': int(result['missing_hours']),
        '현재재고행수': len(result['inventory']),
        '전체데이터품질확인사항수_행중복포함': len(result['quality']),
        '기간내공수이상후보건수': len(result['anomalies']),
        '기간내비교자료부족건수': int(result['insufficient']),
        '전체반복시리얼해당행수': len(result['repeated']),
    }


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def explain(api_key, summary, focus):
    key = api_key.strip()
    if not key or not key.isascii() or any(c.isspace() for c in key):
        raise ValueError('올바른 OpenAI API 키를 입력해 주세요.')
    if focus not in FOCUSES:
        raise ValueError('분석 관점을 선택해 주세요.')
    payload = {
        'model': 'gpt-4.1-mini', 'store': False, 'max_output_tokens': 1800,
        'instructions': (
            '재작업 관리 분석가로서 한국어로 답하라. 제공된 집계만 근거로 활용하라. '
            '확인된 사실, 원인 가설, 확인할 사항, 실행 제안을 구분하라. '
            '행 건수와 제품 수량을 혼동하지 말고 기간 집계와 현재 전체 집계를 구분하라. '
            '품질 확인사항은 중복 포함이다. 이상 후보는 동일 모델 및 구분 5건 이상에서 '
            '대당공수 IQR 1.5배 밖이며 오류 확정이 아니다. 비교 기간, 원문, '
            '개별 모델별 수치가 없으므로 추세나 개별 원인을 확정하지 마라. '
            '없는 수치를 만들거나 외부 정보를 조회하지 마라.'),
        'input': focus + '\n' + json.dumps(summary, ensure_ascii=False, allow_nan=False),
    }
    request = urllib.request.Request('https://api.openai.com/v1/responses',
        data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=45) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        messages = {401: 'API 키가 유효하지 않습니다.', 403: '해당 키에 모델 사용 권한이 없습니다.',
                    429: 'API 사용 한도 또는 잔액을 확인하고 잠시 후 다시 시도해 주세요.'}
        raise ValueError(messages.get(exc.code, 'AI 서비스 요청에 실패했습니다. 잠시 후 다시 시도해 주세요.')) from None
    except (OSError, ValueError):
        raise ValueError('AI 서비스 연결 또는 응답을 확인할 수 없습니다. 잠시 후 다시 시도해 주세요.') from None
    if not isinstance(data, dict) or data.get('status') != 'completed':
        raise ValueError('AI 답변이 완료되지 않았습니다. 다시 실행해 주세요.')
    text = '\n'.join(part.get('text', '') for item in data.get('output', [])
                     if item.get('type') == 'message' for part in item.get('content', [])
                     if part.get('type') == 'output_text').strip()
    if not text:
        raise ValueError('AI가 분석 답변을 반환하지 않았습니다.')
    return text
