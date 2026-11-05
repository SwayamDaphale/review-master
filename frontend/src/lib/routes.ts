import type { ProductSummary } from '../types/api';

export const productPath = (s: Pick<ProductSummary, 'product' | 'variant'>): string =>
  `/app/products/${s.product.id}?v=${s.variant.id}`;
