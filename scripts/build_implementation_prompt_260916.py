from pathlib import Path
import re
from html import escape
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/pdf'
OUT.mkdir(parents=True,exist_ok=True)
NAME='구현프롬프트 재작업대시보드 챗gpt_260916'
base=(ROOT/'outputs/요구사항명세서_재작업통합관리_20260915.md').read_text(encoding='utf-8')
base=base[base.index('## 1. 목적과 범위'):]
base=base.replace('설정으로 구성한다.', '설정, AI 분석으로 구성한다.')
base=base.replace('- AI 예측·이상탐지, ERP 직접 API 연동, 메일 자동 발송은 현행 범위에 포함하지 않는다.', '- 통계·규칙 기반 이상탐지와 개인 OpenAI API 키를 이용한 선택적 AI 해설을 제공한다. 미래 예측 모델, ERP 직접 API 연동, 메일 자동 발송은 제공하지 않는다.')
base=base.replace('사내 공동 접속·외부 공개는 별도 구성 대상이다.', '승인된 사용자의 공용 웹 접속은 외부 호스팅·도메인·HTTPS 구성이 필요한 별도 배포 대상이다. 회사 내부 서버 사용은 필수 조건이 아니다.')
base=base.replace('마스터 다운로드의 조회·다운로드 권한', '마스터 다운로드, AI 분석의 조회·다운로드 권한')
base=base.replace('삭제 데이터 복원 화면, AI 기능, ERP 직접 연동', '삭제 데이터 복원 화면, 고도화된 예측 모델, ERP 직접 연동')
base=base.replace('사내 공용 배포·HTTPS', '외부 호스팅 공용 배포·HTTPS')
base=base.replace('## 16. 문서 근거와 변경 관리', '## 16. 문서 근거와 변경 관리')
intro='''# 구현프롬프트 재작업대시보드 챗gpt_260916

기준일: 2026-09-16 | 개정판: 2.0 | 대상: 개발·유지보수 담당자 및 구현 AI

## 문서 사용 방법

이 문서는 첨부된 ‘구현프롬프트_재작업대시보드.md’를 지금까지의 확정 요청과 현재 코드에 맞춰 갱신한 구현 지침이다. 신규 프로젝트를 무조건 생성하는 초기 프롬프트가 아니라, 기존 시스템을 보존하며 기능을 유지·확장하기 위한 기준으로 사용한다. PDF와 MD는 같은 본문을 제공한다.

기존 프로젝트가 있으면 먼저 코드를 확인하고 차이가 있는 부분만 수정하라. 운영 DB, 승인 계정, 원본 마스터, 저장된 설정을 초기화하거나 덮어쓰지 말라. 원본 문서에 있는 이전 요구보다 이 문서의 최신 규칙을 우선 적용하라. 별도 변경 승인이 없는 기능을 임의로 축소하지 말라. 실제 코드와 명세가 다르면 차이와 영향을 보고하고, 화면 표시만으로 완료를 주장하지 말라.

### 원본 대비 핵심 정정

- 제목: ‘AI기반’을 제외한 ‘재작업 통합 관리 대시보드’로 통일.
- 완료 판정: 재작업일 또는 완료수량 양수. 공수 누락은 완료 취소 사유가 아님.
- 이관: 연속 빈 행 3개 이후 절단 규칙 폐기. 중간 공백 뒤 유효 데이터 보존.
- 원본의 완제품 5,918행·대여 1,664행을 고정 인수 수치로 사용하지 않음. 실제 파일의 유효 업무행과 대조.
- 역할: 관리자·담당자·일반 3종과 사용자별 메뉴 권한. 이메일 가입·세션 유지·관리자 코드 재설정 추가.
- KPI: 검수대기 카드 제거, 전월 비교·증감·상세 팝업 추가.
- 표: 부분 검색, 개별/전체 선택, 선택 출력, 권한 있는 재고 삭제와 삭제 이력 추가.
- 비용 출력: 재작업현황 16열로 개정. ‘무/재작업 현황’은 원본 ‘구분’ 연결.
- 화면: 옅은 회색 바탕·입체 카드·간결한 필터·차트 수치 분리 배치로 갱신.
- AI: 외부 전송 없는 통계 분석에 개인 키 기반 선택적 AI 해설 추가.

### 기술 스택과 코드 기준

Python 3.11 이상을 기준으로 하며 현재 확인 환경은 Python 3.12이다. Streamlit, pandas, SQLite, xlrd, openpyxl, bcrypt, Plotly를 사용한다. 정확한 설치 범위는 requirements.txt를 따른다. 현재 DB는 data/rework.db이고 원본은 data/raw에 보관한다. 외부 AI 호출은 Python 표준 urllib를 사용한다.

- 진입점 및 DB: app/main.py, app/db.py, app/data_access.py.
- 계정 및 공통 화면: app/auth.py, app/ui.py, app/dashboard.css, app/table_ui.py, app/chart_labels.py.
- 화면: app/pages의 개요·업로드_검수·재고현황·완료이력·비용리포트·설정·마스터다운로드·AI분석.
- 이관: app/migration/schema.sql, mapping_config.py, migrate_master.py.
- 업무 규칙: app/services/completion.py, inventory.py, cost_report.py, settings_service.py, permissions.py.
- AI: app/services/analysis_service.py, app/services/ai_explanation.py, app/ai_ui.py.
- 검증: tests 및 scripts/check_cost_report_revision.py. 초기 설계에 적힌 models.py 생성은 필수 조건이 아니다.

'''
append='''
## 17. AI 분석과 개인 API 키

### AI-01 접근 권한과 기본 분석

AI 분석 메뉴와 재고현황·완료이력·비용리포트의 조회 권한을 모두 가진 승인 사용자만 분석한다. 매 실행 시 DB의 현재 승인·권한을 확인한다. 분석 결과 다운로드는 AI 분석 및 원본 세 메뉴의 다운로드 권한을 모두 요구한다.

카테고리, 분석 시작일, 종료일을 선택하고 ‘분석 실행’을 누른다. 기본 날짜는 이번 달 1일부터 오늘까지이다. 기간 내 입고 건수·완료 건수·공수 합계·완료 공수 미등록 건수를 계산한다. 이 화면의 건수는 행 수이며 제품 수량 합계와 구별한다. 기본 통계 실행은 외부 API를 호출하지 않는다.

### AI-02 확인 대상과 근거

- 재고 우선 확인: 현재 재고를 입고 경과일 내림차순으로 제공한다. 완료 가능일을 예측하지 않는다.
- 데이터 품질: 입고일 누락, 완료일 누락, 완료 공수 누락, 완료수량 누락 또는 0, 완료일이 입고일보다 빠른 항목을 표시한다. 한 행에 여러 문제가 있으면 중복 표시할 수 있다.
- 공수 이상 후보: 선택 기간의 완료 항목 중 유효한 0 이상 공수와 양수 완료수량을 가진 항목을 비교한다. 대당공수 = 투입공수 / 완료수량이다.
- 동일 모델명·구분 그룹이 5건 이상일 때 Q1 - 1.5×IQR 미만 또는 Q3 + 1.5×IQR 초과를 후보로 표시한다. 하한은 0 이상으로 제한한다. 비교 부족 건수를 별도 안내하고 후보를 오류로 단정하지 않는다.
- 시리얼 반복 기록: 현재 카테고리 전체에서 비어 있지 않은 같은 시리얼이 여러 번 나타나는 기록을 보여준다. 중복 입력인지 반복 재작업인지는 사람이 확인한다.
- 재고·데이터 품질·시리얼 반복은 현재 전체 데이터, 입고·완료·공수 이상은 선택 기간이라는 범위를 화면에 명시한다.

### AI-03 개인 키 입력과 안내

‘개인 API 키 · AI 기능 확장’ 영역에 비밀번호 형식의 개인 OpenAI API 키 입력란과 ‘키 지우기’를 둔다. 다른 공급사의 키를 지원한다고 표시하지 않는다.

안내 문구: “개인 OpenAI API 키를 입력하면 통계 결과 해설, 이상 원인 가설, 재고·데이터 품질 개선 제안 등 AI 기능을 더 폭넓게 사용할 수 있습니다. 키 없이도 기본 통계·이상탐지 분석을 이용할 수 있습니다.”

키는 현재 로그인 사용자 세션에서만 사용한다. DB·파일·로그·공유 캐시·다운로드에 저장하지 않는다. 로그아웃 또는 키 지우기 시 삭제하며 사용자 변경 시 이전 키·답변·전송 동의를 제거한다. 영구 저장 기능이 아니므로 세션 재연결이나 화면 이동 등에 따라 재입력이 필요할 수 있음을 안내한다.

### AI-04 외부 전송과 실행

- 기본 분석 결과에서 종합 해설, 공수 이상 원인 가설, 재고 관리 개선 제안, 데이터 품질 개선 제안 중 관점을 선택한다.
- ‘AI에 전송할 집계 내용 확인’에서 실제 전송 수치를 보여준다. 사용자가 전송에 동의하고 ‘AI 해설 실행’을 누른 경우에만 호출한다.
- 전송 허용값은 기간·기준일, 입고/완료 건수, 공수 합계, 공수 누락 건수, 재고 행수, 품질 확인사항 수, 이상 후보 건수, 비교 부족 건수, 반복 시리얼 해당 행수이다.
- 이름·SITE·시리얼·모델별 원문·업무 원본 행·첨부 마스터는 전송하지 않는다. 키는 인증 헤더로만 사용한다.
- 개인 API 계정에 요금이 발생할 수 있고 제공사의 데이터 처리 정책이 적용됨을 안내한다. 선택적 AI 해설은 외부 전송이 발생하므로 ‘모든 분석은 외부 전송 없음’이라고 표시하지 않는다.
- 현재 연결은 https://api.openai.com/v1/responses, 모델 gpt-4.1-mini, store=false, 최대 출력 1,800토큰, 연결 제한 45초이다. 임의 주소로 인증정보를 보내거나 리디렉션하지 않는다.
- store=false를 외부 제공사의 완전한 무보관 보장이라고 설명하지 않는다.
- 답변은 한국어로 사실·원인 가설·확인사항·제안을 구분한다. 근거 없는 추세·개별 원인·수치를 만들지 않도록 지시한다. 업무 데이터를 자동 수정하지 않는다.
- 키 오류·권한 부족·한도/잔액·연결 실패는 안전한 안내문으로 처리한다. API 원문 오류에 포함될 수 있는 민감정보를 노출하지 않는다. 자동 재시도로 비용을 중복 발생시키지 않는다.

### AI-05 검증 범위

개인 키 분리·삭제, 명시적 실행 전 무호출, 집계 전송 허용목록, 인증 헤더, store=false, 응답 표시와 오류 메시지는 모의 응답 테스트로 확인했다. 실제 유효 키를 이용한 유료 API 응답·청구 및 모델 접근 가능 여부는 미검증이며 운영자가 본인의 키로 확인해야 한다.

## 18. 데이터 모델 및 이관 구현 지침

원본 첨부의 초기 CREATE TABLE 문만 실행하고 최신 스키마가 완성됐다고 판단하지 말라. 현재 app/db.py의 ensure_schema와 각 서비스의 추가 스키마 적용을 함께 확인하라. 운영 DB에 초기 DDL을 재실행하거나 기존 테이블을 무조건 삭제하지 말라.

### DB-01 주요 업무 필드

rework_items는 id, category, source_no, 입고일, 담당자, 담당팀, site, 재작업월, 재작업일, 품목분류, 모델명, serial, 변경모델명, 변경serial, 투입공수, 작업주체, 입고수량, 완료수량, 구분, 재작업내용, 비고_원문, status 및 생성·수정 메타데이터를 가진다. category는 완제품/대여, status는 검수대기/확정/완료이다. 완료 규칙과 저장 상태가 일치하도록 정규화하고 기존 데이터를 검증한다.

### DB-02 계정·관리 정보

- users: 회사명·이름·팀·직책·login_id·email·password_hash·role·approved·can_upload·permissions. role은 관리자/담당자/일반 3종이다. permissions는 메뉴별 권한 JSON이며 기존 업로드 허용값은 호환 처리한다.
- managers: 이름·담당팀(team)·사용 여부. 이름 중복을 허용하지 않는다.
- settings: key·category·value. 카테고리별 key는 ‘설정키|완제품’ 또는 ‘설정키|대여’로 저장하여 기본키 충돌을 방지한다.
- upload_logs와 import_batches: 업로드 결과 및 파일 내용 해시·카테고리 중복 가드.
- site_flags: 검수 확인 대상과 처리 상태.
- 로그인 세션, 비밀번호 재설정 코드, 삭제 감사 이력은 해당 서비스 스키마를 적용한다. 토큰·코드는 해시 저장하며 실제 값을 문서·테스트 산출물에 기록하지 않는다.

### DB-03 초기값과 운영값

신규 설치의 장기재고 기본값은 카테고리별 180일, 제외 구분은 빈 목록, 분당임율 547, MODEL군 DISPLAY, 작업구분 재작업이다. 사용 중인 DB의 90일 등 변경값은 그대로 보존한다. 설정값을 초기값으로 매번 덮어쓰지 않는다. MODEL군·작업구분은 비용 출력용이며 재고 표의 ‘구분’과 별개이다.

### MIG-01 원본 매핑

완제품은 ‘완제품재작업현황’, 대여는 ‘대여작업현황’ 시트를 읽으며 헤더는 3행(0부터 세면 2)이다. 실제 원본에 맞춰 mapping_config.py를 사용하고 컬럼명 개행을 보존·정규화한다.

- 완제품 ‘사이트명’, 대여 ‘대여처’는 공통 site로 연결한다.
- No.는 source_no, Ser.는 serial, 변경Ser.는 변경serial, 비고는 비고_원문으로 연결한다.
- 품목 분류·투입 공수·작업 주체·입고 수량·완료 수량은 원본 개행이 있는 표제와 대응한다.
- 입고년도·입고월은 별도 업무 저장값으로 중복 적재하지 않으며 출력 시 입고일을 기준으로 구성한다.
- 날짜는 지원되는 엑셀 날짜·날짜 표현을 정규화하고 실패값을 검수 대상으로 기록한다. 숫자는 안전하게 변환하며 결측과 0을 구분한다.
- 완전 공백과 번호만 있는 행을 제외한다. 중간 공백 뒤의 유효 업무행은 버리지 않는다. 완료 판정에 공수의 존재 여부를 사용하지 않는다.
- 중복 파일은 해시 및 카테고리로 방지한다. 다른 파일의 개별 중복 행까지 자동 병합한다고 가정하지 않는다.
- 이관 결과는 카테고리별 유효행·입고수량·완료수량·완료/재고·날짜 실패를 원본과 대조한다. 고정 과거 행 수를 맞추려고 행을 임의 추가·삭제하지 않는다.

## 19. 웹주소 배포 및 접근 보호

승인된 사용자는 추후 발급되는 웹주소에서 로그인해 이용한다. 회사 내부 서버를 반드시 사용할 필요는 없지만 웹주소만 입력한다고 호스팅 서버가 생성되는 것은 아니다. 현재 로컬 주소는 운영 공용 주소가 아니다. 도메인 연결·실제 외부 배포는 아직 수행하지 않았다.

- Python 실행, 영구 디스크, HTTPS, WebSocket을 제공하는 외부 호스팅에 설치한다.
- SQLite 운영은 단일 앱 인스턴스를 기준으로 한다. 다중 인스턴스 확장은 별도 DB 전환·검증을 거친다.
- 외부 공개 전에 최초 관리자 계정을 설정한다. 빈 DB 상태의 관리자 초기화 화면을 공개하지 않는다.
- DB·원본·백업은 영구 저장하고 정적 웹 경로로 공개하지 않는다. 비밀 키를 저장소에 넣지 않는다.
- /rework-dashboard/ 경로와 로그인 쿠키 경로를 일치시킨다. CORS/XSRF 보호를 유지하고 HTTPS에서는 Secure 쿠키를 사용한다.
- 미로그인·미승인 사용자 및 권한 없는 메뉴 요청은 서버에서 차단한다. 메뉴 숨김만으로 보호를 대체하지 않는다.
- 조회 허용은 데이터 열람 허용이다. 화면 캡처 등 모든 복제를 막는 기능이나 완전한 유출 방지 보장으로 설명하지 않는다.
- 공개 전 로그아웃·승인 취소·권한 변경·새로고침·토큰 만료·백업 복구·서버 재시작 후 영구 보존을 검증한다.

로컬 실행 명령:

`python -m streamlit run app/main.py --server.address 127.0.0.1 --server.port 8511 --server.baseUrlPath rework-dashboard --server.headless true`

외부 호스팅은 위 주소 바인딩을 서버 환경에 맞게 설정하고 HTTPS 프록시 뒤에서 제공한다. 로컬 실행을 외부 배포 완료로 보고하지 않는다.

## 20. 후속 구현 순서와 최종 인수

### 개발 AI에게 전달할 실행 지침

1. 기존 프로젝트와 운영 문서·코드·설정의 차이를 먼저 확인하라. 본 문서를 새 프로젝트 생성 지시로 해석하지 말라.
2. 수정 대상 코드 및 필요한 데이터의 복구 가능한 백업을 준비하라. 운영 데이터로 파괴적 테스트를 실행하지 말라.
3. 완료 판정·담당팀 연결·권한 검사를 공통 서비스에서 유지하고 화면마다 상이한 계산을 중복 구현하지 말라.
4. DB 변경은 기존 행·계정·참조를 보존하는 마이그레이션으로 적용하라. 초기화가 필요한 경우 임시 테스트 DB만 사용하라.
5. 인증/권한, 업로드/검수, 재고/완료, 비용 출력, 공통 UI, AI 순으로 영향 범위를 검증하라. 이미 구현된 기능을 다시 만들기보다 회귀 여부를 확인하라.
6. 테스트 결과, 변경한 파일, 남은 제한과 실제 운영 확인 필요 항목을 보고하라. Git 저장소가 없는 환경에서 커밋했다고 주장하지 말라.

### 추가 인수 시나리오

- 일반은 조회만, 담당자는 조회·다운로드, 관리자는 모든 작업을 기본 허용하는지 확인한다. 개별 권한 회수 후 기존 세션에서도 제한되는지 확인한다.
- 표 필터를 바꾼 뒤 전체 선택이 원래 행 위치에 잘못 적용되지 않는지, 다운로드 행 수가 대상 범위와 일치하는지 확인한다.
- 완료수량 1·공수 공란·완료일 공란을 포함한 대표 사례를 원본 마스터와 대조한다.
- 정식 비용 파일의 두 시트, 16열 재작업현황 및 21열 대여반납, 금액 반올림과 공란 처리를 확인한다.
- AI 기본 분석만 실행하면 외부 호출이 없는지, 동의 없는 AI 실행이 막히는지, 키가 다른 사용자의 화면·DB·파일에 남지 않는지 확인한다.
- 네트워크 실패·잘못된 키·사용 한도 초과에서도 업무 통계 기능을 계속 사용할 수 있는지 확인한다.
- PDF·명세 작성 완료와 실제 공용 웹 배포·유료 API 실사용 인수를 구별한다.

### 검토 근거와 남은 확인

첨부 구현프롬프트, 2026-09-15 요구사항 명세서, 후속 사용자 요청 및 2026-09-16 현행 코드를 대조하여 개정했다. 특히 DB 기본값·완료 함수·이관 빈행 처리·권한 서비스·비용 출력·개인 API 구현을 확인했다. 이 작업은 문서 개정이며 운영 데이터와 대시보드 기능을 추가 변경하지 않았다.

직전 AI 기능 작업에서 화면·권한 검사 6건과 신규 AI 관련 검사 5건이 통과했다. 이는 전체 업무의 최종 인수 완료를 뜻하지 않는다. 유효한 개인 키로 실제 AI 응답을 확인하는 작업과 외부 호스팅 배포 검증은 남아 있다.

API 구현 참고: OpenAI Responses API 문서 https://developers.openai.com/api/reference/cli/resources/responses/methods/create 및 모델 문서 https://developers.openai.com/api/docs/models/gpt-4.1-mini . 모델 제공·요금·정책은 운영 시 공식 문서로 재확인한다.
'''
text=intro+base+append
(OUT/(NAME+'.md')).write_text(text,encoding='utf-8-sig')
pdfmetrics.registerFont(TTFont('Malgun','C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('MalgunBold','C:/Windows/Fonts/malgunbd.ttf'))
pdfmetrics.registerFontFamily('Malgun',normal='Malgun',bold='MalgunBold',italic='Malgun',boldItalic='MalgunBold')
styles={
 'body':ParagraphStyle('body',fontName='Malgun',fontSize=9,leading=15,spaceAfter=6,wordWrap='CJK',textColor=colors.HexColor('#25364A')),
 'h1':ParagraphStyle('h1',fontName='MalgunBold',fontSize=20,leading=29,spaceAfter=16,wordWrap='CJK',textColor=colors.HexColor('#18344C')),
 'h2':ParagraphStyle('h2',fontName='MalgunBold',fontSize=14,leading=21,spaceBefore=16,spaceAfter=9,keepWithNext=True,wordWrap='CJK',textColor=colors.HexColor('#197E88')),
 'h3':ParagraphStyle('h3',fontName='MalgunBold',fontSize=10.5,leading=17,spaceBefore=10,spaceAfter=7,keepWithNext=True,wordWrap='CJK',textColor=colors.HexColor('#18344C')),
 'bullet':ParagraphStyle('bullet',fontName='Malgun',fontSize=9,leading=15,spaceAfter=5,leftIndent=10,firstLineIndent=-8,wordWrap='CJK',textColor=colors.HexColor('#25364A')),
}
def markup(s):
    s=escape(s)
    s=re.sub(r'\*\*(.+?)\*\*',r'<b>\1</b>',s)
    s=re.sub(r'`(.+?)`',r'\1',s)
    return s
story=[]
for line in text.splitlines():
    if not line.strip():continue
    kind='body'
    if line.startswith('# '):kind='h1';line=line[2:]
    elif line.startswith('## '):kind='h2';line=line[3:]
    elif line.startswith('### '):kind='h3';line=line[4:]
    elif line.startswith('- '):kind='bullet';line='• '+line[2:]
    story.append(Paragraph(markup(line),styles[kind]))
def footer(c,doc):
    w,h=A4
    c.setStrokeColor(colors.HexColor('#D6E2E8'));c.line(42,h-35,w-42,h-35)
    c.setFont('Malgun',8);c.setFillColor(colors.HexColor('#63788A'))
    c.drawString(42,h-26,'재작업 통합 관리 대시보드 | 구현 프롬프트 2.0')
    c.drawString(42,25,'2026-09-16 · 현행 구현 및 후속 개발 기준')
    c.drawRightString(w-42,25,str(doc.page))
doc=SimpleDocTemplate(str(OUT/(NAME+'.pdf')),pagesize=A4,rightMargin=42,leftMargin=42,topMargin=49,bottomMargin=45,title=NAME,author='생산관리 대시보드')
doc.build(story,onFirstPage=footer,onLaterPages=footer)
print(OUT/(NAME+'.pdf'))
