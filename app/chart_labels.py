"""그래프와 분리된 월별 수치표: 작은 화면에서는 가로 스크롤."""
from html import escape


def add_monthly_labels(fig):
    """데이터 영역과 분리된 그래프 상단에 월별 두 수량을 표시한다."""
    traces = [t for t in fig.data if t.type in ('bar','scatter')]
    if not traces:
        return
    months = list(traces[0].x)
    fig.update_yaxes(domain=[0,.72], rangemode='tozero')
    fig.update_xaxes(type='category')
    fig.update_layout(hovermode='x unified')
    fig.update_layout(margin=dict(l=70))
    fig.add_annotation(x=0,y=1,xref='paper',yref='paper',
        text='<span style="color:#436985"><b>입고</b></span><br><span style="color:#087f8e"><b>완료</b></span>',
        showarrow=False,xanchor='right',xshift=-12,yanchor='top',
        font=dict(size=11),align='right',bgcolor='#edf3f8',borderpad=2)
    for i, month in enumerate(months):
        parts = []
        for j, trace in enumerate(traces):
            value = dict(zip(trace.x,trace.y)).get(month,0)
            color = '#436985' if j == 0 else '#087f8e'
            parts.append(f'<span style="color:{color}">{value:,.0f}</span>')
        fig.add_annotation(x=month,y=1,xref='x',yref='paper',text='<br>'.join(parts),
            showarrow=False,yanchor='top',font=dict(size=11),align='center',
            bgcolor='#edf3f8',borderpad=2)


def monthly_values_html(series):
    months = list(dict.fromkeys(str(month) for _, points in series for month in points))
    header = '<th scope="col">항목 / 월</th>' + ''.join(f'<th scope="col">{escape(month)}</th>' for month in months)
    rows = []
    for name, points in series:
        values = {str(k): v for k, v in points.items()}
        cells = ''.join(f'<td>{values[m]:,.0f}대</td>' if m in values else '<td>—</td>' for m in months)
        rows.append(f'<tr><th scope="row">{escape(name)}</th>{cells}</tr>')
    return '<div class="chart-values"><table><caption>월별 수량 · 단위: 대</caption><thead><tr>'+header+'</tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>'
