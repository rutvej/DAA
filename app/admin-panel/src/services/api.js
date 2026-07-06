const API_BASE = process.env.REACT_APP_API_URL || (window.location.protocol + '//' + window.location.hostname + ':8000');

const buildUrl = (path, params) => {
  const base = API_BASE ? API_BASE.replace(/\/$/, '') : '';
  const url = `${base}${path}`;
  if (!params) return url;

  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      search.set(key, value);
    }
  });

  const query = search.toString();
  return query ? `${url}?${query}` : url;
};

export const apiFetch = async (path, { token, method = 'GET', body, params } = {}) => {
  const response = await fetch(buildUrl(path, params), {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  const contentType = response.headers.get('content-type') || '';
  const data = contentType.includes('application/json')
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const message = typeof data === 'string' ? data : data.message;
    const error = new Error(message || 'Request failed');
    error.status = response.status;
    error.data = data;
    throw error;
  }

  return data;
};

export const authApi = {
  login: (credentials) => apiFetch('/auth/login', { method: 'POST', body: credentials }),
  register: (payload) => apiFetch('/auth/register', { method: 'POST', body: payload }),
};

export const logsApi = {
  list: ({ token, page, limit, status } = {}) =>
    apiFetch('/logs', { token, params: { page, limit, status } }),
  get: ({ token, id }) => apiFetch(`/logs/${id}`, { token }),
};

export const fixesApi = {
  get: ({ token, id }) => apiFetch(`/fixes/${id}`, { token }),
  approve: ({ token, id }) => apiFetch(`/fixes/${id}/approve`, { token, method: 'POST' }),
};

export const healthApi = {
  list: ({ token }) => apiFetch('/health', { token }),
};
