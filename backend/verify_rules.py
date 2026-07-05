#!/usr/bin/env python3
"""消防检查系统 — 规则数据自动校验"""
import json
import sys
from collections import Counter

def verify(path='fire_rules.json'):
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    rules = [r for r in data['rules'] if r.get('inspection_type') != 'reference_only']
    errors = []

    total = len(data['rules'])
    print(f'Rules: {len(rules)} active / {total} total\n')

    # 1. Check duplicates per scene+inspection
    print('=== 1. 重复检查 ===')
    for insp in ['daily', 'preopen']:
        for vt in ['hotel','mall','entertainment','school','hospital','elderly','restaurant','highrise','mixed_use','factory','crowded','nine_small']:
            items = []
            for r in rules:
                itype = r.get('inspection_type','both')
                if (insp == 'daily' and itype == 'preopen') or (insp == 'preopen' and itype == 'daily'):
                    continue
                if vt not in r.get('scene',[]):
                    continue
                # Use title as key for dedup
                items.append(r.get('title',''))
            dups = {t:c for t,c in Counter(items).items() if c>1}
            if dups:
                print(f'  ⚠️ {vt} {insp}: {len(dups)} duplicates')
                for t,c in list(dups.items())[:3]:
                    print(f'      {t[:50]} x{c}')
                if len(dups)>3: print(f'      ... +{len(dups)-3}')

    # 2. Check step coverage
    print('\n=== 2. 步骤完整性 ===')
    for insp, exp_steps in [('daily', [31,32,33,34,35,36,37]), ('preopen', [1,2,3,5,6,7,8])]:
        for vt in ['hotel','nine_small']:
            steps_found = set()
            for r in rules:
                itype = r.get('inspection_type','both')
                if (insp == 'daily' and itype == 'preopen') or (insp == 'preopen' and itype == 'daily'):
                    continue
                if vt not in r.get('scene',[]):
                    continue
                s = r.get('daily_step' if insp == 'daily' else 'step', 5)
                steps_found.add(s if s else 5)
            missing = set(exp_steps) - steps_found
            if missing:
                errors.append(f'{vt} {insp}: missing steps {missing}')
                print(f'  ❌ {vt} {insp}: missing {missing}')
            else:
                print(f'  ✅ {vt} {insp}: all steps present')

    # 3. Check source priority
    print('\n=== 3. 来源优先级 ===')
    mgmt_gb = [r for r in rules if r.get('category')=='消防管理' and 'GB' in r.get('source','') and 'GB/T' not in r.get('source','')]
    if mgmt_gb:
        print(f'  ⚠️ {len(mgmt_gb)} management rules using GB standard (should use 消防法/公安部令):')
        for r in mgmt_gb[:3]:
            print(f'      {r["id"]}: {r.get("source","")[:40]}')

    # 4. Check order values
    print('\n=== 4. Order赋值 ===')
    for field, name in [('preopen_order','Preopen'), ('daily_order','Daily')]:
        missing = [r for r in rules if r.get(field) is None and r.get('inspection_type') not in ('reference_only',)]
        if missing:
            print(f'  ⚠️ {len(missing)} rules missing {name}_order:')
            for r in missing[:5]:
                print(f'      {r["id"]}: {r.get("title","")[:40]}')
        else:
            print(f'  ✅ All rules have {name}_order')

    # 5. Quick counts
    print('\n=== 5. 场景项数 ===')
    for vt in ['hotel','nine_small']:
        d = sum(1 for r in rules if vt in r.get('scene',[]) and r.get('inspection_type','both') in ('daily','both'))
        p = sum(1 for r in rules if vt in r.get('scene',[]) and r.get('inspection_type','both') in ('preopen','both'))
        print(f'  {vt:12s} daily={d} preopen={p}')

    # Summary
    msg = 'OK - no issues' if not errors else f'{len(errors)} issues found'
    print(f'\n{msg}')
    return len(errors) == 0

if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else 'fire_rules.json'
    ok = verify(path)
    sys.exit(0 if ok else 1)
