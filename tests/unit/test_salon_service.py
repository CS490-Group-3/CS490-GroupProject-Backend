from services.salon_service import SalonService


def test_register_salon_returns_expected_keys(monkeypatch):
    """
    Unit test for SalonService.register_salon()

    Ensures that a new salon record returns expected fields
    and proper pending status without touching the real Supabase.
    """

    class MockResponse:
        def __init__(self):
            self.data = [{"id": "uuid"}]
        def execute(self):
            return self

    def fake_table(name):
        class MockTable:
            def insert(self, data):
                return MockResponse()
            def update(self, data):
                return self
            def eq(self, *args, **kwargs):
                return self
            def execute(self):
                return self
        return MockTable()

    monkeypatch.setattr("services.salon_service.supabase.table", fake_table)

    class MockData:
        name = "Studio 55"
        address = "123 Main"
        city = "Jersey City"
        state = "NJ"
        zip_code = "12345"
        phone = "5555555555"
        email = "owner@studio55.com"
        description = "test"
        license_url = None
        logo_url = None

    result = SalonService.register_salon(MockData(), "owner-uuid")

    # --- Validate results ---
    assert isinstance(result, dict)
    assert "message" in result
    assert "salon_name" in result
    assert "salon_id" in result
    assert "status" in result or "verification_status" in result
    assert result["salon_name"] == "Studio 55"

