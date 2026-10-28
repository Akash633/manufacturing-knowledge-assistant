/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_DEV_API_TARGET?: string;
  readonly VITE_OIDC_AUTHORITY?: string;
  readonly VITE_OIDC_CLIENT_ID?: string;
  readonly VITE_OIDC_AUDIENCE?: string;
  readonly VITE_OIDC_SCOPE?: string;
  readonly VITE_OIDC_REDIRECT_URI?: string;
  readonly VITE_OIDC_POST_LOGOUT_REDIRECT_URI?: string;
}
