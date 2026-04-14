import axios from 'axios';

function normalizeBaseUrl(baseUrl) {
  if (!baseUrl) return '';
  return baseUrl.endsWith('/') ? baseUrl.slice(0, -1) : baseUrl;
}

function clearAuthAndRedirect() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  window.location.assign('/login');
}

let refreshRequest = null;

async function refreshAccessToken() {
  if (!refreshRequest) {
    const refreshToken = localStorage.getItem('refresh_token');

    if (!refreshToken) {
      clearAuthAndRedirect();
      throw new Error('Missing refresh token');
    }

    refreshRequest = axios
      .post(`${client.defaults.baseURL}/api/v1/auth/refresh`, {
        refresh_token: refreshToken,
      })
      .then((response) => {
        const { access_token } = response.data;
        localStorage.setItem('access_token', access_token);
        return access_token;
      })
      .catch((error) => {
        clearAuthAndRedirect();
        throw error;
      })
      .finally(() => {
        refreshRequest = null;
      });
  }

  return refreshRequest;
}

const client = axios.create({
  baseURL: normalizeBaseUrl(process.env.REACT_APP_API_URL),
  headers: { 'Content-Type': 'application/json' },
});

// Request interceptor — attach JWT
client.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor — handle 401 + auto-refresh
client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // If 401 and we haven't already retried
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const accessToken = await refreshAccessToken();

        // Retry original request with new token
        originalRequest.headers.Authorization = `Bearer ${accessToken}`;
        return client(originalRequest);
      } catch (refreshError) {
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

export default client;
