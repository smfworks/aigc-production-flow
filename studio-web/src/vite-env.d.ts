/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_PACK_BUILDER_URL?: string;
  readonly VITE_API_TOKEN?: string;
  readonly VITE_STUDIO_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
