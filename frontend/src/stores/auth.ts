import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { User } from '../models/types';

const API_URL = '/api/v1';
const TOKEN_KEY = 'openfeis_token';

interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export const useAuthStore = defineStore('auth', () => {
  // State
  const user = ref<User | null>(null);
  const token = ref<string | null>(localStorage.getItem(TOKEN_KEY));
  const loading = ref(false);
  const error = ref<string | null>(null);

  // Computed
  const isAuthenticated = computed(() => !!token.value && !!user.value);
  const userRole = computed(() => user.value?.role || null);
  
  // Role checks
  const isAdmin = computed(() => user.value?.role === 'super_admin');
  const isOrganizer = computed(() => user.value?.role === 'organizer' || user.value?.role === 'super_admin');
  const isAdjudicator = computed(() => user.value?.role === 'adjudicator');
  const isParent = computed(() => user.value?.role === 'parent');
  const isTeacher = computed(() => user.value?.role === 'teacher');
  
  // Can access admin features
  const canAccessAdmin = computed(() => 
    user.value?.role === 'super_admin' || user.value?.role === 'organizer'
  );
  
  // Can access judge features (super_admin has full access)
  const canAccessJudge = computed(() => 
    user.value?.role === 'super_admin' || user.value?.role === 'adjudicator'
  );

  // Helper to make authenticated requests
  async function authFetch(url: string, options: RequestInit = {}): Promise<Response> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string> || {})
    };
    
    if (token.value) {
      headers['Authorization'] = `Bearer ${token.value}`;
    }
    
    return fetch(url, {
      ...options,
      headers
    });
  }

  // Actions
  async function login(email: string, password: string): Promise<boolean> {
    loading.value = true;
    error.value = null;
    
    try {
      const response = await fetch(`${API_URL}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });
      
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Login failed');
      }
      
      const data: AuthResponse = await response.json();
      
      // Store token and user
      token.value = data.access_token;
      user.value = data.user;
      localStorage.setItem(TOKEN_KEY, data.access_token);
      
      return true;
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Login failed';
      return false;
    } finally {
      loading.value = false;
    }
  }

  async function register(email: string, password: string, name: string): Promise<boolean> {
    loading.value = true;
    error.value = null;
    
    try {
      const response = await fetch(`${API_URL}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, name })
      });
      
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Registration failed');
      }
      
      const data: AuthResponse = await response.json();
      
      // Store token and user (auto-login)
      token.value = data.access_token;
      user.value = data.user;
      localStorage.setItem(TOKEN_KEY, data.access_token);
      
      return true;
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Registration failed';
      return false;
    } finally {
      loading.value = false;
    }
  }

  async function fetchCurrentUser(): Promise<boolean> {
    if (!token.value) {
      return false;
    }
    
    loading.value = true;
    error.value = null;
    
    try {
      const response = await authFetch(`${API_URL}/auth/me`);
      
      if (!response.ok) {
        // Token is invalid or expired
        logout();
        return false;
      }
      
      const data: User = await response.json();
      user.value = data;
      
      return true;
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch user';
      logout();
      return false;
    } finally {
      loading.value = false;
    }
  }

  function logout() {
    token.value = null;
    user.value = null;
    localStorage.removeItem(TOKEN_KEY);
  }

  // Initialize: try to restore session from stored token
  async function initialize() {
    if (token.value) {
      await fetchCurrentUser();
    }
  }

  // Expose authFetch for other stores/components to use
  return {
    // State
    user,
    token,
    loading,
    error,
    
    // Computed
    isAuthenticated,
    userRole,
    isAdmin,
    isOrganizer,
    isAdjudicator,
    isParent,
    isTeacher,
    canAccessAdmin,
    canAccessJudge,
    
    // Actions
    login,
    register,
    logout,
    fetchCurrentUser,
    initialize,
    authFetch
  };
});

