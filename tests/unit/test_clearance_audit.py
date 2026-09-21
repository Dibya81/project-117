import pytest
from backend.security.clearance import Clearance, ClearanceDenied
from backend.security.clearance.access import change_clearance
from backend.security.rbac import Principal


class MockAuditService:
    def __init__(self):
        self.records = []

    def record(self, **kwargs):
        self.records.append(kwargs)


def test_clearance_change_requires_auth():
    audit = MockAuditService()
    with pytest.raises(ClearanceDenied, match="Unauthenticated caller"):
        change_clearance(
            principal=None,
            target_user_id="user-123",
            new_clearance=Clearance.RESTRICTED,
            audit_service=audit,
        )
    assert len(audit.records) == 1
    assert audit.records[0]["outcome"] == "denied"
    assert audit.records[0]["approval"] == "rejected"


def test_clearance_change_requires_admin():
    audit = MockAuditService()
    operator = Principal(user="op1", roles=("operator",), authenticated=True)
    with pytest.raises(ClearanceDenied, match="lacks 'admin' role"):
        change_clearance(
            principal=operator,
            target_user_id="user-123",
            new_clearance=Clearance.CONFIDENTIAL,
            audit_service=audit,
        )
    assert len(audit.records) == 1
    assert audit.records[0]["outcome"] == "denied"


def test_clearance_self_elevation_requires_distinct_approver():
    audit = MockAuditService()
    admin = Principal(user="admin1", roles=("admin",), authenticated=True)
    
    # Self elevation without approver fails
    with pytest.raises(ClearanceDenied, match="Self-elevation requires a distinct admin approver"):
        change_clearance(
            principal=admin,
            target_user_id="admin1",
            current_clearance=Clearance.INTERNAL,
            new_clearance=Clearance.HIGHLY_CONFIDENTIAL,
            audit_service=audit,
        )
    
    # Self elevation with self as approver fails
    with pytest.raises(ClearanceDenied, match="Self-elevation requires a distinct admin approver"):
        change_clearance(
            principal=admin,
            target_user_id="admin1",
            current_clearance=Clearance.INTERNAL,
            new_clearance=Clearance.HIGHLY_CONFIDENTIAL,
            approver=admin,
            audit_service=audit,
        )

    # Self elevation with distinct admin approver succeeds
    admin2 = Principal(user="admin2", roles=("admin",), authenticated=True)
    res = change_clearance(
        principal=admin,
        target_user_id="admin1",
        current_clearance=Clearance.INTERNAL,
        new_clearance=Clearance.HIGHLY_CONFIDENTIAL,
        approver=admin2,
        reason="Security audit task",
        audit_service=audit,
    )
    assert res == Clearance.HIGHLY_CONFIDENTIAL
    last = audit.records[-1]
    assert last["outcome"] == "success"
    assert last["approval"] == "approved"
    assert last["detail"]["target_user_id"] == "admin1"
    assert last["detail"]["previous_clearance"] == "INTERNAL"
    assert last["detail"]["new_clearance"] == "HIGHLY_CONFIDENTIAL"
    assert last["detail"]["approver_id"] == "admin2"


def test_admin_can_modify_other_user_clearance():
    audit = MockAuditService()
    admin = Principal(user="admin1", roles=("admin",), authenticated=True)
    res = change_clearance(
        principal=admin,
        target_user_id="worker42",
        current_clearance=Clearance.INTERNAL,
        new_clearance=Clearance.CONFIDENTIAL,
        reason="Promoted to senior engineer",
        audit_service=audit,
    )
    assert res == Clearance.CONFIDENTIAL
    assert len(audit.records) == 1
    assert audit.records[0]["outcome"] == "success"
    assert audit.records[0]["detail"]["target_user_id"] == "worker42"

