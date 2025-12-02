<script setup lang="ts">
import { ref } from 'vue';
import { useAuthStore } from '../../stores/auth';

const emit = defineEmits<{
  (e: 'success'): void;
  (e: 'switchToRegister'): void;
}>();

const auth = useAuthStore();

const email = ref('');
const password = ref('');
const showPassword = ref(false);

async function handleSubmit() {
  if (!email.value || !password.value) return;
  
  const success = await auth.login(email.value, password.value);
  if (success) {
    emit('success');
  }
}
</script>

<template>
  <div class="bg-white rounded-2xl shadow-xl border border-slate-200 p-8 w-full max-w-md">
    <!-- Header -->
    <div class="text-center mb-8">
      <div class="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-emerald-400 to-teal-500 mb-4">
        <span class="text-3xl">☘️</span>
      </div>
      <h2 class="text-2xl font-bold text-slate-800">Welcome Back</h2>
      <p class="text-slate-500 mt-1">Sign in to your Open Feis account</p>
    </div>

    <!-- Form -->
    <form @submit.prevent="handleSubmit" class="space-y-5">
      <!-- Email -->
      <div>
        <label for="email" class="block text-sm font-medium text-slate-700 mb-1.5">
          Email Address
        </label>
        <input
          id="email"
          v-model="email"
          type="email"
          autocomplete="email"
          required
          placeholder="you@example.com"
          class="w-full px-4 py-3 rounded-xl border border-slate-300 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 transition-all outline-none"
        />
      </div>

      <!-- Password -->
      <div>
        <label for="password" class="block text-sm font-medium text-slate-700 mb-1.5">
          Password
        </label>
        <div class="relative">
          <input
            id="password"
            v-model="password"
            :type="showPassword ? 'text' : 'password'"
            autocomplete="current-password"
            required
            placeholder="••••••••"
            class="w-full px-4 py-3 rounded-xl border border-slate-300 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 transition-all outline-none pr-12"
          />
          <button
            type="button"
            @click="showPassword = !showPassword"
            class="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
          >
            <svg v-if="showPassword" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
            </svg>
            <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
            </svg>
          </button>
        </div>
      </div>

      <!-- Error Message -->
      <div v-if="auth.error" class="p-3 rounded-lg bg-red-50 border border-red-200">
        <p class="text-sm text-red-600 flex items-center gap-2">
          <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          {{ auth.error }}
        </p>
      </div>

      <!-- Submit Button -->
      <button
        type="submit"
        :disabled="auth.loading || !email || !password"
        class="w-full py-3.5 rounded-xl font-semibold text-white bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 shadow-lg shadow-emerald-200 hover:shadow-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:shadow-lg flex items-center justify-center gap-2"
      >
        <svg v-if="auth.loading" class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
        <span>{{ auth.loading ? 'Signing in...' : 'Sign In' }}</span>
      </button>
    </form>

    <!-- Footer -->
    <div class="mt-6 text-center">
      <p class="text-slate-500">
        Don't have an account?
        <button
          @click="emit('switchToRegister')"
          class="text-emerald-600 hover:text-emerald-700 font-semibold transition-colors"
        >
          Create one
        </button>
      </p>
    </div>

    <!-- Demo Credentials -->
    <div class="mt-6 p-4 rounded-xl bg-slate-50 border border-slate-200">
      <p class="text-xs font-medium text-slate-500 uppercase tracking-wide mb-2">Demo Account</p>
      <div class="text-sm text-slate-600 space-y-1">
        <p><span class="text-slate-400">Email:</span> admin@openfeis.org</p>
        <p><span class="text-slate-400">Password:</span> admin123</p>
      </div>
    </div>
  </div>
</template>

