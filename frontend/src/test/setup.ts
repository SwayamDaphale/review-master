import '@testing-library/jest-dom/vitest';
import { afterEach, beforeAll } from 'vitest';

// jsdom does not implement these browser APIs; the layouts call them on navigation.
beforeAll(() => {
  window.scrollTo = () => undefined;
  Element.prototype.scrollIntoView = () => undefined;
});

afterEach(() => {
  window.localStorage.clear();
});
