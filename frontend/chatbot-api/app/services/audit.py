from app.repositories.users import now


def record(db, action, actor_id=None, department=None, target_id=None):
    # Never record passwords, tokens, or message content in audit events.
    db.record_audit(actor_id, department, action, target_id, now())
