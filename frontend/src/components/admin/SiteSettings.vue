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

onMounted(() => {
  fetchSettings();
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

