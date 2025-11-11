from middleware.auth import login_required, role_required
from config import supabase
import uuid

def test_full_approval_workflow(client, mock_supabase):
    # Salon applies
    mock_id = str(uuid.uuid4())

    res = client.post("/api/salons/apply", json={
        "name": "Hype Hair",
        "address": "321 Main",
        "city": "Jersey City",
        "state": "NJ",
        "zip_code": "07001",
        "phone": "5555555555",
        "email": "owner@test.com"
    })
    assert res.status_code == 201
    mock_supabase["salons"][-1]["id"] = mock_id
    salon_id = mock_id

    #  Admin views pending
    res = client.get("/api/salons/pending")
    assert res.status_code == 200
    assert any(s["name"] == "Hype Hair" for s in mock_supabase["salons"])

    #  Admin rejects
    res = client.patch(f"/api/salons/{salon_id}/reject", json={"reason": "Incomplete docs"})
    assert res.status_code == 200
    assert any(n["title"] == "Salon Denied" for n in mock_supabase["notifications"])

    #  Owner appeals
    res = client.put(f"/api/salons/{salon_id}/appeal", json={"updates": {"description": "Fixed"}})
    assert res.status_code == 200
    assert any(n["title"] == "Salon Appeal submitted" for n in mock_supabase["notifications"])

    #  Admin approves
    res = client.patch(f"/api/salons/{salon_id}/approve")
    assert res.status_code == 200
    assert any(n["title"] == "Salon Approved" for n in mock_supabase["notifications"])

    # Check history
    res = client.get(f"/api/salons/{uuid.UUID(salon_id)}/status-history")
    assert res.status_code == 200

