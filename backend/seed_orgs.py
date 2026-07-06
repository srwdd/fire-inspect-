import sqlite3, hashlib

conn = sqlite3.connect('/opt/fire-inspect/backend/fire_inspect.db')

# Create orgs table
conn.execute('''CREATE TABLE IF NOT EXISTS organizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    short_name TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT ''
)''')

# Create users table
conn.execute('''CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'assist',
    display_name TEXT NOT NULL,
    org_id INTEGER DEFAULT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT ''
)''')

# 14 orgs
orgs = [
    '信州区消防救援大队', '广信区消防救援大队', '广丰区消防救援大队',
    '玉山县消防救援大队', '横峰县消防救援大队', '弋阳县消防救援大队',
    '铅山县消防救援大队', '德兴市消防救援大队', '婺源县消防救援大队',
    '万年县消防救援大队', '余干县消防救援大队', '鄱阳县消防救援大队',
    '上饶高铁经济试验区消防救援大队', '上饶经济技术开发区消防救援大队'
]

org_ids = {}
for name in orgs:
    row = conn.execute('SELECT id FROM organizations WHERE name = ?', (name,)).fetchone()
    if row:
        print(f'  Skip: {name}')
        org_ids[name] = row[0]
    else:
        c = conn.execute('INSERT INTO organizations (name, short_name) VALUES (?, ?)',
              (name, name.replace('消防救援大队', '大队')))
        conn.commit()
        org_ids[name] = c.lastrowid
        print(f'  Created: {name} (id={c.lastrowid})')

# Create admin + sample users in first org
def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()

gxf_id = org_ids['广丰区消防救援大队']
users = [
    ('admin', 'admin123', 'admin', '系统管理员', None),
    ('chief1', '123456', 'chief', '王大队长', gxf_id),
    ('lead1', '123456', 'lead', '张监督员', gxf_id),
    ('assist1', '123456', 'assist', '李消防员', gxf_id),
]
for username, password, role, name, oid in users:
    row = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
    if row:
        conn.execute('UPDATE users SET role=?, display_name=?, org_id=? WHERE username=?',
                     (role, name, oid, username))
        print(f'  Updated: {username} ({role})')
    else:
        conn.execute('INSERT INTO users (username, password_hash, role, display_name, org_id) VALUES (?,?,?,?,?)',
                     (username, hash_pw(password), role, name, oid))
        print(f'  Created: {username} ({role})')

conn.commit()
conn.close()
print('Seed complete')
