<script setup lang="ts">
import { ref, computed } from 'vue';
import { useAuthStore } from '../../stores/auth';

const emit = defineEmits<{
  (e: 'success'): void;
  (e: 'switchToLogin'): void;
}>();

const auth = useAuthStore();

const name = ref('');
const email = ref('');
const password = ref('');
const confirmPassword = ref('');
const showPassword = ref(false);

const passwordsMatch = computed(() => 
  !confirmPassword.value || password.value === confirmPassword.value
);

const passwordStrong = computed(() => 
  password.value.length >= 6
);

const canSubmit = computed(() => 
  name.value && 
  email.value && 
  password.value && 
  passwordsMatch.value && 
  passwordStrong.value
);

async function handleSubmit() {
  if (!canSubmit.value) return;
  
  const success = await auth.register(email.value, password.value, name.value);
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
      <h2 class="text-2xl font-bold text-slate-800">Create Account</h2>
      <p class="text-slate-500 mt-1">Join the Open Feis community</p>
    </div>

    <!-- Form -->
    <form @submit.prevent="handleSubmit" class="space-y-5">
      <!-- Name -->
      <div>
        <label for="name" class="block text-sm font-medium text-slate-700 mb-1.5">
          Full Name
        </label>
        <input
          id="name"
          v-model="name"
          type="text"
          autocomplete="name"
          required
          placeholder="Your full name"
          class="w-full px-4 py-3 rounded-xl border border-slate-300 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 transition-all outline-none"
        />
      </div>

      <!-- Email -->
      <div>
        <label for="reg-email" class="block text-sm font-medium text-slate-700 mb-1.5">
          Email Address
        </label>
        <input
          id="reg-email"
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
        <label for="reg-password" class="block text-sm font-medium text-slate-700 mb-1.5">
          Password
        </label>
        <div class="relative">
          <input
            id="reg-password"
            v-model="password"
            :type="showPassword ? 'text' : 'password'"
            autocomplete="new-password"
            required
            placeholder="At least 6 characters"
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
        <p v-if="password && !passwordStrong" class="mt-1.5 text-xs text-amber-600">
          Password must be at least 6 characters
        </p>
      </div>

      <!-- Confirm Password -->
      <div>
        <label for="confirm-password" class="block text-sm font-medium text-slate-700 mb-1.5">
          Confirm Password
        </label>
        <input
          id="confirm-password"
          v-model="confirmPassword"
          :type="showPassword ? 'text' : 'password'"
          autocomplete="new-password"
          required
          placeholder="Confirm your password"
          :class="[
            'w-full px-4 py-3 rounded-xl border transition-all outline-none',
            confirmPassword && !passwordsMatch
              ? 'border-red-300 focus:border-red-500 focus:ring-2 focus:ring-red-500/20'
              : 'border-slate-300 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20'
          ]"
        />
        <p v-if="confirmPassword && !passwordsMatch" class="mt-1.5 text-xs text-red-600">
          Passwords do not match
        </p>
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
        :disabled="auth.loading || !canSubmit"
        class="w-full py-3.5 rounded-xl font-semibold text-white bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 shadow-lg shadow-emerald-200 hover:shadow-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:shadow-lg flex items-center justify-center gap-2"
      >
        <svg v-if="auth.loading" class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
        <span>{{ auth.loading ? 'Creating account...' : 'Create Account' }}</span>
      </button>
    </form>

    <!-- Footer -->
    <div class="mt-6 text-center">
      <p class="text-slate-500">
        Already have an account?
        <button
          @click="emit('switchToLogin')"
          class="text-emerald-600 hover:text-emerald-700 font-semibold transition-colors"
        >
          Sign in
        </button>
      </p>
    </div>

    <!-- Role Note -->
    <div class="mt-6 p-4 rounded-xl bg-blue-50 border border-blue-200">
      <p class="text-sm text-blue-700">
        <span class="font-semibold">Note:</span> New accounts are created with the "Parent" role by default. 
        Contact an administrator to request organizer or adjudicator access.
      </p>
    </div>
  </div>
</template>

