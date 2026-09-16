from pathlib import Path
from html import escape
import re
root=Path(__file__).resolve().parents[1]
source=root/'outputs/요구사항명세서_재작업통합관리_20260915.md'
def inline(value):
    value=escape(value)
    value=re.sub(r'\*\*(.+?)\*\*',r'<strong>\1</strong>',value)
    return re.sub(r'`(.+?)`',r'<code>\1</code>',value)
parts=[];toc=[];lst=None
for line in source.read_text(encoding='utf-8').splitlines():
    item=line.startswith('- ') or bool(re.match(r'^\d+\. ',line))
    if lst and not item:
        parts.append(f'</{lst}>');lst=None
    if not line.strip():continue
    if line.startswith('#'):
        depth=len(line)-len(line.lstrip('#'));title=line[depth:].strip();identifier=f's{len(parts)}'
        parts.append(f'<h{depth} id="{identifier}">{inline(title)}</h{depth}>')
        if depth==2:toc.append(f'<a href="#{identifier}">{inline(title)}</a>')
    elif item:
        kind='ul' if line.startswith('- ') else 'ol'
        if lst!=kind:
            if lst:parts.append(f'</{lst}>')
            parts.append(f'<{kind}>');lst=kind
        parts.append('<li>'+inline(re.sub(r'^(?:- |\d+\. )','',line))+'</li>')
    else:parts.append('<p>'+inline(line.strip())+'</p>')
if lst:parts.append(f'</{lst}>')
html='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>재작업 통합 관리 대시보드 요구사항 명세서</title><style>
body{margin:0;background:#f3f5fa;color:#203746;font:15px/1.85 'Malgun Gothic',sans-serif}main{max-width:1000px;margin:32px auto;padding:48px;background:white;border-radius:16px;box-shadow:0 5px 20px #18304912}h1{font-size:30px;line-height:1.4;border-bottom:4px solid #247c83;padding-bottom:24px}h2{margin-top:42px;padding:10px 14px;background:#eaf1f6;border-left:4px solid #247c83;font-size:22px;break-after:avoid}h3{margin-top:26px;font-size:17px;break-after:avoid}li{margin-bottom:6px}code{overflow-wrap:anywhere;font-size:13px;background:#f2f5f8;padding:2px 4px}nav{display:flex;flex-wrap:wrap;gap:10px;padding:20px;background:#eaf1f6}nav a{color:#247c83;text-decoration:none;font-size:13px}button{background:#247c83;color:white;border:0;border-radius:8px;padding:12px 20px;cursor:pointer}p{margin:12px 0}@media print{body{background:white;font-size:10pt}main{margin:0;padding:0;box-shadow:none}nav,button{display:none}h2{font-size:15pt}h1{font-size:22pt}@page{size:A4;margin:18mm}}@media(max-width:700px){main{margin:0;padding:20px}}
</style><main><button onclick="window.print()">인쇄 / PDF 저장</button><nav>'''+''.join(toc)+'</nav>'+''.join(parts)+'</main></html>'
source.with_suffix('.html').write_text(html,encoding='utf-8')
assert html.count('<h2 ')==16
assert '무/재작업 현황: 원본 ‘구분’' in html
print('Created HTML; verified 16 sections and latest cost mapping.')
