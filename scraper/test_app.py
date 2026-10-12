import os
import tempfile
import unittest
from unittest.mock import patch

# Use an isolated database so tests never touch the developer's watchlist.
_tmp = tempfile.TemporaryDirectory()
os.environ["DB_FILE"] = os.path.join(_tmp.name, "test.db")

from fastapi.testclient import TestClient
import app

client = TestClient(app.app)


class ApiContractTests(unittest.TestCase):
    def test_health(self):
        response = client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "online")
        self.assertEqual(response.json()["version"], "1.1.0")

    def test_audit_inventory_includes_routes_and_limitations(self):
        response = client.get("/api/audit")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "inventory_only")
        self.assertIn("/api/search", [route["path"] for route in payload["routes"]])
        self.assertIn("/api/stream", [route["path"] for route in payload["routes"]])
        self.assertGreater(payload["route_count"], 10)

    def test_anivault_is_marked_metadata_only(self):
        payload = client.get("/api/providers").json()
        anivault = next(p for p in payload["providers"] if p["id"] == "anivault")
        self.assertIn("metadata only", anivault["mode"])

    def test_unknown_provider_returns_400(self):
        response = client.get("/api/search", params={"platform": "not-a-provider", "q": "test"})
        self.assertEqual(response.status_code, 400)

    def test_search_rejects_empty_query(self):
        response = client.get("/api/search", params={"platform": "anikoto", "q": ""})
        self.assertEqual(response.status_code, 422)

    def test_provider_url_allowlist_rejects_untrusted_host(self):
        with self.assertRaises(app.HTTPException) as caught:
            app.safe_provider_url("https://example.org/watch/1", "anikoto")
        self.assertEqual(caught.exception.status_code, 400)

    def test_anivault_episodes_are_not_fabricated(self):
        response = client.get("/api/episodes", params={
            "platform": "anivault", "url": "https://anilist.co/anime/124080"
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["episodes"], [])
        self.assertIn("does not provide provider episode URLs", response.json()["note"])

    def test_watchlist_round_trip_and_delete(self):
        created = client.post("/api/watchlist", json={
            "platform": "anivault", "title": "Unit Test Anime",
            "url": "https://anilist.co/anime/999999", "poster": ""
        })
        self.assertEqual(created.status_code, 200)
        listed = client.get("/api/watchlist")
        item = next(x for x in listed.json()["watchlist"] if x["title"] == "Unit Test Anime")
        deleted = client.delete(f"/api/watchlist/{item['id']}")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(client.delete(f"/api/watchlist/{item['id']}").status_code, 404)

    def test_servers_does_not_claim_metadata_page_is_video_server(self):
        response = client.get("/api/servers", params={
            "platform": "anivault", "url": "https://anilist.co/anime/124080"
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["servers"], [])


if __name__ == "__main__":
    unittest.main()
