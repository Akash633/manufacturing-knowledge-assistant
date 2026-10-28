import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { AuthenticatedProfile } from '../types';
import { api, ApiError } from '../services/api';
import { oidcConfigured, oidcManager } from '../services/oidc';

type AuthStatus = 'checking' | 'unconfigured' | 'signed_out' | 'authenticated' | 'error';

interface AuthContextValue {
  status: AuthStatus;
  profile: AuthenticatedProfile | null;
  message: string | null;
  can: (...roles: string[]) => boolean;
  signIn: () => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue>({
  status: 'checking',
  profile: null,
  message: null,
  can: () => false,
  signIn: async () => undefined,
  signOut: async () => undefined,
});

export const AuthProvider: React.FC<React.PropsWithChildren> = ({ children }) => {
  const [status, setStatus] = useState<AuthStatus>('checking');
  const [profile, setProfile] = useState<AuthenticatedProfile | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    const initialize = async () => {
      if (!oidcConfigured || !oidcManager) {
        setStatus('unconfigured');
        return;
      }

      try {
        const callbackPath = new URL(oidcManager.settings.redirect_uri).pathname;
        const user = window.location.pathname === callbackPath
          ? await oidcManager.signinRedirectCallback()
          : await oidcManager.getUser();

        if (window.location.pathname === callbackPath) {
          window.history.replaceState({}, document.title, window.location.origin);
        }

        if (!active) return;
        if (!user || user.expired) {
          setStatus('signed_out');
          return;
        }

        const verifiedProfile = await api.getCurrentUser(user.access_token);
        if (!active) return;
        setProfile(verifiedProfile);
        setStatus('authenticated');
        setMessage(null);
      } catch (error) {
        if (!active) return;
        const statusCode = error instanceof ApiError ? error.status : undefined;
        setStatus('error');
        setMessage(
          statusCode === 503
            ? 'The backend identity service is not configured or is unavailable.'
            : 'Sign-in could not be verified by the backend. Protected actions remain disabled.',
        );
      }
    };

    void initialize();
    return () => {
      active = false;
    };
  }, []);

  const signIn = async () => {
    if (!oidcManager) {
      setStatus('unconfigured');
      setMessage('Configure the OIDC authority and client ID to enable sign-in.');
      return;
    }
    try {
      const audience = import.meta.env.VITE_OIDC_AUDIENCE?.trim();
      await oidcManager.signinRedirect({
        extraQueryParams: audience ? { audience } : undefined,
      });
    } catch {
      setStatus('error');
      setMessage('The identity provider could not start sign-in.');
    }
  };

  const signOut = async () => {
    if (!oidcManager) return;
    try {
      await oidcManager.signoutRedirect();
    } catch {
      setStatus('error');
      setMessage('The identity provider could not complete sign-out.');
    }
  };

  const value = useMemo<AuthContextValue>(() => ({
    status,
    profile,
    message,
    can: (...roles) => Boolean(
      profile && (
        profile.roles.includes('admin')
        || roles.some((role) => profile.roles.includes(role))
      )
    ),
    signIn,
    signOut,
  }), [status, profile, message]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export function useAuth(): AuthContextValue {
  return useContext(AuthContext);
}
