import type { ProductItem, Category } from '../types/api';
import { MOCK_PRODUCTS } from './mockData';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

class ReviewMasterApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  async listProducts(category?: Category): Promise<ProductItem[]> {
    try {
      const url = category ? `${this.baseUrl}/api/v1/products?category=${category}` : `${this.baseUrl}/api/v1/products`;
      const res = await fetch(url, { signal: AbortSignal.timeout(1500) });
      if (res.ok) {
        return await res.json();
      }
    } catch {
      // Backend not running locally yet -> fallback smoothly to verified seed data
    }

    if (category) {
      return MOCK_PRODUCTS.filter((p) => p.product.category === category);
    }
    return MOCK_PRODUCTS;
  }

  async getProduct(productId: string): Promise<ProductItem | null> {
    try {
      const res = await fetch(`${this.baseUrl}/api/v1/products/${productId}`, { signal: AbortSignal.timeout(1500) });
      if (res.ok) {
        return await res.json();
      }
    } catch {
      // Fallback to mock
    }

    return MOCK_PRODUCTS.find((p) => p.product.id === productId || p.variant.id === productId) || null;
  }

  async search(query: string): Promise<ProductItem[]> {
    const q = query.trim().toLowerCase();
    if (!q) return this.listProducts();

    try {
      const res = await fetch(`${this.baseUrl}/api/v1/products/search?q=${encodeURIComponent(q)}`, {
        signal: AbortSignal.timeout(1500)
      });
      if (res.ok) {
        return await res.json();
      }
    } catch {
      // Fallback
    }

    return MOCK_PRODUCTS.filter((p) =>
      p.product.name.toLowerCase().includes(q) ||
      p.product.brand.toLowerCase().includes(q) ||
      p.variant.asin?.toLowerCase().includes(q) ||
      p.variant.label.toLowerCase().includes(q)
    );
  }
}

export const api = new ReviewMasterApiClient(BASE_URL);
