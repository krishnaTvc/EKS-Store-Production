/**
 * EKS Beverage Store - Main Application Controller
 */

import { api } from './api.js';
import { cart } from './cart.js';
import { ui } from './ui.js';

// Application State
const state = {
  category: null,
  size_ml: null,
  search: '',
  sort_by: 'name',
  sort_order: 'asc',
  page: 1,
  limit: 24,
  total_items: 0,
  total_pages: 1,
  categories: [],
  sizes: []
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

/**
 * Initializes the application
 */
async function init() {
  setupEventListeners();
  subscribeCart();
  await checkSystemHealth();
  await loadMetadata();
  await loadCatalog();
  
  // Periodic health check
  setInterval(checkSystemHealth, 20000);
}

/**
 * Checks backend health
 */
async function checkSystemHealth() {
  const [catalogOk, orderOk] = await Promise.all([
    api.checkCatalogHealth(),
    api.checkOrderHealth()
  ]);

  if (statusDot && statusText) {
    if (catalogOk && orderOk) {
      statusDot.className = 'status-dot';
      statusText.textContent = 'All Microservices Operational';
    } else if (catalogOk || orderOk) {
      statusDot.className = 'status-dot';
      statusDot.style.background = 'var(--warning)';
      statusText.textContent = catalogOk ? 'Order Service Degraded' : 'Catalog Service Degraded';
    } else {
      statusDot.className = 'status-dot down';
      statusText.textContent = 'Backend Microservices Offline';
    }
  }
}

/**
 * Loads metadata (categories, sizes)
 */
async function loadMetadata() {
  try {
    const [catData, sizeData] = await Promise.all([
      api.getCategories(),
      api.getSizes()
    ]);
    state.categories = catData.categories || [];
    state.sizes = sizeData.sizes || [];

    ui.renderCategories(state.categories, state.category, onSelectCategory);
    populateSizeFilter(state.sizes);
  } catch (err) {
    console.error('Failed to load catalog metadata', err);
  }
}

function populateSizeFilter(sizes) {
  if (!sizeSelect) return;
  sizeSelect.innerHTML = '<option value="">All Sizes</option>';
  sizes.forEach(size => {
    const opt = document.createElement('option');
    opt.value = size;
    opt.textContent = `${size} ml`;
    sizeSelect.appendChild(opt);
  });
}

/**
 * Fetches and displays catalog items based on current state
 */
async function loadCatalog() {
  try {
    const data = await api.getItems({
      category: state.category,
      size_ml: state.size_ml,
      search: state.search,
      page: state.page,
      limit: state.limit,
      sort_by: state.sort_by,
      sort_order: state.sort_order
    });

    state.total_items = data.total;
    state.total_pages = data.total_pages;

    ui.renderProductGrid(data.items, (item) => {
      cart.addItem(item, 1);
      ui.showToast(`Added ${item.product_name} (${item.size_ml} ml) to cart`, 'success');
    });

    updatePagination();
  } catch (err) {
    console.error('Error loading catalog items:', err);
    if (resultsSummary) {
      resultsSummary.innerHTML = `<span style="color: var(--danger);">⚠️ Connection error: ${err.message}</span>`;
    }
    ui.renderErrorGrid(`Failed to load catalog items (${err.message}). The frontend is attempting to reach the catalog-service API.`, () => {
      loadMetadata();
      loadCatalog();
    });
    ui.showToast(`Error connecting to catalog: ${err.message}`, 'error');
  }
}

function onSelectCategory(cat) {
  state.category = cat;
  state.page = 1;
  ui.renderCategories(state.categories, state.category, onSelectCategory);
  loadCatalog();
}

function updatePagination() {
  if (resultsSummary) {
    const start = state.total_items === 0 ? 0 : (state.page - 1) * state.limit + 1;
    const end = Math.min(state.page * state.limit, state.total_items);
    resultsSummary.innerHTML = `Showing <strong>${start}–${end}</strong> of <strong>${state.total_items}</strong> beverages`;
  }

  if (pageIndicator) {
    pageIndicator.textContent = `Page ${state.page} of ${Math.max(1, state.total_pages)}`;
  }

  if (btnPrevPage) btnPrevPage.disabled = state.page <= 1;
  if (btnNextPage) btnNextPage.disabled = state.page >= state.total_pages;
}

/**
 * Subscribes cart updates to UI
 */
function subscribeCart() {
  cart.subscribe((items, totals) => {
    ui.renderCartDrawer(
      items,
      totals,
      (id, qty) => cart.updateQuantity(id, qty),
      (id) => cart.removeItem(id)
    );
  });
}

/**
 * Sets up all DOM Event Listeners
 */
function setupEventListeners() {
  // Search input debounced
  let searchTimeout = null;
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => {
        state.search = e.target.value;
        state.page = 1;
        loadCatalog();
      }, 300);
    });
  }

  // Size filter
  if (sizeSelect) {
    sizeSelect.addEventListener('change', (e) => {
      state.size_ml = e.target.value ? parseInt(e.target.value, 10) : null;
      state.page = 1;
      loadCatalog();
    });
  }

  // Sort filter
  if (sortSelect) {
    sortSelect.addEventListener('change', (e) => {
      const [by, order] = e.target.value.split(':');
      state.sort_by = by;
      state.sort_order = order;
      state.page = 1;
      loadCatalog();
    });
  }

  // Items per page
  if (limitSelect) {
    limitSelect.addEventListener('change', (e) => {
      state.limit = parseInt(e.target.value, 10);
      state.page = 1;
      loadCatalog();
    });
  }

  // Pagination buttons
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

  // Cart Drawer toggling
  if (btnOpenCart) {
    btnOpenCart.addEventListener('click', () => {
      cartDrawerOverlay.classList.add('open');
    });
  }

  if (btnCloseCart) {
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

  // Checkout submission
  if (btnCheckout) {
    btnCheckout.addEventListener('click', async () => {
      const items = cart.getItems();
      if (items.length === 0) return;

      const customerRef = customerRefInput?.value.trim() || 'demo_customer_andhra';

      btnCheckout.disabled = true;
      btnCheckout.innerHTML = `
        <svg class="spinner" width="20" height="20" viewBox="0 0 50 50" style="animation: spin 1s linear infinite;">
          <circle cx="25" cy="25" r="20" fill="none" stroke="currentColor" stroke-width="5" stroke-dasharray="31.4 31.4"></circle>
        </svg>
        Creating Order...
      `;

      try {
        const order = await api.createOrder(customerRef, items);
        cart.clear();
        cartDrawerOverlay.classList.remove('open');
        ui.renderOrderReceiptModal(order);
        ui.showToast('Order successfully created with immutable snapshots!', 'success');
      } catch (err) {
        console.error('Order creation failed:', err);
        ui.showToast(`Order submission failed: ${err.message}`, 'error');
      } finally {
        btnCheckout.disabled = false;
        btnCheckout.innerHTML = `Place Order (Idempotent)`;
      }
    });
  }

  // Close Order Confirmation Modal
  if (btnCloseReceipt && orderConfirmModal) {
    btnCloseReceipt.addEventListener('click', () => {
      orderConfirmModal.classList.remove('open');
    });
  }

  // Order Lookup Modal open/close
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

  // Order Lookup Submit
  if (btnSubmitLookup && orderLookupInput && lookupResultBox) {
    btnSubmitLookup.addEventListener('click', async () => {
      const orderId = orderLookupInput.value.trim();
      if (!orderId) {
        ui.showToast('Please enter a valid Order UUID', 'error');
        return;
      }

      lookupResultBox.innerHTML = '<p style="color: var(--text-muted); text-align: center;">Fetching order snapshot from order-service...</p>';

      try {
        const order = await api.getOrder(orderId);
        const formattedTotal = ui.formatCurrency(order.total_amount);
        const dateFormatted = new Date(order.created_at).toLocaleString('en-IN');

        lookupResultBox.innerHTML = `
          <div class="receipt-details" style="margin-top: 1rem;">
            <div class="receipt-row"><span>Order ID:</span><span><code>${order.id}</code></span></div>
            <div class="receipt-row"><span>Status:</span><span style="color: var(--success); font-weight: bold;">${order.status}</span></div>
            <div class="receipt-row"><span>Customer:</span><span>${order.customer_ref}</span></div>
            <div class="receipt-row"><span>Created:</span><span>${dateFormatted}</span></div>
            <div class="receipt-row"><span>Total:</span><span style="color: #fbbf24; font-weight: bold;">${formattedTotal}</span></div>
          </div>
          <table class="receipt-items-table" style="margin-top: 1rem;">
            <thead>
              <tr><th>Item Snapshot</th><th>Size</th><th>Qty</th><th>Price</th><th style="text-align: right;">Total</th></tr>
            </thead>
            <tbody>
              ${order.items.map(i => `
                <tr>
                  <td><strong>${i.product_name}</strong><br><small style="color:var(--text-muted)">${i.product_code}</small></td>
                  <td>${i.size_ml} ml</td>
                  <td>${i.quantity}</td>
                  <td>${ui.formatCurrency(i.unit_price)}</td>
                  <td style="text-align: right; color:#fbbf24; font-weight:bold;">${ui.formatCurrency(i.line_total)}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        `;
      } catch (err) {
        lookupResultBox.innerHTML = `
          <div style="background: rgba(239, 68, 68, 0.15); border: 1px solid var(--danger); padding: 1rem; border-radius: var(--radius-md); color: var(--danger); text-align: center;">
            ${err.message}
          </div>
        `;
      }
    });
  }
}

// Start app on DOMContentLoaded
document.addEventListener('DOMContentLoaded', init);
