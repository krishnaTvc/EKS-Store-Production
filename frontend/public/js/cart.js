/**
 * EKS Beverage Store - Cart State Management
 * Handles cart items, quantities, local storage persistence, and totals.
 */

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

export const cart = new CartManager();
