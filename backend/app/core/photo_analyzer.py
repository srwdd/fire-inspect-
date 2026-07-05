"""Vision LLM photo hazard analysis — supports Qwen-VL, Kimi, etc."""
import base64
import json
import logging
from pathlib import Path
from typing import Dict, Optional
import httpx

logger = logging.getLogger(__name__)
_HAZARD_LABELS: Optional[Dict] = None

def _load_hazard_labels() -> Dict:
    global _HAZARD_LABELS
    if _HAZARD_LABELS is not None:
        return _HAZARD_LABELS
    label_path = Path(__file__).resolve().parent / 'app' / 'data' / 'hazard_labels.json'
    if not label_path.exists():
        label_path = Path(__file__).resolve().parent.parent / 'app' / 'data' / 'hazard_labels.json'
    if label_path.exists():
        _HAZARD_LABELS = json.loads(label_path.read_text('utf-8'))
    else:
        _HAZARD_LABELS = {'categories': {}}
    return _HAZARD_LABELS

def _build_label_taxonomy() -> str:
    labels = _load_hazard_labels()
    cats = labels.get('categories', {})
    lines = []
    for cat_key, cat_info in cats.items():
        cat_name = cat_info.get('name', cat_key)
        for label_code, label_info in cat_info.get('labels', {}).items():
            lines.append('  {}: {} - {}'.format(label_code, cat_name, label_info['name']))
    return '\n'.join(lines)

def _lookup_hazard(hazard_code: str) -> Dict:
    labels = _load_hazard_labels()
    for cat_info in labels.get('categories', {}).values():
        for code, info in cat_info.get('labels', {}).items():
            if code == hazard_code:
                return {
                    'hazard_code': code,
                    'hazard_category': cat_info.get('name', ''),
                    'hazard_name': info.get('name', ''),
                    'regulation': info.get('regulation', []),
                    'rectification': info.get('rectification', ''),
                    'deadline': info.get('deadline', '3 days'),
                    'severity': info.get('severity', 'normal'),
                }
    return {}

async def analyze_photo(image_bytes, item_context, api_key,
                        base_url='https://api.siliconflow.cn/v1',
                        model='deepseek-ai/deepseek-vl2'):
    facility = item_context.get('facility', '')
    check_point = item_context.get('check_point', '')
    regulation = item_context.get('regulation', {})
    reg_source = regulation.get('source', '')
    reg_text = regulation.get('text', '')[:300]
    taxonomy = _build_label_taxonomy()

    # Step 1: Vision API
    vision_error = ''
    try:
        img_b64 = base64.b64encode(image_bytes).decode('utf-8')
        result = await _call_vision_api(img_b64, facility, check_point, reg_source, reg_text,
                                        taxonomy, api_key, base_url, model)
        return result
    except Exception as _e:
        vision_error = str(_e)[:200]
        logger.warning('Vision API failed: %s, trying text fallback', vision_error)

    # Step 2: Text fallback
    try:
        result = await _call_text_fallback(facility, check_point, reg_source, reg_text,
                                           api_key, base_url, model, vision_error)
        return result
    except Exception:
        logger.exception('Both vision and text fallback failed')

    return {
        'violation': None,
        'reason': 'AI analysis temporarily unavailable, please inspect manually: ' + facility,
        'confidence': 0.0,
        'hazard_code': None, 'hazard_category': None,
        'regulation': [], 'rectification': '', 'deadline': '',
        'detail': {
            'judgment': 'unable', 'hazard_code': 'NONE',
            'device': facility, 'description': 'Please check manually: ' + check_point,
            'severity': 'none', 'confidence': 'low'
        },
        'raw': '',
    }

