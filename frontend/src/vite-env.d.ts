/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** "1" builds the static GitHub Pages demo that reads frontend/public/data/. */
  readonly VITE_STATIC?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
