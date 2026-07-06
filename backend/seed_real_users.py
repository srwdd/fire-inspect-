import sqlite3, hashlib

conn = sqlite3.connect('/opt/fire-inspect/backend/fire_inspect.db')

def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()

# Get org IDs
gxf_id = conn.execute("SELECT id FROM organizations WHERE name LIKE '%广丰区%'").fetchone()[0]
print(f'广丰区大队 id={gxf_id}')

# Create 上饶市消防救援支队 org if not exists
row = conn.execute("SELECT id FROM organizations WHERE name LIKE '%上饶市消防救援支队%'").fetchone()
if not row:
    c = conn.execute("INSERT INTO organizations (name, short_name) VALUES (?, ?)",
          ('上饶市消防救援支队', '支队'))
    conn.commit()
    sr_id = c.lastrowid
    print(f'Created: 上饶市消防救援支队 id={sr_id}')
else:
    sr_id = row[0]
    print(f'上饶支队 id={sr_id}')

# 广丰区用户
gxf_users = [
    ('wangdongdong@gf', '123456', 'chief', '王冬冬', gxf_id),
    ('luochong', '123456', 'chief', '罗翀', gxf_id),
    ('zhangjian', '123456', 'lead', '张建', gxf_id),
    ('zhoujiawei', '123456', 'lead', '周嘉伟', gxf_id),
    ('liuhuixiang', '123456', 'lead', '刘辉翔', gxf_id),
    ('zhangli', '123456', 'lead', '张利', gxf_id),
]

# 支队用户
sr_users = [
    ('test', '123456', 'lead', 'Test', sr_id),
]

for username, password, role, name, oid in gxf_users + sr_users:
    row = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
    if row:
        conn.execute('UPDATE users SET role=?, display_name=?, org_id=?, password_hash=? WHERE username=?',
                     (role, name, oid, hash_pw(password), username))
        print(f'  Updated: {username} -> {name} ({role}) org={oid}')
    else:
        conn.execute('INSERT INTO users (username, password_hash, role, display_name, org_id) VALUES (?,?,?,?,?)',
                     (username, hash_pw(password), role, name, oid))
        print(f'  Created: {username} -> {name} ({role}) org={oid}')

conn.commit()
conn.close()
print('\nDone')
