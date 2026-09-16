import json

MENUS = {'upload':'업로드·검수','inventory':'재고현황','history':'완료이력','cost':'비용리포트','master':'마스터 다운로드','analysis':'AI 분석'}

def allowed(user, menu, action='view'):
    if not user or not user.get('approved'):
        return False
    if user.get('role') == '관리자':
        return True
    try:
        overrides = json.loads(user.get('permissions') or '{}')
    except (ValueError, TypeError):
        overrides = {}
    default = action == 'view' or (action == 'download' and user.get('role') == '담당자')
    if menu == 'upload' and action == 'edit':
        default = bool(user.get('can_upload'))
    view = overrides.get(menu, {}).get('view', True)
    return bool(view and overrides.get(menu, {}).get(action, default))
