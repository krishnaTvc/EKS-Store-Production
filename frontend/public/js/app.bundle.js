/**
 * EKS Beverage Store - Unified Client Application Bundle
 * Zero-dependency, compatible with file://, http://, and Nginx reverse proxy.
 * Automatically connects to backend microservices (:8001, :8002) and falls back
 * gracefully to local embedded schedule data when services are offline.
 */

(function () {
  'use strict';

  const SVG_BOTTLE_FALLBACK = "data:image/svg+xml;charset=UTF-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%20120%20120%22%20fill%3D%22none%22%3E%3Crect%20width%3D%22120%22%20height%3D%22120%22%20rx%3D%2216%22%20fill%3D%22%23131b2a%22%2F%3E%3Cpath%20d%3D%22M54%2028h12v14l6%2010v38c0%203.3-2.7%206-6%206H54c-3.3%200-6-2.7-6-6V52l6-10V28z%22%20fill%3D%22%23223048%22%20stroke%3D%22%23f59e0b%22%20stroke-width%3D%222%22%2F%3E%3Cpath%20d%3D%22M52%2028h16v4H52z%22%20fill%3D%22%23f59e0b%22%2F%3E%3Ccircle%20cx%3D%2260%22%20cy%3D%2268%22%20r%3D%2210%22%20fill%3D%22%23f59e0b%22%20opacity%3D%220.25%22%2F%3E%3Ctext%20x%3D%2260%22%20y%3D%2272%22%20text-anchor%3D%22middle%22%20fill%3D%22%23f59e0b%22%20font-size%3D%2210%22%20font-family%3D%22sans-serif%22%20font-weight%3D%22bold%22%3EBEV%3C%2Ftext%3E%3C%2Fsvg%3E";

  // ---------------------------------------------------------------------------
  // 1. API Client
  // ---------------------------------------------------------------------------
  class ApiClient {
    constructor() {
      this.catalogBaseUrl = localStorage.getItem('CATALOG_API_URL') || '';
      this.orderBaseUrl = localStorage.getItem('ORDER_API_URL') || '';

      const port = window.location.port;
      // Default to direct localhost ports if running outside Nginx on port 80/3000
      if ((port && port !== '80' && port !== '3000') || !window.location.host) {
        if (!this.catalogBaseUrl) this.catalogBaseUrl = 'http://localhost:8001';
        if (!this.orderBaseUrl) this.orderBaseUrl = 'http://localhost:8002';
      }
    }

    generateUUID() {
      if (typeof crypto !== 'undefined' && crypto.randomUUID) {
        return crypto.randomUUID();
      }
      return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
      });
    }

    async request(endpoint, options = {}, isOrderService = false) {
      let baseUrl = isOrderService ? this.orderBaseUrl : this.catalogBaseUrl;
      let url = baseUrl ? `${baseUrl}${endpoint}` : endpoint;

      try {
        let res = await fetch(url, options);
        if (res.status === 404 && !baseUrl && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')) {
          const fallbackBase = isOrderService ? 'http://localhost:8002' : 'http://localhost:8001';
          if (isOrderService) this.orderBaseUrl = fallbackBase;
          else this.catalogBaseUrl = fallbackBase;
          url = `${fallbackBase}${endpoint}`;
          res = await fetch(url, options);
        }
        return res;
      } catch (err) {
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

    async getCategories() {
      try {
        const res = await this.request('/api/catalog/categories', {}, false);
        if (res.ok) {
          const contentType = res.headers.get('content-type') || '';
          if (contentType.includes('application/json')) return await res.json();
        }
      } catch (e) {
        if (window.location.protocol.startsWith('http')) {
          console.warn('Backend categories unavailable:', e);
        }
      }
      // Fallback from embedded data for file:// preview
      const embedded = window.EMBEDDED_CATALOG || [];
      const cats = [...new Set(embedded.map(i => i.category))].sort();
      return { categories: cats, count: cats.length };
    }

    async getSizes(category = null) {
      try {
        let endpoint = '/api/catalog/sizes';
        if (category) endpoint += `?category=${encodeURIComponent(category)}`;
        const res = await this.request(endpoint, {}, false);
        if (res.ok) {
          const contentType = res.headers.get('content-type') || '';
          if (contentType.includes('application/json')) return await res.json();
        }
      } catch (e) {
        if (window.location.protocol.startsWith('http')) {
          console.warn('Backend sizes unavailable:', e);
        }
      }
      // Fallback from embedded data for file:// preview
      let embedded = window.EMBEDDED_CATALOG || [];
      if (category) embedded = embedded.filter(i => i.category === category);
      const sizes = [...new Set(embedded.map(i => i.size_ml))].sort((a, b) => a - b);
      return { sizes, count: sizes.length };
    }

    async getItems({ category, origin_group, size_ml, search, page = 1, limit = 24, sort_by = 'name', sort_order = 'asc' }) {
      const isHttp = window.location.protocol.startsWith('http');
      try {
        const params = new URLSearchParams();
        if (category) params.set('category', category);
        if (origin_group) params.set('origin_group', origin_group);
        if (size_ml) params.set('size_ml', size_ml);
        if (search && search.trim()) params.set('search', search.trim());
        params.set('page', page);
        params.set('limit', limit);
        params.set('sort_by', sort_by);
        params.set('sort_order', sort_order);

        const res = await this.request(`/api/catalog/items?${params.toString()}`, {
          headers: { 'X-Correlation-Id': this.generateUUID() }
        }, false);

        if (res.ok) {
          const contentType = res.headers.get('content-type') || '';
          if (contentType.includes('application/json')) {
            const data = await res.json();
            data.is_live = true;
            return data;
          }
        }
        if (isHttp) {
          throw new Error(`Catalog API returned HTTP ${res.status}`);
        }
      } catch (e) {
        if (isHttp) {
          // Disable silent fallback in AWS / EKS mode so backend health is verified
          throw e;
        }
        console.warn('Backend catalog unavailable, using local schedule data:', e);
      }

      // Offline / Fallback filter engine (only for local standalone file:// preview)
      let items = [...(window.EMBEDDED_CATALOG || [])];
      if (origin_group) items = items.filter(i => (i.origin_group || '').toLowerCase() === origin_group.toLowerCase());
      if (category) items = items.filter(i => i.category.toLowerCase() === category.toLowerCase());
      if (size_ml) items = items.filter(i => i.size_ml === parseInt(size_ml, 10));
      if (search && search.trim()) {
        const q = search.trim().toLowerCase();
        items = items.filter(i =>
          i.product_name.toLowerCase().includes(q) ||
          i.product_code.toLowerCase().includes(q) ||
          (i.brand_code && i.brand_code.toLowerCase().includes(q))
        );
      }

      // Sort
      items.sort((a, b) => {
        if (sort_by === 'price') {
          const diff = parseFloat(a.mrp) - parseFloat(b.mrp);
          return sort_order === 'desc' ? -diff : diff;
        }
        const cmp = a.product_name.localeCompare(b.product_name);
        return sort_order === 'desc' ? -cmp : cmp;
      });

      const total = items.length;
      const total_pages = Math.max(1, Math.ceil(total / limit));
      const start = (page - 1) * limit;
      const paginated = items.slice(start, start + limit);

      return {
        items: paginated,
        total,
        page,
        limit,
        total_pages,
        is_live: false
      };
    }

    async createOrder(customerRef, items, idempotencyKey = null) {
      const key = idempotencyKey || this.generateUUID();
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
          'X-Correlation-Id': this.generateUUID()
        },
        body: JSON.stringify(payload)
      }, true);

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Order submission failed (Status ${res.status})`);
      }
      return await res.json();
    }

    async getOrder(orderId) {
      const res = await this.request(`/api/orders/${orderId}`, {
        headers: { 'X-Correlation-Id': this.generateUUID() }
      }, true);

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Order ${orderId} not found`);
      }
      return await res.json();
    }
  }

  const api = new ApiClient();

  // ---------------------------------------------------------------------------
  // 2. Cart State Manager
  // ---------------------------------------------------------------------------
  class CartManager {
    constructor() {
      this.STORAGE_KEY = 'eks_beverage_store_cart';
      this.listeners = [];
      this.items = this.load();
    }

    load() {
      try {
        const data = localStorage.getItem(this.STORAGE_KEY);
        return data ? JSON.parse(data) : [];
      } catch {
        return [];
      }
    }

    save() {
      try {
        localStorage.setItem(this.STORAGE_KEY, JSON.stringify(this.items));
      } catch (e) {
        console.error('Failed to save cart to localStorage', e);
      }
      this.notify();
    }

    subscribe(callback) {
      this.listeners.push(callback);
      callback(this.getItems(), this.getTotals());
    }

    notify() {
      const items = this.getItems();
      const totals = this.getTotals();
      this.listeners.forEach(cb => cb(items, totals));
    }

    getItems() {
      return [...this.items];
    }

    addItem(product, quantity = 1) {
      const existingIndex = this.items.findIndex(i => i.id === product.id);
      if (existingIndex > -1) {
        this.items[existingIndex].quantity += quantity;
      } else {
        this.items.push({
          id: product.id,
          catalog_item_id: product.id,
          product_code: product.product_code,
          product_name: product.product_name,
          category: product.category,
          size_ml: product.size_ml,
          mrp: parseFloat(product.mrp),
          image_url: product.image_url,
          quantity: quantity
        });
      }
      this.save();
    }

    updateQuantity(productId, quantity) {
      const index = this.items.findIndex(i => i.id === productId);
      if (index > -1) {
        if (quantity <= 0) {
          this.items.splice(index, 1);
        } else {
          this.items[index].quantity = quantity;
        }
        this.save();
      }
    }

    removeItem(productId) {
      this.items = this.items.filter(i => i.id !== productId);
      this.save();
    }

    clear() {
      this.items = [];
      this.save();
    }

    getTotals() {
      const totalCount = this.items.reduce((sum, item) => sum + item.quantity, 0);
      const subtotal = this.items.reduce((sum, item) => sum + (item.mrp * item.quantity), 0);
      return {
        totalCount,
        subtotal: subtotal.toFixed(2),
        formattedSubtotal: new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(subtotal)
      };
    }
  }

  const cart = new CartManager();

  // ---------------------------------------------------------------------------
  // 3. UI View Helpers
  // ---------------------------------------------------------------------------
  const ui = {
    formatCurrency(amount) {
      const num = typeof amount === 'string' ? parseFloat(amount) : amount;
      return new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: 'INR',
        maximumFractionDigits: 2
      }).format(num);
    },

    showToast(message, type = 'info') {
      let container = document.getElementById('toast-container');
      if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container';
        document.body.appendChild(container);
      }

      const toast = document.createElement('div');
      toast.className = `toast ${type}`;

      let icon = 'ℹ️';
      if (type === 'success') icon = '✅';
      if (type === 'error') icon = '⚠️';

      toast.innerHTML = `<span>${icon}</span><span>${message}</span>`;
      container.appendChild(toast);

      requestAnimationFrame(() => toast.classList.add('show'));

      setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
      }, 3500);
    },

    renderCategories(categories, activeCategory, onSelect) {
      const container = document.getElementById('category-pills');
      if (!container) return;

      container.innerHTML = '';

      // "All" chip
      const allChip = document.createElement('button');
      allChip.className = `category-chip ${!activeCategory ? 'active' : ''}`;
      allChip.innerHTML = `All Beverages`;
      allChip.onclick = () => onSelect(null);
      container.appendChild(allChip);

      categories.forEach(cat => {
        const chip = document.createElement('button');
        chip.className = `category-chip ${activeCategory === cat ? 'active' : ''}`;
        chip.innerHTML = `${cat.charAt(0).toUpperCase() + cat.slice(1)}`;
        chip.onclick = () => onSelect(cat);
        container.appendChild(chip);
      });
    },

    renderProductGrid(items, onAddToCart) {
      const grid = document.getElementById('product-grid');
      if (!grid) return;

      if (!items || items.length === 0) {
        grid.innerHTML = `
          <div style="grid-column: 1/-1; text-align: center; padding: 4rem 1rem; color: var(--text-muted);">
            <div style="font-size: 3rem; margin-bottom: 1rem;">🍷</div>
            <h3>No beverages match your search or filter criteria</h3>
            <p style="margin-top: 0.5rem; font-size: 0.9rem;">Try selecting a different category or clearing search terms.</p>
          </div>
        `;
        return;
      }

      grid.innerHTML = items.map(item => {
        const formattedPrice = this.formatCurrency(item.mrp);
        const subcat = item.subcategory ? ` • ${item.subcategory}` : '';
        const fallbackPlaceholder = 'assets/catalog/placeholder.png';

        let imgSrc = item.image_url;
        if (!imgSrc || imgSrc.includes('placeholder')) {
          imgSrc = fallbackPlaceholder;
        } else if (imgSrc.startsWith('/')) {
          imgSrc = imgSrc.replace(/^\/+/, '');
        }

        return `
          <article class="product-card" data-id="${item.id}">
            <div class="card-img-wrap">
              <span class="category-badge">${item.category}${subcat}</span>
              <span class="origin-badge ${item.origin_group || 'domestic'}">${item.origin_group === 'foreign' ? 'Foreign' : 'Domestic'}</span>
              <span class="size-badge">${item.size_ml} ml</span>
              <img 
                src="${imgSrc}" 
                alt="${item.product_name}" 
                loading="lazy"
                onerror="this.onerror=null; this.src='${fallbackPlaceholder}'; this.onerror=() => { this.src='${SVG_BOTTLE_FALLBACK}'; };"
              />
            </div>
            <div class="card-body">
              <div class="card-meta">
                <span>Code: <strong>${item.product_code}</strong></span>
                <span>•</span>
                <span>Brand: <strong>#${item.brand_code}</strong></span>
                ${item.country_of_origin ? `<span>•</span><span><strong>${item.country_of_origin}</strong></span>` : ''}
              </div>
              <h3 class="product-title" title="${item.product_name}">${item.product_name}</h3>
              <div class="card-footer">
                <div class="price-box">
                  <span class="price-label">Govt. MRP</span>
                  <span class="price-value">${formattedPrice}</span>
                </div>
                <button class="btn-add-cart" data-id="${item.id}">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"></path>
                    <line x1="3" y1="6" x2="21" y2="6"></line>
                    <path d="M16 10a4 4 0 0 1-8 0"></path>
                  </svg>
                  Add
                </button>
              </div>
            </div>
          </article>
        `;
      }).join('');

      // Add click handlers
      grid.querySelectorAll('.btn-add-cart').forEach(btn => {
        btn.addEventListener('click', (e) => {
          const id = e.currentTarget.getAttribute('data-id');
          const item = items.find(i => String(i.id) === String(id));
          if (item) onAddToCart(item);
        });
      });
    },

    renderCartDrawer(cartItems, totals, onUpdateQty, onRemove) {
      const list = document.getElementById('cart-items-list');
      const badge = document.getElementById('cart-badge');
      const subtotalDisplay = document.getElementById('cart-subtotal-val');
      const totalDisplay = document.getElementById('cart-grand-total-val');
      const checkoutBtn = document.getElementById('btn-checkout');

      if (badge) badge.textContent = totals.totalCount;
      if (subtotalDisplay) subtotalDisplay.textContent = totals.formattedSubtotal;
      if (totalDisplay) totalDisplay.textContent = totals.formattedSubtotal;
      if (checkoutBtn) checkoutBtn.disabled = cartItems.length === 0;

      if (!list) return;

      if (cartItems.length === 0) {
        list.innerHTML = `
          <div style="text-align: center; padding: 3rem 1rem; color: var(--text-muted);">
            <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">🛒</div>
            <p>Your shopping cart is empty.</p>
            <span style="font-size: 0.8rem;">Browse the catalog and add items.</span>
          </div>
        `;
        return;
      }

      const fallbackPlaceholder = 'assets/catalog/placeholder.png';
      list.innerHTML = cartItems.map(item => {
        const lineTotal = this.formatCurrency(item.mrp * item.quantity);
        let imgSrc = item.image_url || fallbackPlaceholder;
        if (imgSrc.startsWith('/')) imgSrc = imgSrc.replace(/^\/+/, '');

        return `
          <div class="cart-item">
            <div class="cart-item-img">
              <img 
                src="${imgSrc}" 
                alt="${item.product_name}"
                onerror="this.onerror=null; this.src='${fallbackPlaceholder}'; this.onerror=() => { this.src='${SVG_BOTTLE_FALLBACK}'; };"
              />
            </div>
            <div class="cart-item-details">
              <h4 class="cart-item-title" title="${item.product_name}">${item.product_name}</h4>
              <div class="cart-item-meta">${item.size_ml} ml • ${this.formatCurrency(item.mrp)} each</div>
              <div class="cart-item-qty">
                <button class="qty-btn" data-id="${item.id}" data-action="dec">-</button>
                <span class="qty-display">${item.quantity}</span>
                <button class="qty-btn" data-id="${item.id}" data-action="inc">+</button>
              </div>
            </div>
            <div style="text-align: right;">
              <div class="cart-item-price">${lineTotal}</div>
              <button class="btn-remove-item" data-id="${item.id}">Remove</button>
            </div>
          </div>
        `;
      }).join('');

      list.querySelectorAll('.qty-btn').forEach(btn => {
        btn.onclick = (e) => {
          const id = e.currentTarget.getAttribute('data-id');
          const action = e.currentTarget.getAttribute('data-action');
          const item = cartItems.find(i => String(i.id) === String(id));
          if (item) {
            const newQty = action === 'inc' ? item.quantity + 1 : item.quantity - 1;
            onUpdateQty(id, newQty);
          }
        };
      });

      list.querySelectorAll('.btn-remove-item').forEach(btn => {
        btn.onclick = (e) => {
          const id = e.currentTarget.getAttribute('data-id');
          onRemove(id);
        };
      });
    },

    renderOrderReceiptModal(order) {
      const modal = document.getElementById('order-confirmation-modal');
      const body = document.getElementById('order-receipt-content');
      if (!modal || !body) return;

      const formattedTotal = this.formatCurrency(order.total_amount);
      const dateFormatted = new Date(order.created_at).toLocaleString('en-IN', {
        dateStyle: 'medium',
        timeStyle: 'medium'
      });

      body.innerHTML = `
        <div class="receipt-details">
          <div class="receipt-row"><span>Order ID:</span><span><code>${order.id}</code></span></div>
          <div class="receipt-row"><span>Idempotency Key:</span><span><code>${order.idempotency_key}</code></span></div>
          <div class="receipt-row"><span>Customer Ref:</span><span>${order.customer_ref}</span></div>
          <div class="receipt-row"><span>Status:</span><span style="color: var(--success); font-weight: 800;">${order.status}</span></div>
          <div class="receipt-row"><span>Created At:</span><span>${dateFormatted}</span></div>
        </div>

        <h4 style="font-size: 0.9rem; margin-bottom: 0.5rem; color: var(--text-secondary); text-transform: uppercase;">
          Immutable Purchased Item Snapshots
        </h4>
        <table class="receipt-items-table">
          <thead>
            <tr><th>Product Snapshot</th><th>Size</th><th>Qty</th><th>Price</th><th style="text-align: right;">Total</th></tr>
          </thead>
          <tbody>
            ${order.items.map(i => `
              <tr>
                <td><strong>${i.product_name}</strong><div style="font-size: 0.75rem; color: var(--text-muted);">${i.product_code}</div></td>
                <td>${i.size_ml} ml</td>
                <td>${i.quantity}</td>
                <td>${this.formatCurrency(i.unit_price)}</td>
                <td style="text-align: right; font-weight: 700; color: #fbbf24;">${this.formatCurrency(i.line_total)}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>

        <div class="receipt-row" style="font-size: 1.15rem; font-weight: 800; border-top: 1px solid var(--border-color); padding-top: 0.75rem;">
          <span>Grand Total (INR):</span>
          <span style="color: #fbbf24;">${formattedTotal}</span>
        </div>
      `;

      modal.classList.add('open');
    }
  };

  // ---------------------------------------------------------------------------
  // 4. Main Application Controller
  // ---------------------------------------------------------------------------
  const state = {
    category: null,
    origin_group: '',
    size_ml: null,
    search: '',
    sort_by: 'name',
    sort_order: 'asc',
    page: 1,
    limit: 24,
    total_items: 0,
    total_pages: 1,
    categories: [],
    sizes: [],
    is_live: false
  };

  // DOM Elements
  const searchInput = document.getElementById('search-input');
  const sizeSelect = document.getElementById('size-filter');
  const sortSelect = document.getElementById('sort-filter');
  const limitSelect = document.getElementById('limit-filter');
  const resultsSummary = document.getElementById('results-summary');
  const btnPrevPage = document.getElementById('btn-prev-page');
  const btnNextPage = document.getElementById('btn-next-page');
  const pageIndicator = document.getElementById('page-indicator');
  const cartDrawerOverlay = document.getElementById('cart-drawer-overlay');
  const btnOpenCart = document.getElementById('btn-open-cart');
  const btnCloseCart = document.getElementById('btn-close-drawer');
  const btnCheckout = document.getElementById('btn-checkout');
  const customerRefInput = document.getElementById('customer-ref-input');
  const btnOpenOrderLookup = document.getElementById('btn-open-order-lookup');
  const orderLookupModal = document.getElementById('order-lookup-modal');
  const btnCloseLookup = document.getElementById('btn-close-lookup');
  const btnSubmitLookup = document.getElementById('btn-submit-lookup');
  const orderLookupInput = document.getElementById('order-lookup-input');
  const lookupResultBox = document.getElementById('lookup-result-box');
  const orderConfirmModal = document.getElementById('order-confirmation-modal');
  const btnCloseReceipt = document.getElementById('btn-close-receipt');
  const statusDot = document.getElementById('health-status-dot');
  const statusText = document.getElementById('health-status-text');

  async function checkSystemHealth() {
    const [catalogOk, orderOk] = await Promise.all([
      api.checkCatalogHealth(),
      api.checkOrderHealth()
    ]);

    if (statusDot && statusText) {
      if (catalogOk && orderOk) {
        statusDot.className = 'status-dot';
        statusDot.style.background = 'var(--success)';
        statusText.textContent = 'All Microservices Operational';
      } else if (catalogOk || orderOk) {
        statusDot.className = 'status-dot';
        statusDot.style.background = 'var(--warning)';
        statusText.textContent = catalogOk ? 'Order Service Degraded' : 'Catalog Service Degraded';
      } else {
        statusDot.className = 'status-dot down';
        statusDot.style.background = 'var(--danger)';
        statusText.textContent = 'Microservices Offline (Demo Mode)';
      }
    }
  }

  async function loadMetadata() {
    try {
      const [catData, sizeData] = await Promise.all([
        api.getCategories(),
        api.getSizes(state.category)
      ]);
      state.categories = catData.categories || [];
      state.sizes = sizeData.sizes || [];

      ui.renderCategories(state.categories, state.category, onSelectCategory);
      populateSizeFilter(state.sizes);
    } catch (err) {
      console.error('Failed to load metadata', err);
    }
  }

  function populateSizeFilter(sizes) {
    if (!sizeSelect) return;
    const currentVal = sizeSelect.value;
    sizeSelect.innerHTML = '<option value="">All Sizes</option>';
    sizes.forEach(size => {
      const opt = document.createElement('option');
      opt.value = size;
      opt.textContent = `${size} ml`;
      if (String(size) === String(currentVal)) opt.selected = true;
      sizeSelect.appendChild(opt);
    });
  }

  async function loadCatalog() {
    try {
      const data = await api.getItems({
        category: state.category,
        origin_group: state.origin_group,
        size_ml: state.size_ml,
        search: state.search,
        page: state.page,
        limit: state.limit,
        sort_by: state.sort_by,
        sort_order: state.sort_order
      });

      state.total_items = data.total;
      state.total_pages = data.total_pages;
      state.is_live = data.is_live;

      ui.renderProductGrid(data.items, (item) => {
        cart.addItem(item, 1);
        ui.showToast(`Added ${item.product_name} (${item.size_ml} ml) to cart`, 'success');
      });

      if (btnCheckout) btnCheckout.disabled = false;
      updatePagination();
    } catch (err) {
      console.error('Error loading catalog from backend:', err);
      const grid = document.getElementById('product-grid');
      if (grid) {
        grid.innerHTML = `
          <div style="grid-column: 1/-1; text-align: center; padding: 4rem 1.5rem; color: var(--danger); background: rgba(239, 68, 68, 0.08); border: 1px solid var(--danger); border-radius: var(--radius-lg); margin: 1rem 0;">
            <div style="font-size: 2.5rem; margin-bottom: 0.75rem;">⚠️</div>
            <h3 style="margin-bottom: 0.5rem; color: #fca5a5;">Catalog Microservice Unavailable</h3>
            <p style="font-size: 0.95rem; color: var(--text-secondary); max-width: 500px; margin: 0 auto;">
              Unable to reach the live EKS/RDS PostgreSQL catalog backend (${err.message}).
              Local fallback is disabled in cloud mode to verify authentic backend integration.
            </p>
          </div>
        `;
      }
      if (resultsSummary) {
        resultsSummary.innerHTML = '<span style="color:var(--danger); font-weight:600;">[Backend Unavailable - Orders Disabled]</span>';
      }
      if (btnCheckout) {
        btnCheckout.disabled = true;
      }
      ui.showToast(`Catalog Error: ${err.message}`, 'error');
    }
  }

  function onSelectCategory(cat) {
    state.category = cat;
    state.page = 1;
    ui.renderCategories(state.categories, state.category, onSelectCategory);
    loadMetadata();
    loadCatalog();
  }

  function updatePagination() {
    if (resultsSummary) {
      const start = state.total_items === 0 ? 0 : (state.page - 1) * state.limit + 1;
      const end = Math.min(state.page * state.limit, state.total_items);
      const modeTag = state.is_live
        ? '<span style="color:var(--success); font-weight:600; margin-left:0.5rem;">[Live EKS Backend]</span>'
        : '<span style="color:var(--warning); font-weight:600; margin-left:0.5rem;">[Local Schedule Cache]</span>';
      resultsSummary.innerHTML = `Showing <strong>${start}–${end}</strong> of <strong>${state.total_items}</strong> beverages ${modeTag}`;
    }

    if (pageIndicator) {
      pageIndicator.textContent = `Page ${state.page} of ${Math.max(1, state.total_pages)}`;
    }

    if (btnPrevPage) btnPrevPage.disabled = state.page <= 1;
    if (btnNextPage) btnNextPage.disabled = state.page >= state.total_pages;
  }

  function setupEventListeners() {
    // Origin Tabs (Domestic vs Foreign)
    const originTabs = document.querySelectorAll('.origin-tab');
    originTabs.forEach(tab => {
      tab.addEventListener('click', () => {
        originTabs.forEach(t => {
          t.classList.remove('active');
          t.setAttribute('aria-selected', 'false');
        });
        tab.classList.add('active');
        tab.setAttribute('aria-selected', 'true');
        state.origin_group = tab.getAttribute('data-origin') || '';
        state.page = 1;
        loadCatalog();
      });
    });

    // Search
    let searchTimeout = null;
    if (searchInput) {
      searchInput.addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
          state.search = e.target.value;
          state.page = 1;
          loadCatalog();
        }, 250);
      });
    }

    // Filters
    if (sizeSelect) {
      sizeSelect.addEventListener('change', (e) => {
        state.size_ml = e.target.value ? parseInt(e.target.value, 10) : null;
        state.page = 1;
        loadCatalog();
      });
    }

    if (sortSelect) {
      sortSelect.addEventListener('change', (e) => {
        const [by, order] = e.target.value.split(':');
        state.sort_by = by;
        state.sort_order = order;
        state.page = 1;
        loadCatalog();
      });
    }

    if (limitSelect) {
      limitSelect.addEventListener('change', (e) => {
        state.limit = parseInt(e.target.value, 10);
        state.page = 1;
        loadCatalog();
      });
    }

    // Pagination
    if (btnPrevPage) {
      btnPrevPage.addEventListener('click', () => {
        if (state.page > 1) {
          state.page--;
          loadCatalog();
          window.scrollTo({ top: 300, behavior: 'smooth' });
        }
      });
    }

    if (btnNextPage) {
      btnNextPage.addEventListener('click', () => {
        if (state.page < state.total_pages) {
          state.page++;
          loadCatalog();
          window.scrollTo({ top: 300, behavior: 'smooth' });
        }
      });
    }

    // Cart Drawer Toggle
    if (btnOpenCart && cartDrawerOverlay) {
      btnOpenCart.addEventListener('click', () => {
        cartDrawerOverlay.classList.add('open');
      });
    }

    if (btnCloseCart && cartDrawerOverlay) {
      btnCloseCart.addEventListener('click', () => {
        cartDrawerOverlay.classList.remove('open');
      });
    }

    if (cartDrawerOverlay) {
      cartDrawerOverlay.addEventListener('click', (e) => {
        if (e.target === cartDrawerOverlay) {
          cartDrawerOverlay.classList.remove('open');
        }
      });
    }

    // Order Lookup Modal Toggle
    if (btnOpenOrderLookup && orderLookupModal) {
      btnOpenOrderLookup.addEventListener('click', () => {
        orderLookupModal.classList.add('open');
        if (orderLookupInput) orderLookupInput.focus();
      });
    }

    if (btnCloseLookup && orderLookupModal) {
      btnCloseLookup.addEventListener('click', () => {
        orderLookupModal.classList.remove('open');
      });
    }

    if (orderLookupModal) {
      orderLookupModal.addEventListener('click', (e) => {
        if (e.target === orderLookupModal) {
          orderLookupModal.classList.remove('open');
        }
      });
    }

    // Order Receipt Modal Close
    if (btnCloseReceipt && orderConfirmModal) {
      btnCloseReceipt.addEventListener('click', () => {
        orderConfirmModal.classList.remove('open');
      });
    }

    if (orderConfirmModal) {
      orderConfirmModal.addEventListener('click', (e) => {
        if (e.target === orderConfirmModal) {
          orderConfirmModal.classList.remove('open');
        }
      });
    }

    // Checkout Action
    if (btnCheckout) {
      btnCheckout.addEventListener('click', async () => {
        const items = cart.getItems();
        if (items.length === 0) return;

        const customerRef = customerRefInput ? customerRefInput.value.trim() : 'table_demo';
        btnCheckout.disabled = true;
        btnCheckout.textContent = 'Submitting Order...';

        try {
          const order = await api.createOrder(customerRef, items);
          cart.clear();
          if (cartDrawerOverlay) cartDrawerOverlay.classList.remove('open');
          ui.renderOrderReceiptModal(order);
          ui.showToast('Order created with immutable snapshots!', 'success');
        } catch (err) {
          console.error('Checkout error:', err);
          ui.showToast(`Order submission: ${err.message}`, 'error');
        } finally {
          btnCheckout.disabled = false;
          btnCheckout.textContent = 'Place Order (Idempotent)';
        }
      });
    }

    // Order Lookup Action
    if (btnSubmitLookup && orderLookupInput && lookupResultBox) {
      btnSubmitLookup.addEventListener('click', async () => {
        const id = orderLookupInput.value.trim();
        if (!id) {
          ui.showToast('Please enter an Order UUID', 'error');
          return;
        }

        lookupResultBox.innerHTML = '<p style="text-align:center;color:var(--text-muted);">Fetching order...</p>';
        try {
          const order = await api.getOrder(id);
          const dateFormatted = new Date(order.created_at).toLocaleString('en-IN');
          lookupResultBox.innerHTML = `
            <div class="receipt-details" style="margin-top:1rem;">
              <div class="receipt-row"><span>Order ID:</span><span><code>${order.id}</code></span></div>
              <div class="receipt-row"><span>Status:</span><span style="color:var(--success);font-weight:bold;">${order.status}</span></div>
              <div class="receipt-row"><span>Customer:</span><span>${order.customer_ref}</span></div>
              <div class="receipt-row"><span>Created:</span><span>${dateFormatted}</span></div>
              <div class="receipt-row"><span>Total:</span><span style="color:#fbbf24;font-weight:bold;">${ui.formatCurrency(order.total_amount)}</span></div>
            </div>
            <table class="receipt-items-table" style="margin-top:1rem;">
              <thead>
                <tr><th>Snapshot</th><th>Size</th><th>Qty</th><th>Price</th><th style="text-align:right;">Total</th></tr>
              </thead>
              <tbody>
                ${order.items.map(i => `
                  <tr>
                    <td><strong>${i.product_name}</strong><br><small style="color:var(--text-muted)">${i.product_code}</small></td>
                    <td>${i.size_ml} ml</td>
                    <td>${i.quantity}</td>
                    <td>${ui.formatCurrency(i.unit_price)}</td>
                    <td style="text-align:right;color:#fbbf24;font-weight:bold;">${ui.formatCurrency(i.line_total)}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          `;
        } catch (err) {
          lookupResultBox.innerHTML = `
            <div style="background:rgba(239,68,68,0.15);border:1px solid var(--danger);padding:1rem;border-radius:var(--radius-md);color:var(--danger);text-align:center;">
              ${err.message}
            </div>
          `;
        }
      });
    }
  }

  function init() {
    // 1. Immediately bind event listeners so user clicks are NEVER ignored
    setupEventListeners();

    // 2. Subscribe cart drawer to state changes
    cart.subscribe((items, totals) => {
      ui.renderCartDrawer(
        items,
        totals,
        (id, qty) => cart.updateQuantity(id, qty),
        (id) => cart.removeItem(id)
      );
    });

    // 3. Initial render of metadata and catalog
    loadMetadata();
    loadCatalog();

    // 4. Check backend health and start periodic polling
    checkSystemHealth();
    setInterval(checkSystemHealth, 15000);
  }

  // Execute immediately if DOM is already parsed, or wait for DOMContentLoaded
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
