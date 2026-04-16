import { createContext, useContext, useReducer, useEffect } from 'react';
import client from '../api/client';

const AuthContext = createContext(null);

const initialState = {
  user: null,
  tenant: null,
  isAuthenticated: false,
  isLoading: true,
};

function authReducer(state, action) {
  switch (action.type) {
    case 'AUTH_SUCCESS':
      return {
        ...state,
        user: action.payload.user,
        tenant: action.payload.tenant,
        isAuthenticated: true,
        isLoading: false,
      };
    case 'AUTH_LOGOUT':
      return {
        ...initialState,
        isLoading: false,
      };
    case 'AUTH_LOADING':
      return { ...state, isLoading: true };
    case 'AUTH_LOADED':
      return { ...state, isLoading: false };
    default:
      return state;
  }
}

export function AuthProvider({ children }) {
  const [state, dispatch] = useReducer(authReducer, initialState);

  // On mount — check if we have a valid token
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      dispatch({ type: 'AUTH_LOADED' });
      return;
    }

    client
      .get('/api/v1/auth/me')
      .then((res) => {
        dispatch({
          type: 'AUTH_SUCCESS',
          payload: {
            user: res.data,
            tenant: res.data.tenant,
          },
        });
      })
      .catch((err) => {
        const statusCode = err?.response?.status;
        if (statusCode === 401 || statusCode === 403) {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          dispatch({ type: 'AUTH_LOGOUT' });
          return;
        }

        dispatch({ type: 'AUTH_LOADED' });
      });
  }, []);

  const login = async (email, password) => {
    const res = await client.post('/api/v1/auth/login', { email, password });
    const { access_token, refresh_token, user } = res.data;

    localStorage.setItem('access_token', access_token);
    localStorage.setItem('refresh_token', refresh_token);

    dispatch({
      type: 'AUTH_SUCCESS',
      payload: { user, tenant: user.tenant },
    });

    return user;
  };

  const register = async (email, password, fullName, tenantName) => {
    const res = await client.post('/api/v1/auth/register', {
      email,
      password,
      full_name: fullName,
      tenant_name: tenantName,
    });

    const { access_token, refresh_token } = res.data;
    localStorage.setItem('access_token', access_token);
    localStorage.setItem('refresh_token', refresh_token);

    // Fetch full user profile
    const profileRes = await client.get('/api/v1/auth/me');
    dispatch({
      type: 'AUTH_SUCCESS',
      payload: {
        user: profileRes.data,
        tenant: profileRes.data.tenant,
      },
    });

    return profileRes.data;
  };

  const logout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    dispatch({ type: 'AUTH_LOGOUT' });
  };

  const value = {
    ...state,
    login,
    register,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
