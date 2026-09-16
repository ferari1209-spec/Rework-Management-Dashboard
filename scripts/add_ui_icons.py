"""정적 위젯 호출에 Streamlit 기본 선 아이콘을 추가한다."""
import ast
from pathlib import Path
root = Path(__file__).resolve().parents[1]/'app'
for path in [*sorted((root/'pages').glob('*.py')),root/'table_ui.py',root/'ui.py']:
    source=path.read_text(encoding='utf-8'); raw=source.encode('utf-8')
    offsets=[0]
    for line in raw.splitlines(keepends=True): offsets.append(offsets[-1]+len(line))
    changes=[]
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node,ast.Call) or not isinstance(node.func,ast.Attribute): continue
        kind=node.func.attr
        label=node.args[0].value if node.args and isinstance(node.args[0],ast.Constant) and isinstance(node.args[0].value,str) else ''
        icon=None
        if kind=='download_button': icon='download'
        elif kind in ('button','form_submit_button'):
            icon=next((symbol for word,symbol in [('삭제','delete'),('거부','delete'),('해제','deselect'),('전체 선택','select_all'),('다운로드','download'),('수정','edit'),('저장','save'),('승인','verified_user'),('완료','task_alt'),('추가','person_add'),('등록','add_circle'),('로그아웃','logout'),('발급','key'),('상세','open_in_new'),('반영','publish')] if word in label),None)
        elif kind=='text_input' and '검색' in label: icon='search'
        if icon and not any(k.arg=='icon' for k in node.keywords):
            pos=offsets[node.end_lineno-1]+node.end_col_offset-1
            prefix='' if raw[:pos].rstrip().endswith(b',') else ','
            changes.append((pos,pos,(prefix+f" icon=':material/{icon}:'").encode()))
        if label and kind in ('date_input','selectbox','multiselect') and ':material/' not in label:
            symbol='calendar_month' if kind=='date_input' else next((v for k,v in [('모델','inventory_2'),('담당자','person'),('사용자','person'),('담당팀','groups'),('SITE','location_on'),('역할','admin_panel_settings')] if k in label),'filter_list')
            arg=node.args[0];a=offsets[arg.lineno-1]+arg.col_offset;b=offsets[arg.end_lineno-1]+arg.end_col_offset
            changes.append((a,b,repr(f':material/{symbol}: {label}').encode()))
    for a,b,replacement in sorted(changes,reverse=True): raw=raw[:a]+replacement+raw[b:]
    path.write_bytes(raw)