async def _call_vision_api(img_b64, facility, check_point, reg_source, reg_text, taxonomy,
                            api_key, base_url, model):
    prompt = (
        '你是消防设施检查专家。请根据照片进行深度分析。\n\n'
        '## 检查部位\n' + facility + '\n\n'
        '## 检查要点\n' + check_point + '\n\n'
        '## 法规依据\n' + reg_source + '\n' + reg_text + '\n\n'
        '## 隐患标签\n' + taxonomy + '\n\n'
        '只返回JSON: {"判定":"合格/不合格/无法判断",'
        '"hazard_code":"编码","设备类型":"名称","隐患描述":"简要描述(100字内)",'
        '"隐患等级":"严重/重大/一般/无","置信度":"高/中/低"}'
    )

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            base_url + '/chat/completions',
            headers={'Authorization': 'Bearer ' + api_key},
            json={
                'model': model,
                'messages': [{'role': 'user', 'content': [
                    {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + img_b64}},
                    {'type': 'text', 'text': prompt},
                ]}],
                'max_tokens': 600, 'temperature': 0.1,
            },
        )
        data = resp.json()
        if 'error' in data:
            raise RuntimeError(str(data['error'].get('message', data['error']))[:200])
        reply = data['choices'][0]['message']['content'] if 'choices' in data else ''
    return _parse_to_contract(reply, facility)

async def _call_text_fallback(facility, check_point, reg_source, reg_text, api_key, base_url, model, error_msg):
    prompt = (
        'You are a fire safety assistant.\n'
        'User uploaded a photo of "' + facility + '" but image analysis is unavailable.\n'
        'Based on the check item, give the most common hazard reminders.\n\n'
        'Facility: ' + facility + '\nCheck Point: ' + check_point + '\n'
        'Regulation: ' + reg_source + ' ' + reg_text + '\n\n'
        'Return JSON: {"judgment":"unclear","hazard_code":"NONE","device":"' + facility + '",'
        '"description":"Photo AI unavailable. Please inspect: ' + facility + ' - ' + check_point + '",'
        '"severity":"minor","confidence":"low"}'
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            base_url + '/chat/completions',
            headers={'Authorization': 'Bearer ' + api_key},
            json={'model': model, 'messages': [{'role': 'user', 'content': prompt}],
                  'max_tokens': 400, 'temperature': 0.1},
        )
        data = resp.json()
        reply = data['choices'][0]['message']['content'] if 'choices' in data and 'choices' in data else ''
    return _parse_to_contract(reply, facility)

def _parse_to_contract(reply, fallback_facility=''):
    detail = _extract_detail(reply, fallback_facility)
    judgment = detail.get('判定', '无法判断')
    if '不合格' in judgment or 'non-compliant' in judgment:
        violation = True
    elif '合格' in judgment or 'compliant' in judgment:
        violation = False
    else:
        violation = None
    confidence = _confidence(detail.get('置信度', '中'))
    reason = detail.get('隐患描述', '')
    hazard_code = detail.get('hazard_code', 'NONE')
    hazard_info = _lookup_hazard(hazard_code) if hazard_code and hazard_code != 'NONE' else {}
    regulation = hazard_info.get('regulation', [])
    rectification = hazard_info.get('rectification', '')
    deadline = hazard_info.get('deadline', '')
    return {
        'violation': violation, 'reason': reason, 'confidence': confidence,
        'hazard_code': hazard_code if hazard_code != 'NONE' else None,
        'hazard_category': hazard_info.get('hazard_category'),
        'hazard_name': hazard_info.get('hazard_name'),
        'regulation': regulation, 'rectification': rectification, 'deadline': deadline,
        'detail': detail, 'raw': reply,
    }

def _extract_detail(reply, fallback_facility=''):
    try:
        start = reply.find('{')
        end = reply.rfind('}') + 1
        if start >= 0 and end > start:
            data = json.loads(reply[start:end])
            return {
                '判定': data.get('判定', data.get('judgment', '无法判断')),
                'hazard_code': data.get('hazard_code', 'NONE'),
                '设备类型': data.get('设备类型', data.get('device', fallback_facility)),
                '隐患描述': data.get('隐患描述', data.get('description', '')),
                '隐患等级': data.get('隐患等级', data.get('severity', '无')),
                '置信度': data.get('置信度', data.get('confidence', '中')),
            }
    except (json.JSONDecodeError, KeyError):
        pass
    return {
        '判定': '无法判断', 'hazard_code': 'NONE',
        '设备类型': fallback_facility, '隐患描述': '',
        '隐患等级': '无', '置信度': '中'
    }

def _confidence(val):
    v = str(val).strip()
    if 'high' in v.lower() or '高' in v: return 0.9
    if 'medium' in v.lower() or '中' in v: return 0.6
    if 'low' in v.lower() or '低' in v: return 0.3
    try: return float(v)
    except (ValueError, TypeError): return 0.5
