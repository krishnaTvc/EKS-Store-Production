def test_list_items_default(client):
    response = client.get("/api/catalog/items")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 4  # 4 active items out of 5
    assert len(data["items"]) == 4


def test_category_filtering(client):
    response = client.get("/api/catalog/items?category=whisky")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    for item in data["items"]:
        assert item["category"] == "whisky"


def test_size_filtering(client):
    response = client.get("/api/catalog/items?size_ml=750")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["size_ml"] == 750
    assert data["items"][0]["product_code"] == "1715W1139GQQ"


def test_search_filtering(client):
    response = client.get("/api/catalog/items?search=kingfisher")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert "KINGFISHER" in data["items"][0]["product_name"]


def test_sorting_by_price_desc(client):
    response = client.get("/api/catalog/items?sort_by=price&sort_order=desc")
    assert response.status_code == 200
    items = response.json()["items"]
    prices = [float(i["mrp"]) for i in items]
    assert prices == sorted(prices, reverse=True)


def test_bounded_pagination(client):
    response = client.get("/api/catalog/items?limit=2&page=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["total"] == 4
    assert data["total_pages"] == 2


def test_get_item_by_id(client):
    response = client.get("/api/catalog/items/11111111-1111-1111-1111-111111111111")
    assert response.status_code == 200
    item = response.json()
    assert item["product_code"] == "1715W1139GNN"
    assert "blenders-pride.jpeg" in item["image_url"]


def test_unmapped_item_returns_placeholder(client):
    response = client.get("/api/catalog/items/44444444-4444-4444-4444-444444444444")
    assert response.status_code == 200
    item = response.json()
    assert item["image_key"] is None
    assert "placeholder.png" in item["image_url"]


def test_get_item_not_found(client):
    response = client.get("/api/catalog/items/99999999-9999-9999-9999-999999999999")
    assert response.status_code == 404


def test_list_categories(client):
    response = client.get("/api/catalog/categories")
    assert response.status_code == 200
    data = response.json()
    assert set(data["categories"]) == {"beer", "brandy", "whisky"}


def test_list_sizes_for_category(client):
    response = client.get("/api/catalog/sizes?category=whisky")
    assert response.status_code == 200
    data = response.json()
    assert data["sizes"] == [180, 750]


def test_health_probes(client):
    # Liveness probe
    live_resp = client.get("/health/live")
    assert live_resp.status_code == 200
    assert live_resp.json()["status"] == "UP"

    # Readiness probe
    ready_resp = client.get("/health/ready")
    assert ready_resp.status_code == 200
    assert ready_resp.json()["status"] == "UP"


def test_metrics_endpoint(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "catalog_http_requests_total" in response.text


def test_origin_group_filtering(client):
    # Test domestic tab filter
    dom_resp = client.get("/api/catalog/items?origin_group=domestic")
    assert dom_resp.status_code == 200
    dom_data = dom_resp.json()
    assert dom_data["total"] == 3
    for item in dom_data["items"]:
        assert item["origin_group"] == "domestic"

    # Test foreign tab filter
    for_resp = client.get("/api/catalog/items?origin_group=foreign")
    assert for_resp.status_code == 200
    for_data = for_resp.json()
    assert for_data["total"] == 1
    assert for_data["items"][0]["origin_group"] == "foreign"
    assert for_data["items"][0]["country_of_origin"] == "France"


