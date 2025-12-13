<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useAuthStore } from '../../stores/auth';

const auth = useAuthStore();

const emit = defineEmits<{
  (e: 'back'): void;
}>();

// Form state
const resendApiKey = ref('');
const resendFromEmail = ref('');
const siteName = ref('');
const siteUrl = ref('');

// UI state
const loading = ref(true);
const saving = ref(false);
const error = ref<string | null>(null);
const success = ref<string | null>(null);
const resendConfigured = ref(false);

// Demo data state
const hasDemoData = ref(false);
const demoLoading = ref(false);
const demoPopulating = ref(false);
const demoDeleting = ref(false);
const demoMessage = ref<string | null>(null);
const demoError = ref<string | null>(null);

// Fetch current settings
const fetchSettings = async () => {
  loading.value = true;
  error.value = null;
  
  try {
    const response = await auth.authFetch('/api/v1/admin/settings');
    
    if (!response.ok) {
      throw new Error('Failed to load settings');
    }
    
    const data = await response.json();
    resendConfigured.value = data.resend_configured;
    resendFromEmail.value = data.resend_from_email;
    siteName.value = data.site_name;
    siteUrl.value = data.site_url;
    // API key is never returned for security
    resendApiKey.value = '';
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load settings';
  } finally {
    loading.value = false;
  }
};

// Save settings
const saveSettings = async () => {
  saving.value = true;
  error.value = null;
  success.value = null;
  
  try {
    const payload: Record<string, string> = {};
    
    // Only send API key if it was entered (not empty placeholder)
    if (resendApiKey.value.trim()) {
      payload.resend_api_key = resendApiKey.value.trim();
    }
    if (resendFromEmail.value.trim()) {
      payload.resend_from_email = resendFromEmail.value.trim();
    }
    if (siteName.value.trim()) {
      payload.site_name = siteName.value.trim();
    }
    if (siteUrl.value.trim()) {
      payload.site_url = siteUrl.value.trim();
    }
    
    const response = await auth.authFetch('/api/v1/admin/settings', {
      method: 'PUT',
      body: JSON.stringify(payload)
    });
    
    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.detail || 'Failed to save settings');
    }
    
    const data = await response.json();
    resendConfigured.value = data.resend_configured;
    resendApiKey.value = ''; // Clear the input after saving
    
    success.value = 'Settings saved successfully!';
    setTimeout(() => {
      success.value = null;
    }, 3000);
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to save settings';
  } finally {
    saving.value = false;
  }
};

// Fetch demo data status
const fetchDemoStatus = async () => {
  demoLoading.value = true;
  try {
    const response = await auth.authFetch('/api/v1/admin/demo-data/status');
    if (response.ok) {
      const data = await response.json();
      hasDemoData.value = data.has_demo_data;
    }
  } catch (e) {
    console.error('Failed to check demo data status:', e);
  } finally {
    demoLoading.value = false;
  }
};

// Populate demo data
const populateDemoData = async () => {
  if (!confirm(
    'This will create demo data including:\n\n' +
    '• 3 feiseanna (2 future, 1 past with results)\n' +
    '• ~700 dancers across the events\n' +
    '• 15 Demo judges, 12 teachers, and parents\n' +
    '• Competitions ready for scheduling\n\n' +
    'Proceed?'
  )) {
    return;
  }
  
  demoPopulating.value = true;
  demoMessage.value = null;
  demoError.value = null;
  
  try {
    const response = await auth.authFetch('/api/v1/admin/demo-data/populate', {
      method: 'POST'
    });
    
    const data = await response.json();
    
    if (response.ok && data.success) {
      demoMessage.value = data.message;
      hasDemoData.value = true;
    } else {
      demoError.value = data.message || data.detail || 'Failed to populate demo data';
    }
  } catch (e) {
    demoError.value = e instanceof Error ? e.message : 'Failed to populate demo data';
  } finally {
    demoPopulating.value = false;
  }
};

// Delete demo data
const deleteDemoData = async () => {
  if (!confirm(
    '⚠️ This will DELETE all demo data:\n\n' +
    '• All demo users (organizers, teachers, parents, judges)\n' +
    '• All demo feiseanna and their competitions\n' +
    '• All demo dancers and their entries\n' +
    '• All demo scores and results\n\n' +
    'This cannot be undone. Proceed?'
  )) {
    return;
  }
  
  demoDeleting.value = true;
  demoMessage.value = null;
  demoError.value = null;
  
  try {
    const response = await auth.authFetch('/api/v1/admin/demo-data', {
      method: 'DELETE'
    });
    
    const data = await response.json();
    
    if (response.ok && data.success) {
      demoMessage.value = data.message;
      hasDemoData.value = false;
    } else {
      demoError.value = data.message || data.detail || 'Failed to delete demo data';
    }
  } catch (e) {
    demoError.value = e instanceof Error ? e.message : 'Failed to delete demo data';
  } finally {
    demoDeleting.value = false;
  }
};

