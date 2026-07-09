"""消防设施检查 — Vision LLM photo analysis (v3)"""
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

async def analyze_photo(images_bytes, item_context, api_key,
                        base_url='https://dashscope.aliyuncs.com/compatible-mode/v1',
                        model='qwen-vl-max'):
    facility = item_context.get('facility', '')
    check_point = item_context.get('check_point', '')
    regulation = item_context.get('regulation', {})
    reg_source = regulation.get('source', '')
    reg_text = regulation.get('text', '')[:300]
    taxonomy = _build_label_taxonomy()

    try:
        images_b64 = [base64.b64encode(img).decode('utf-8') for img in images_bytes]
        result = await _call_vision_api(images_b64, facility, check_point, reg_source, reg_text,
                                        taxonomy, api_key, base_url, model)
        return result
    except Exception as _e:
        logger.warning('Vision API failed: %s', str(_e)[:200])

    try:
        result = await _call_text_fallback(facility, check_point, reg_source, reg_text,
                                           api_key, base_url, model)
        return result
    except Exception:
        logger.exception('Both vision and text fallback failed')

    return {
        'violation': None,
        'reason': '图片分析暂不可用，请人工检查: ' + facility,
        'confidence': 0.0,
        'hazard_code': None, 'hazard_category': None,
        'regulation': [], 'rectification': '', 'deadline': '',
        'detail': {'judgment': 'unable', 'hazard_code': 'NONE', 'device': facility,
                   'description': '请人工检查: ' + check_point, 'severity': 'none', 'confidence': 'low'},
        'raw': '',
    }

