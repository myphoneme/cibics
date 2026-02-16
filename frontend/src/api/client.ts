import axios from 'axios';

const baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8200/api/v1';

export const api = axios.create({
  baseURL,
});

export function setAuthToken(token: string | null) {
  if (token) {
    api.defaults.headers.common.Authorization = `Bearer ${token}`;
  } else {
    delete api.defaults.headers.common.Authorization;
  }
}
