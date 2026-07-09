"""修复 speech.py 中 fuzzy-search 的数据读取逻辑"""
import re

with open('/opt/fire-inspect/backend/app/api/v1/speech.py', 'r', encoding='utf-8') as f:
    code = f.read()

# 修复 fuzzy_search 函数中的数据加载部分
old = '''        # 加载对应场景的检查项
        import json
        import os
        checklist_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'checklist_config.json')
        # checklist_config 不直接含检查项，我们直接从 fire_rules.json 提取
        rules_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'fire_rules.json')

        items = []
        if os.path.exists(rules_path):
            with open(rules_path, 'r', encoding='utf-8') as f:
                rules = json.load(f)
            # fire_rules.json 结构: {"scenes": {"hotel": {"items": [...]}, ...}}
            scene_data = rules.get('scenes', {}).get(scene, {})
            scene_items = scene_data.get('items', [])
            for i, item in enumerate(scene_items):
                items.append({
                    "index": i,
                    "facility": item.get('facility', ''),
                    "check_point": item.get('check_point', ''),
                })

        if not items:
            return FuzzySearchResponse(success=False, error=f"未找到场景 '{scene}' 的检查项")'''

new = '''        # 加载对应场景的检查项（从 fire_rules.json）
        import json
        import os
        rules_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'fire_rules.json')
        checklist_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'checklist_config.json')

        items = []
        # 优先从 fire_rules.json 提取（218条规则，含 scene 标签）
        if os.path.exists(rules_path):
            with open(rules_path, 'r', encoding='utf-8') as f:
                rules_data = json.load(f)
            all_rules = rules_data.get('rules', [])
            for i, rule in enumerate(all_rules):
                rule_scenes = rule.get('scene', [])
                # scene 可能是字符串列表或逗号分隔
                if isinstance(rule_scenes, str):
                    rule_scenes = [s.strip() for s in rule_scenes.split(',')]
                if scene in rule_scenes or not rule_scenes:
                    facility = rule.get('title', '') or rule.get('category', '')
                    check_point = rule.get('check_point', '') or rule.get('text', '')[:80]
                    items.append({
                        "index": i,
                        "facility": facility,
                        "check_point": check_point,
                    })

        # 如果 fire_rules.json 没有匹配，回退到 checklist_config.json
        if not items and os.path.exists(checklist_path):
            with open(checklist_path, 'r', encoding='utf-8') as f:
                checklist = json.load(f)
            scene_data = checklist.get('scenes', {}).get(scene, {})
            scene_items = scene_data.get('items', [])
            for i, item in enumerate(scene_items):
                items.append({
                    "index": i,
                    "facility": item.get('facility', ''),
                    "check_point": item.get('check_point', ''),
                })

        if not items:
            return FuzzySearchResponse(success=False, error=f"未找到场景 '{scene}' 的检查项")'''

if old in code:
    code = code.replace(old, new, 1)
    print('fixed fuzzy_search data loading')
else:
    print('ERROR: old string not found!')

# 同时移除之前添加的 debug 行
old_debug = '''try:
        fm = get_matcher()
        result = fm.classify_judgment(text)
        print(f'[DEBUG fuzzy-judge] text={text!r} pinyin={fm.to_pinyin(text)!r} result={result}', flush=True)
        return FuzzyJudgeResponse('''
new_nodebug = '''try:
        fm = get_matcher()
        result = fm.classify_judgment(text)
        return FuzzyJudgeResponse('''
if old_debug in code:
    code = code.replace(old_debug, new_nodebug, 1)
    print('removed debug line')
else:
    print('debug line not found (may already be removed)')

with open('/opt/fire-inspect/backend/app/api/v1/speech.py', 'w', encoding='utf-8') as f:
    f.write(code)

print('Done')
