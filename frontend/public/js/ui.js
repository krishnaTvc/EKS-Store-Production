/**
 * EKS Beverage Store - UI Rendering & View Helpers
 */

const SVG_BOTTLE_FALLBACK = "data:image/svg+xml;charset=UTF-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%20120%20120%22%20fill%3D%22none%22%3E%3Crect%20width%3D%22120%22%20height%3D%22120%22%20rx%3D%2216%22%20fill%3D%22%23131b2a%22%2F%3E%3Cpath%20d%3D%22M54%2028h12v14l6%2010v38c0%203.3-2.7%206-6%206H54c-3.3%200-6-2.7-6-6V52l6-10V28z%22%20fill%3D%22%23223048%22%20stroke%3D%22%23f59e0b%22%20stroke-width%3D%222%22%2F%3E%3Cpath%20d%3D%22M52%2028h16v4H52z%22%20fill%3D%22%23f59e0b%22%2F%3E%3Ccircle%20cx%3D%2260%22%20cy%3D%2268%22%20r%3D%2210%22%20fill%3D%22%23f59e0b%22%20opacity%3D%220.25%22%2F%3E%3Ctext%20x%3D%2260%22%20y%3D%2272%22%20text-anchor%3D%22middle%22%20fill%3D%22%23f59e0b%22%20font-size%3D%2210%22%20font-family%3D%22sans-serif%22%20font-weight%3D%22bold%22%3EBEV%3C%2Ftext%3E%3C%2Fsvg%3E";

export const ui = {
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

  renderErrorGrid(errorMessage, onRetry) {
    const grid = document.getElementById('product-grid');
    if (!grid) return;

    grid.innerHTML = `
      <div style="grid-column: 1/-1; text-align: center; padding: 3.5rem 1.5rem; background: var(--bg-card); border: 1px dashed rgba(239, 68, 68, 0.4); border-radius: var(--radius-lg); margin: 1rem 0;">
        <div style="font-size: 3rem; margin-bottom: 0.75rem;">⚠️</div>
        <h3 style="color: var(--danger); font-size: 1.25rem; font-weight: 700;">Catalog Service Offline or Unreachable</h3>
        <p style="color: var(--text-secondary); margin: 0.5rem auto 1.25rem; max-width: 580px; font-size: 0.9rem;">
          ${errorMessage}
        </p>
        <div style="background: var(--bg-input); border: 1px solid var(--border-color); padding: 1rem; border-radius: var(--radius-md); max-width: 520px; margin: 0 auto 1.5rem; text-align: left; font-size: 0.85rem;">
          <strong style="color: var(--accent);">Quick Resolution Steps:</strong>
          <ol style="margin-left: 1.25rem; margin-top: 0.4rem; line-height: 1.6; color: var(--text-muted);">
            <li>Run <code>python scripts/dev_server.py</code> (or <code>docker-compose up</code>)</li>
            <li>Verify <code>catalog-service</code> is running on <strong>http://localhost:8001</strong></li>
            <li>Ensure database is seeded with <code>python scripts/import_catalog.py</code></li>
          </ol>
        </div>
        <button id="btn-retry-catalog" class="btn-checkout" style="width: auto; padding: 0.65rem 1.75rem; margin: 0 auto; display: inline-flex;">
          🔄 Retry Connection
        </button>
      </div>
    `;

    const btnRetry = document.getElementById('btn-retry-catalog');
    if (btnRetry && onRetry) {
      btnRetry.addEventListener('click', onRetry);
    }
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

      // Ensure image URL resolves properly
      let imgSrc = item.image_url;
      if (!imgSrc || imgSrc.includes('placeholder')) {
        imgSrc = fallbackPlaceholder;
      } else if (imgSrc.startsWith('/')) {
        // Strip leading slash so it resolves relative to frontend assets
        imgSrc = imgSrc.replace(/^\/+/, '');
      }

      return `
        <article class="product-card" data-id="${item.id}">
          <div class="card-img-wrap">
            <span class="category-badge">${item.category}${subcat}</span>
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
              <span>Brand: <strong>#${item.brand_code}</strong></span>
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

    // Attach click handlers to Add buttons
    grid.querySelectorAll('.btn-add-cart').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const id = e.currentTarget.getAttribute('data-id');
        const item = items.find(i => i.id === id);
        if (item) onAddToCart(item);
      });
    });
  },

  renderCartDrawer(cartItems, totals, onUpdateQty, onRemove) {
    const list = document.getElementById('cart-items-list');
    const badge = document.getElementById('cart-badge');
    const miniTotal = document.getElementById('cart-mini-total');
    const subtotalDisplay = document.getElementById('cart-subtotal-val');
    const totalDisplay = document.getElementById('cart-grand-total-val');
    const checkoutBtn = document.getElementById('btn-checkout');

    if (badge) badge.textContent = totals.totalCount;
    if (miniTotal) miniTotal.textContent = totals.formattedSubtotal;
    if (subtotalDisplay) subtotalDisplay.textContent = totals.formattedSubtotal;
    if (totalDisplay) totalDisplay.textContent = totals.formattedSubtotal;

    if (checkoutBtn) {
      checkoutBtn.disabled = cartItems.length === 0;
    }

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

    list.innerHTML = cartItems.map(item => {
      const lineTotal = this.formatCurrency(item.mrp * item.quantity);
      const fallbackPlaceholder = '/assets/catalog/placeholder.png';
      return `
        <div class="cart-item">
          <div class="cart-item-img">
            <img 
              src="${item.image_url || fallbackPlaceholder}" 
              alt="${item.product_name}"
              onerror="this.onerror=null; this.src='${fallbackPlaceholder}';"
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

    // Attach quantity and remove event listeners
    list.querySelectorAll('.qty-btn').forEach(btn => {
      btn.onclick = (e) => {
        const id = e.currentTarget.getAttribute('data-id');
        const action = e.currentTarget.getAttribute('data-action');
        const item = cartItems.find(i => i.id === id);
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
        <div class="receipt-row">
          <span>Order ID:</span>
          <span><code>${order.id}</code></span>
        </div>
        <div class="receipt-row">
          <span>Idempotency Key:</span>
          <span><code>${order.idempotency_key}</code></span>
        </div>
        <div class="receipt-row">
          <span>Customer Ref:</span>
          <span>${order.customer_ref}</span>
        </div>
        <div class="receipt-row">
          <span>Status:</span>
          <span style="color: var(--success); font-weight: 800;">${order.status}</span>
        </div>
        <div class="receipt-row">
          <span>Created At:</span>
          <span>${dateFormatted}</span>
        </div>
      </div>

      <h4 style="font-size: 0.9rem; margin-bottom: 0.5rem; color: var(--text-secondary); text-transform: uppercase;">
        Immutable Purchased Item Snapshots
      </h4>
      <table class="receipt-items-table">
        <thead>
          <tr>
            <th>Product Snapshot</th>
            <th>Size</th>
            <th>Qty</th>
            <th>Price</th>
            <th style="text-align: right;">Total</th>
          </tr>
        </thead>
        <tbody>
          ${order.items.map(i => `
            <tr>
              <td>
                <strong>${i.product_name}</strong>
                <div style="font-size: 0.75rem; color: var(--text-muted);">${i.product_code}</div>
              </td>
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
