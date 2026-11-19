"""
Unit & Integration tests verifying Frontend UI assets, Nginx configuration,
DOM structure, and microservice proxy alignment.
"""

import os
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT_DIR / "frontend"
PUBLIC_DIR = FRONTEND_DIR / "public"


def test_frontend_files_exist():
    """Verify all essential frontend files exist in public/ and root frontend/."""
    expected_files = [
        PUBLIC_DIR / "index.html",
        PUBLIC_DIR / "css" / "styles.css",
        PUBLIC_DIR / "js" / "api.js",
        PUBLIC_DIR / "js" / "cart.js",
        PUBLIC_DIR / "js" / "ui.js",
        PUBLIC_DIR / "js" / "app.js",
        PUBLIC_DIR / "assets" / "favicon.svg",
        FRONTEND_DIR / "nginx.conf",
        FRONTEND_DIR / "Dockerfile",
    ]
    for file_path in expected_files:
        assert file_path.is_file(), f"Expected frontend file missing: {file_path}"


def test_index_html_dom_elements():
    """Verify index.html contains all critical DOM elements referenced by JS modules."""
    html_path = PUBLIC_DIR / "index.html"
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    # Parse with standard string or BeautifulSoup if available
    required_ids = [
        "search-input",
        "size-filter",
        "sort-filter",
        "limit-filter",
        "category-pills",
        "results-summary",
        "product-grid",
        "pagination-container",
        "btn-prev-page",
        "btn-next-page",
        "page-indicator",
        "cart-drawer-overlay",
        "btn-open-cart",
        "btn-close-drawer",
        "btn-checkout",
        "cart-items-list",
        "cart-badge",
        "cart-subtotal-val",
        "cart-grand-total-val",
        "customer-ref-input",
        "order-confirmation-modal",
        "order-receipt-content",
        "btn-close-receipt",
        "order-lookup-modal",
        "btn-open-order-lookup",
        "btn-close-lookup",
        "order-lookup-input",
        "btn-submit-lookup",
        "lookup-result-box",
        "toast-container",
        "health-status-dot",
        "health-status-text",
    ]

    for elem_id in required_ids:
        assert f'id="{elem_id}"' in html_content, f"Required DOM element id='{elem_id}' not found in index.html"

    # Check JS script entry point
    assert ('app.bundle.js' in html_content or 'app.js' in html_content)


def test_nginx_configuration_proxies():
    """Verify nginx.conf defines correct proxy passes for microservices and assets."""
    nginx_conf_path = FRONTEND_DIR / "nginx.conf"
    with open(nginx_conf_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "location /api/catalog/" in content
    assert "proxy_pass http://catalog-service:8001/api/catalog/;" in content

    assert "location /api/orders/" in content
    assert "proxy_pass http://order-service:8002/api/orders/;" in content

    assert "location /assets/catalog/" in content
    assert "proxy_pass http://catalog-service:8001/assets/catalog/;" in content

    assert "location = /healthz" in content


def test_dockerfile_and_compose_integration():
    """Verify Dockerfile and docker-compose.yml properly wire the frontend service."""
    dockerfile_path = FRONTEND_DIR / "Dockerfile"
    with open(dockerfile_path, "r", encoding="utf-8") as f:
        df_content = f.read()

    assert "FROM nginx" in df_content
    assert ("EXPOSE 80" in df_content or "EXPOSE 8080" in df_content)

    compose_path = ROOT_DIR / "docker-compose.yml"
    with open(compose_path, "r", encoding="utf-8") as f:
        compose_content = f.read()

    assert "frontend:" in compose_content
    assert ('"3000:80"' in compose_content or '"3000:8080"' in compose_content)
    assert "catalog-service" in compose_content
    assert "order-service" in compose_content
