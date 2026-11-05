/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_GOOGLE_CLIENT_ID?: string;
  readonly VITE_ADMIN_PASSWORD?: string;
  readonly VITE_USE_MOCK?: string;
  readonly VITE_MOCK_LATENCY_MS?: string;
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
