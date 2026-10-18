"""One-shot: create/update admin. Run:
  python -m scripts.make_admin <mobile> <password> [name]
Example:
  python -m scripts.make_admin 9834460139 MyStrong@123 Admin
"""
import sys
from app.db.session import SessionLocal
from app.models.user import User
from app.core.security import hash_password


def main():
    if len(sys.argv) < 3:
        print("Usage: python -m scripts.make_admin <mobile> <password> [name]")
        sys.exit(1)
    mobile = sys.argv[1].strip()
    password = sys.argv[2].strip()
    name = sys.argv[3].strip() if len(sys.argv) > 3 else "Administrator"
    if len(password) < 8:
        print("Password must be at least 8 characters")
        sys.exit(1)
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.mobile == mobile).first()
        pw_hash = hash_password(password)
        if u:
            u.password_hash = pw_hash
            u.role = "admin"
            u.is_active = True
            if name:
                u.name = name
            action = "UPDATED"
        else:
            db.add(User(name=name, mobile=mobile,
                        password_hash=pw_hash, role="admin"))
            action = "CREATED"
        db.commit()
        print(f"{action} admin | mobile={mobile} | name={name}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
