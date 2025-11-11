from services.notification_service import NotificationService



def test_broadcast_admins_inserts_notifications(monkeypatch):
    """
    Unit test for NotificationService.broadcast()

    Verifies that:
    - Notifications are inserted for admin users.
    - The broadcast method correctly loops through recipients.
    """

    inserted = []  # store inserted notifications for verification

    # --- Mock Supabase table() behavior ---
    def fake_table(name):
        """
        Mimics supabase.table('...') chain behavior for select(), eq(), execute(), insert().
        """
        class MockTable:
            def insert(self, data):
                inserted.append(data)
                return self

            def select(self, *args, **kwargs):
                return self

            def eq(self, *args, **kwargs):
                return self

            def execute(self):
                # When selecting from "user_profiles", return a fake admin list
                if name == "user_profiles":
                    return type("R", (), {"data": [{"user_id": "admin-uuid"}]})
                # For notifications or others, just return empty
                return type("R", (), {"data": []})
        return MockTable()

    monkeypatch.setattr("services.notification_service.supabase.table", fake_table)

    NotificationService.broadcast(
        recipients=["admins"],
        event_type="general",
        title="Test Notification",
        message="New salon verification event occurred.",
        related_id="salon-1"
    )

    # --- Verify outcomes ---
    assert len(inserted) > 0, "Expected at least one notification to be inserted"
    inserted_record = inserted[0]
    if isinstance(inserted_record, list):
        inserted_record = inserted_record[0]

    assert inserted_record["user_id"] == "admin-uuid"
    assert inserted_record["notification_type"] == "general"
    assert inserted_record["title"] == "Test Notification"
    assert "salon-1" in inserted_record["related_id"]

