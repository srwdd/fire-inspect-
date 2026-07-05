"""Seed default RBAC users"""
import hashlib, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.db.session import SessionLocal, engine, Base
from app.db.models import User

def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()

Base.metadata.create_all(bind=engine)
db = SessionLocal()

users = [
    ("admin", "admin123", "admin", "系统管理员", ""),
    ("chief1", "123456", "chief", "大队长", "XX消防救援大队"),
    ("lead1", "123456", "lead", "张监督员", "XX消防救援大队"),
    ("assist1", "123456", "assist", "李消防员", "XX消防救援大队"),
]

for username, password, role, name, unit in users:
    if db.query(User).filter(User.username == username).first():
        print(f"  Skip: {username} exists")
        continue
    db.add(User(username=username, password_hash=hash_pw(password),
                role=role, display_name=name, unit=unit))
    print(f"  Created: {username} ({role})")

db.commit()
db.close()
print("Seed complete")
