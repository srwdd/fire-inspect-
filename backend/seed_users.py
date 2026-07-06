"""Seed RBAC users + organizations"""
import hashlib, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.db.session import SessionLocal, engine, Base
from app.db.models import User, Organization

def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()

Base.metadata.create_all(bind=engine)
db = SessionLocal()

# Create default org
org = db.query(Organization).filter(Organization.name == "广丰区消防救援大队").first()
if not org:
    org = Organization(name="广丰区消防救援大队", short_name="广丰大队")
    db.add(org); db.commit()
    print("  Created: 广丰区消防救援大队")
else:
    print("  Skip: org exists")

# Create users
users = [
    ("admin", "admin123", "admin", "系统管理员", org.id),
    ("chief1", "123456", "chief", "王大队长", org.id),
    ("lead1", "123456", "lead", "张监督员", org.id),
    ("assist1", "123456", "assist", "李消防员", org.id),
]
for username, password, role, name, oid in users:
    if db.query(User).filter(User.username == username).first():
        print(f"  Skip: {username} exists")
        continue
    db.add(User(username=username, password_hash=hash_pw(password),
                role=role, display_name=name, unit=org.short_name))
    print(f"  Created: {username} ({role})")

db.commit(); db.close()
print("Seed complete")
