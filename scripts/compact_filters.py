from pathlib import Path
root=Path(__file__).resolve().parents[1]/'app/pages'
for filename,start,end,width in [
 ('3_재고현황.py','c1, c2, c3, c4 = st.columns(4)','view = inv.copy()',980),
 ('4_완료이력.py','c1, c2 = st.columns(2)','if not done.empty:',460),
 ('5_비용리포트.py','c1, c2 = st.columns(2)','if d_from > d_to:',460),
]:
 p=root/filename;s=p.read_text(encoding='utf-8');a=s.index(start);b=s.index(end,a)
 block=s[a:b].rstrip()
 s=s[:a]+f"with st.container(width={width}, key='compact_filters'):\n"+'\n'.join('    '+line if line else '' for line in block.splitlines())+'\n\n'+s[b:]
 p.write_text(s,encoding='utf-8')
p=root/'4_완료이력.py';s=p.read_text(encoding='utf-8')
s=s.replace('    start_col, end_col = st.columns(2)',"    with st.container(width=460):\n        start_col, end_col = st.columns(2)")
p.write_text(s,encoding='utf-8')
