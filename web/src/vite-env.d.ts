/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_BUYER_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