async def _call_vision_api(images_b64, facility, check_point, reg_source, reg_text, taxonomy,
                            api_key, base_url, model):
    # Facility-specific hard rules
    guides = {
        "防火门": "硬性判定: 1)铭牌不可见→标记隐患'铭牌缺失,建议核实耐火等级' 2)门未关闭→不合格 3)闭门器损坏→不合格 4)密封条脱落→不合格 5)门扇变形锈蚀→不合格 6)全部完好→合格",
        "灭火器": "硬性判定: 1)压力表红区→不合格 2)瓶体锈蚀→不合格 3)过期→不合格 4)被遮挡→不合格 5)外观完好→合格",
        "消火栓": "硬性判定: 1)箱门损坏→不合格 2)水带水枪缺失→不合格 3)阀门漏水→不合格 4)完好→合格",
        "疏散通道": "硬性判定: 1)有杂物堵塞→不合格 2)宽度不足→不合格 3)锁闭→不合格 4)畅通→合格",
        "安全出口": "硬性判定: 1)门锁闭→不合格 2)指示灯不亮→不合格 3)门前堆物→不合格 4)正常→合格",
    }
    guide_text = ""
    for k, v in guides.items():
        if k in facility:
            guide_text = f"\n## {k}判定规则\n{v}"
            break

    prompt = (
        "你是消防检查专家。铁律:永远不要说'无法判断'。\n"
        "铭牌/标签看不到就是问题→标记为隐患(建议现场核实)。\n"
        "照片中能看到什么就判定什么,不清晰也给出你的最佳判断。\n\n"
        "## 检查部位\n" + facility + "\n\n"
        "## 检查要点\n" + check_point + "\n\n"
        "## 法规依据\n" + reg_source + "\n" + reg_text + "\n\n"
        + guide_text + "\n\n"
        "## 隐患编码\n" + taxonomy + "\n\n"
        "返回JSON(判定只能是合格或不合格): "
        "{\"判定\":\"合格/不合格\",\"hazard_code\":\"编码或NONE\","
        "\"设备类型\":\"名称\",\"隐患描述\":\"照片中看到的具体问题(100字内)\","
        "\"隐患等级\":\"严重/重大/一般/无\",\"置信度\":\"高/中/低\"}"
    )

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            base_url + '/chat/completions',
            headers={'Authorization': 'Bearer ' + api_key},
            json={
                'model': model,
                'messages': [{'role': 'user', 'content': [
                    *[{'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + img}} for img in images_b64],
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

async def _call_text_fallback(facility, check_point, reg_source, reg_text, api_key, base_url, model):
    prompt = (
        "你是消防检查专家。用户上传了\"" + facility + "\"的照片但图片分析暂不可用。\n"
        "请根据检查要点，基于最常出现的问题给出检查提示，不要只说'请人工检查'。\n\n"
        "检查部位: " + facility + "\n检查要点: " + check_point + "\n"
        "法规: " + reg_source + " " + reg_text + "\n\n"
        "返回JSON: {\"判定\":\"不合格\",\"hazard_code\":\"NONE\","
        "\"设备类型\":\"" + facility + "\","
        "\"隐患描述\":\"图片分析暂不可用，请人工检查: " + check_point + "\","
        "\"隐患等级\":\"一般\",\"置信度\":\"低\"}"
    )
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            base_url + '/chat/completions',
            headers={'Authorization': 'Bearer ' + api_key},
            json={'model': model, 'messages': [{'role': 'user', 'content': prompt}],
                  'max_tokens': 400, 'temperature': 0.1},
        )
        data = resp.json()
        reply = data['choices'][0]['message']['content'] if 'choices' in data else ''
    return _parse_to_contract(reply, facility)

def _parse_to_contract(reply, fallback_facility=''):
    detail = _extract_detail(reply, fallback_facility)
    judgment = detail.get('判定', '不合格')
    if '不合格' in judgment or 'non-compliant' in judgment:
        violation = True
    elif '合格' in judgment or 'compliant' in judgment:
        violation = False
    else:
        violation = True  # 宁严勿松
    confidence = _confidence(detail.get('置信度', '中'))
    reason = detail.get('隐患描述', '')
    hazard_code = detail.get('hazard_code', 'NONE')
    hazard_info = _lookup_hazard(hazard_code) if hazard_code and hazard_code != 'NONE' else {}
    regulation = hazard_info.get('regulation', [])
    rectification = hazard_info.get('rectification', '')
    deadline = hazard_info.get('deadline', '')
    return {
        'violation': violation,
        'reason': reason or 'AI分析: ' + fallback_facility,
        'confidence': confidence,
        'hazard_code': hazard_code,
        'hazard_category': hazard_info.get('hazard_category', ''),
        'hazard_name': hazard_info.get('hazard_name', ''),
        'regulation': regulation,
        'rectification': rectification,
        'deadline': deadline,
        'detail': detail,
        'raw': reply,
    }

def _extract_detail(reply, fallback_facility=''):
    # Handle markdown-wrapped JSON (```json ... ```)
    cleaned = reply.strip()
    if cleaned.startswith('```'):
        # Remove markdown code fences
        lines = cleaned.split('\n')
        if lines[0].startswith('```'):
            lines = lines[1:]
        if lines and lines[-1].startswith('```'):
            lines = lines[:-1]
        cleaned = '\n'.join(lines)
    try:
        data = json.loads(cleaned)
        return {
            '判定': data.get('判定', data.get('judgment', '不合格')),
            'hazard_code': data.get('hazard_code', 'NONE'),
            '设备类型': data.get('设备类型', data.get('device', fallback_facility)),
            '隐患描述': data.get('隐患描述', data.get('description', '')),
            '隐患等级': data.get('隐患等级', data.get('severity', '一般')),
            '置信度': data.get('置信度', data.get('confidence', '中')),
        }
    except (json.JSONDecodeError, TypeError):
        pass
    return {
        '判定': '不合格', 'hazard_code': 'NONE',
        '设备类型': fallback_facility, '隐患描述': reply[:100],
        '隐患等级': '一般', '置信度': '低',
    }

def _confidence(val):
    if isinstance(val, (int, float)):
        return float(val)
    mapping = {'高': 0.85, '中': 0.6, '低': 0.35}
    return mapping.get(str(val), 0.5)