onMounted(() => {
  fetchSettings();
  fetchDemoStatus();
});
</script>

<template>
  <div>
    <!-- Header -->
    <div class="mb-6">
      <button
        @click="emit('back')"
        class="text-slate-600 hover:text-slate-800 text-sm font-medium flex items-center gap-1 mb-2"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
        </svg>
        Back to Admin
      </button>
      <h1 class="text-2xl font-bold text-slate-800">Site Settings</h1>
      <p class="text-slate-600">Configure email and site-wide settings</p>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="bg-white rounded-xl shadow-lg p-8 text-center">
      <div class="animate-spin w-8 h-8 border-4 border-slate-200 border-t-emerald-500 rounded-full mx-auto mb-4"></div>
      <p class="text-slate-600">Loading settings...</p>
    </div>

    <!-- Settings Form -->
    <div v-else class="space-y-6">
      <!-- Email Settings Card -->
      <div class="bg-white rounded-xl shadow-lg overflow-hidden">
        <div class="bg-gradient-to-r from-emerald-500 to-teal-500 px-6 py-4">
          <h2 class="text-lg font-bold text-white flex items-center gap-2">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
            Email Settings (Resend)
          </h2>
          <p class="text-emerald-100 text-sm">Configure email verification and notifications</p>
        </div>
        
        <div class="p-6 space-y-4">
          <!-- Status Badge -->
          <div class="flex items-center gap-2">
            <span class="text-sm font-medium text-slate-700">Status:</span>
            <span
              v-if="resendConfigured"
              class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700"
            >
              <svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
              </svg>
              Configured
            </span>
            <span
              v-else
              class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-100 text-amber-700"
            >
              <svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
              </svg>
              Not Configured
            </span>
          </div>

          <!-- API Key -->
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">
              Resend API Key
            </label>
            <input
              v-model="resendApiKey"
              type="password"
              :placeholder="resendConfigured ? '••••••••••••••••••••••••' : 'Enter your Resend API key'"
              class="w-full px-4 py-2.5 rounded-lg border border-slate-300 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200 transition-all font-mono text-sm"
            />
            <p class="text-xs text-slate-500 mt-1">
              Get your API key from <a href="https://resend.com/api-keys" target="_blank" class="text-emerald-600 hover:underline">resend.com/api-keys</a>
            </p>
          </div>

          <!-- From Email -->
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">
              From Email Address
            </label>
            <input
              v-model="resendFromEmail"
              type="text"
              placeholder="Open Feis <noreply@yourdomain.com>"
              class="w-full px-4 py-2.5 rounded-lg border border-slate-300 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200 transition-all"
            />
            <p class="text-xs text-slate-500 mt-1">
              Must be from a verified domain in your Resend account, or use <code class="bg-slate-100 px-1 rounded">onboarding@resend.dev</code> for testing
            </p>
          </div>
        </div>
      </div>

      <!-- Site Settings Card -->
      <div class="bg-white rounded-xl shadow-lg overflow-hidden">
        <div class="bg-gradient-to-r from-slate-600 to-slate-700 px-6 py-4">
          <h2 class="text-lg font-bold text-white flex items-center gap-2">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            General Settings
          </h2>
          <p class="text-slate-300 text-sm">Site name and URL for emails</p>
        </div>
        
        <div class="p-6 space-y-4">
          <!-- Site Name -->
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">
              Site Name
            </label>
            <input
              v-model="siteName"
              type="text"
              placeholder="Open Feis"
              class="w-full px-4 py-2.5 rounded-lg border border-slate-300 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200 transition-all"
            />
            <p class="text-xs text-slate-500 mt-1">
              Used in email subject lines and content
            </p>
          </div>

          <!-- Site URL -->
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">
              Site URL
            </label>
            <input
              v-model="siteUrl"
              type="url"
              placeholder="https://openfeis.com"
              class="w-full px-4 py-2.5 rounded-lg border border-slate-300 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200 transition-all"
            />
            <p class="text-xs text-slate-500 mt-1">
              Used for verification links in emails (use <code class="bg-slate-100 px-1 rounded">http://localhost:5173</code> for local development)
            </p>
          </div>
        </div>
      </div>

      <!-- Error/Success Messages -->
      <div v-if="error" class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg flex items-center gap-2">
        <svg class="w-5 h-5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
        </svg>
        {{ error }}
      </div>

      <div v-if="success" class="bg-emerald-50 border border-emerald-200 text-emerald-700 px-4 py-3 rounded-lg flex items-center gap-2">
        <svg class="w-5 h-5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
        </svg>
        {{ success }}
      </div>

      <!-- Save Button -->
      <div class="flex justify-end">
        <button
          @click="saveSettings"
          :disabled="saving"
          class="px-6 py-3 rounded-xl font-semibold bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow-lg shadow-emerald-200 hover:shadow-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
        >
          <svg v-if="saving" class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
          </svg>
          {{ saving ? 'Saving...' : 'Save Settings' }}
        </button>
      </div>

      <!-- Demo Data Card (Super Admin Only) -->
      <div class="bg-white rounded-xl shadow-lg overflow-hidden border-2 border-dashed border-amber-300">
        <div class="bg-gradient-to-r from-amber-500 to-orange-500 px-6 py-4">
          <h2 class="text-lg font-bold text-white flex items-center gap-2">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
            </svg>
            Demo Data (Development)
          </h2>
          <p class="text-amber-100 text-sm">Populate with realistic test data for development and demos</p>
        </div>
        
        <div class="p-6 space-y-4">
          <!-- Status -->
          <div v-if="demoLoading" class="flex items-center gap-2 text-slate-500">
            <div class="animate-spin w-4 h-4 border-2 border-slate-300 border-t-amber-500 rounded-full"></div>
            Checking demo data status...
          </div>
          
          <div v-else class="flex items-center gap-2">
            <span class="text-sm font-medium text-slate-700">Status:</span>
            <span
              v-if="hasDemoData"
              class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-100 text-amber-700"
            >
              <svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                <path d="M3 12v3c0 1.657 3.134 3 7 3s7-1.343 7-3v-3c0 1.657-3.134 3-7 3s-7-1.343-7-3z" />
                <path d="M3 7v3c0 1.657 3.134 3 7 3s7-1.343 7-3V7c0 1.657-3.134 3-7 3S3 8.657 3 7z" />
                <path d="M17 5c0 1.657-3.134 3-7 3S3 6.657 3 5s3.134-3 7-3 7 1.343 7 3z" />
              </svg>
              Demo Data Present
            </span>
            <span
              v-else
              class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-600"
            >
              <svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M5 2a2 2 0 00-2 2v14l3.5-2 3.5 2 3.5-2 3.5 2V4a2 2 0 00-2-2H5zm2.5 3a1.5 1.5 0 100 3 1.5 1.5 0 000-3zm6.207.293a1 1 0 00-1.414 0l-6 6a1 1 0 101.414 1.414l6-6a1 1 0 000-1.414zM12.5 10a1.5 1.5 0 100 3 1.5 1.5 0 000-3z" clip-rule="evenodd" />
              </svg>
              No Demo Data
            </span>
          </div>

          <!-- Description -->
          <div class="bg-amber-50 rounded-lg p-4 text-sm text-amber-800">
            <p class="font-medium mb-2">Demo data includes:</p>
            <ul class="space-y-1 text-amber-700">
              <li class="flex items-center gap-2">
                <span class="text-amber-500">☘️</span>
                <strong>Shamrock Classic Feis</strong> — 60 days out, ~250 dancers
              </li>
              <li class="flex items-center gap-2">
                <span class="text-amber-500">🏆</span>
                <strong>Celtic Pride Championships</strong> — 90 days out, ~103 dancers
              </li>
              <li class="flex items-center gap-2">
                <span class="text-amber-500">📊</span>
                <strong>Emerald Isle Fall Feis</strong> — 7 days ago, ~350 dancers with complete results
              </li>
              <li class="flex items-center gap-2">
                <span class="text-amber-500">👥</span>
                15 judges, 12 teachers, parents, and dancers with realistic Irish names
              </li>
            </ul>
            <p class="mt-3 text-xs text-amber-600">
              All demo accounts use password: <code class="bg-amber-100 px-1.5 py-0.5 rounded font-mono">demo123</code>
            </p>
          </div>

          <!-- Messages -->
          <div v-if="demoError" class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg flex items-center gap-2">
            <svg class="w-5 h-5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
            </svg>
            {{ demoError }}
          </div>

          <div v-if="demoMessage" class="bg-emerald-50 border border-emerald-200 text-emerald-700 px-4 py-3 rounded-lg flex items-center gap-2">
            <svg class="w-5 h-5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
            </svg>
            {{ demoMessage }}
          </div>

          <!-- Buttons -->
          <div class="flex flex-wrap gap-3">
            <button
              v-if="!hasDemoData"
              @click="populateDemoData"
              :disabled="demoPopulating"
              class="px-5 py-2.5 rounded-lg font-semibold bg-gradient-to-r from-amber-500 to-orange-500 text-white shadow-md hover:shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              <svg v-if="demoPopulating" class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
              </svg>
              {{ demoPopulating ? 'Populating... (this may take a moment)' : 'Populate Demo Data' }}
            </button>

            <button
              v-if="hasDemoData"
              @click="deleteDemoData"
              :disabled="demoDeleting"
              class="px-5 py-2.5 rounded-lg font-semibold bg-red-500 hover:bg-red-600 text-white shadow-md hover:shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              <svg v-if="demoDeleting" class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
              {{ demoDeleting ? 'Deleting...' : 'Delete Demo Data' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
.animate-spin {
  animation: spin 1s linear infinite;
}
</style>

