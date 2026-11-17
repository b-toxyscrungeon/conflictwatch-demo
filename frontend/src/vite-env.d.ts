/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** "1" builds the static GitHub Pages demo that reads frontend/public/data/. */
  readonly VITE_STATIC?: string;
  /** GoatCounter site code; enables the daily visitor counter when set. */
  readonly VITE_GOATCOUNTER?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
