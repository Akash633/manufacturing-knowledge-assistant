import { UserManager, WebStorageStateStore } from 'oidc-client-ts';

const authority = import.meta.env.VITE_OIDC_AUTHORITY?.trim();
const clientId = import.meta.env.VITE_OIDC_CLIENT_ID?.trim();
const redirectUri =
  import.meta.env.VITE_OIDC_REDIRECT_URI?.trim() ||
  `${window.location.origin}/auth/callback`;
const postLogoutRedirectUri =
  import.meta.env.VITE_OIDC_POST_LOGOUT_REDIRECT_URI?.trim() ||
  window.location.origin;

export const oidcConfigured = Boolean(authority && clientId);

export const oidcManager = oidcConfigured
  ? new UserManager({
      authority,
      client_id: clientId,
      redirect_uri: redirectUri,
      post_logout_redirect_uri: postLogoutRedirectUri,
      response_type: 'code',
      scope: import.meta.env.VITE_OIDC_SCOPE?.trim() || 'openid profile email',
      userStore: new WebStorageStateStore({ store: window.sessionStorage }),
      loadUserInfo: false,
      automaticSilentRenew: false,
    })
  : null;

export async function getAccessToken(): Promise<string | undefined> {
  if (!oidcManager) return undefined;
  const user = await oidcManager.getUser();
  return user && !user.expired ? user.access_token : undefined;
}
