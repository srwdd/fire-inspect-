#!/bin/bash
echo '=== HTML Div Balance ==='
python3 -c "
html = open('/opt/fire-inspect/web/index.html').read()
o = html.count('<div')
c = html.count('</div>')
print(f'<div>: {o}, </div>: {c}')
if o != c: print('FAIL - missing '+str(o-c)+' tags! DO NOT DEPLOY')
else: print('PASS')
"
echo '=== JS Syntax ==='
node --check /opt/fire-inspect/web/index.html 2>/dev/null
for f in /opt/fire-inspect/web/app_v*.js; do
    node --check "$f" 2>&1 | grep -i error && echo "FAIL: $f" || true
done
echo 'Done'
