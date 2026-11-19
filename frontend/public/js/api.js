/**
 * EKS Beverage Store - API Client Module
 * Provides unified communication with catalog-service (:8001) and order-service (:8002).
 * Automatically supports Nginx reverse proxy routes or direct localhost URLs.
 */

class ApiClient {
  constructor() {
    // Determine backend URLs
    // If running under Nginx or ALB, relative URLs (/api/catalog, /api/orders) will route automatically.
    // If running in local standalone development, fall back to localhost:8001 and localhost:8002.
    this.catalogBaseUrl = localStorage.getItem('CATALOG_API_URL') || '';
    this.orderBaseUrl = localStorage.getItem('ORDER_API_URL') || '';

    const port = window.location.port;
    const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
    
    // If running on a random local dev port (e.g. 5500, 8080) or file://, use direct ports
    if ((port && port !== '80' && port !== '3000') || !window.location.host) {
      if (!this.catalogBaseUrl) this.catalogBaseUrl = 'http://localhost:8001';
      if (!this.orderBaseUrl) this.orderBaseUrl = 'http://localhost:8002';
    }
  }

  /**
   * Helper that falls back to localhost:8001 / 8002 if relative proxy route is not found
   */
  async request(endpoint, options = {}, isOrderService = false) {
    let baseUrl = isOrderService ? this.orderBaseUrl : this.catalogBaseUrl;
    let url = baseUrl ? `${baseUrl}${endpoint}` : endpoint;

    try {
      let res = await fetch(url, options);
      // If relative URL returned 404 and we're on localhost, try direct port fallback
      if (res.status === 404 && !baseUrl && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')) {
        const fallbackBase = isOrderService ? 'http://localhost:8002' : 'http://localhost:8001';
        if (isOrderService) this.orderBaseUrl = fallbackBase;
        else this.catalogBaseUrl = fallbackBase;
        url = `${fallbackBase}${endpoint}`;
        res = await fetch(url, options);
      }
      return res;
    } catch (err) {
      // Network failure on relative path: try direct port fallback on localhost
      if (!baseUrl && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')) {
        const fallbackBase = isOrderService ? 'http://localhost:8002' : 'http://localhost:8001';
        if (isOrderService) this.orderBaseUrl = fallbackBase;
        else this.catalogBaseUrl = fallbackBase;
        url = `${fallbackBase}${endpoint}`;
        return await fetch(url, options);
      }
      throw err;
    }
  }

  /**
   * Generates a standard UUID v4 for request correlation and idempotency
   */
  generateUUID() {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
      return crypto.randomUUID();
    }
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
      const r = Math.random() * 16 | 0;
      const v = c === 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
  }

  /**
   * Health check for Catalog Service
   */
  async checkCatalogHealth() {
    try {
      const endpoint = this.catalogBaseUrl ? '/health/live' : '/health/catalog';
      const res = await this.request(endpoint, { cache: 'no-store' }, false);
      if (!res.ok) return false;
      const contentType = res.headers.get('content-type') || '';
      if (!contentType.includes('application/json')) return false;
      const data = await res.json();
      return data.status === 'UP' || data.status === 'healthy';
    } catch {
      return false;
    }
  }

  /**
   * Health check for Order Service
   */
  async checkOrderHealth() {
    try {
      const endpoint = this.orderBaseUrl ? '/health/live' : '/health/orders';
      const res = await this.request(endpoint, { cache: 'no-store' }, true);
      if (!res.ok) return false;
      const contentType = res.headers.get('content-type') || '';
      if (!contentType.includes('application/json')) return false;
      const data = await res.json();
      return data.status === 'UP' || data.status === 'healthy';
    } catch {
      return false;
    }
  }

  /**
   * Retrieves unique categories from catalog
   */
  async getCategories() {
    const res = await this.request('/api/catalog/categories', {}, false);
    if (!res.ok) throw new Error(`Failed to load categories: ${res.statusText}`);
    return await res.json();
  }

  /**
   * Retrieves unique bottle sizes (ml) for a given category
   */
  async getSizes(category = null) {
    let endpoint = '/api/catalog/sizes';
    if (category) endpoint += `?category=${encodeURIComponent(category)}`;
    const res = await this.request(endpoint, {}, false);
    if (!res.ok) throw new Error(`Failed to load bottle sizes: ${res.statusText}`);
    return await res.json();
  }

  /**
   * Lists catalog items with search, category/size filter, origin filter, pagination, and sorting
   */
  async getItems({ category, origin_group, size_ml, search, page = 1, limit = 24, sort_by = 'name', sort_order = 'asc' }) {
    const params = new URLSearchParams();
    if (category) params.set('category', category);
    if (origin_group) params.set('origin_group', origin_group);
    if (size_ml) params.set('size_ml', size_ml);
    if (search && search.trim()) params.set('search', search.trim());
    params.set('page', page);
    params.set('limit', limit);
    params.set('sort_by', sort_by);
    params.set('sort_order', sort_order);

    const endpoint = `/api/catalog/items?${params.toString()}`;
    const corrId = this.generateUUID();
    const res = await this.request(endpoint, {
      headers: {
        'X-Correlation-Id': corrId
      }
    }, false);

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Catalog error (${res.status})`);
    }
    return await res.json();
  }

  /**
   * Retrieves single item by UUID
   */
  async getItem(id) {
    const res = await this.request(`/api/catalog/items/${id}`, {}, false);
    if (!res.ok) throw new Error(`Item ${id} not found`);
    return await res.json();
  }

  /**
   * Submits an order to order-service with Idempotency-Key
   */
  async createOrder(customerRef, items, idempotencyKey = null) {
    const key = idempotencyKey || this.generateUUID();
    const corrId = this.generateUUID();

    const payload = {
      customer_ref: customerRef,
      items: items.map(i => ({
        catalog_item_id: i.catalog_item_id || i.id,
        quantity: parseInt(i.quantity, 10)
      }))
    };

    const res = await this.request('/api/orders', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Idempotency-Key': key,
        'X-Correlation-Id': corrId
      },
      body: JSON.stringify(payload)
    }, true);

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Order failed with status ${res.status}`);
    }

    return await res.json();
  }

  /**
   * Retrieves order by UUID
   */
  async getOrder(orderId) {
    const corrId = this.generateUUID();
    const res = await this.request(`/api/orders/${orderId}`, {
      headers: {
        'X-Correlation-Id': corrId
      }
    }, true);

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Order ${orderId} not found`);
    }

    return await res.json();
  }
}

export const api = new ApiClient();
