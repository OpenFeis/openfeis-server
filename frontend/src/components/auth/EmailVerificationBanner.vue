<script setup lang="ts">
import { ref } from 'vue';
import { useAuthStore } from '../../stores/auth';

const auth = useAuthStore();

const resending = ref(false);
const resendMessage = ref('');
const dismissed = ref(false);

const handleResend = async () => {
  resending.value = true;
  resendMessage.value = '';
  
  const result = await auth.resendVerification();
  
  resendMessage.value = result.message;
  resending.value = false;
  
  // Clear message after 5 seconds
  setTimeout(() => {
    resendMessage.value = '';
  }, 5000);
};

const dismiss = () => {
  dismissed.value = true;
};
</script>

<template>
  <div
    v-if="auth.isAuthenticated && !auth.isEmailVerified && !dismissed"
    class="bg-gradient-to-r from-amber-500 to-orange-500 text-white px-4 py-3 shadow-lg"
  >
    <div class="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-3">
      <div class="flex items-center gap-3">
        <div class="flex-shrink-0">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
          </svg>
        </div>
        <p class="text-sm font-medium">
          <span class="font-semibold">Please verify your email address.</span>
          <span class="hidden sm:inline"> Check your inbox for a verification link.</span>
        </p>
      </div>
      
      <div class="flex items-center gap-3">
        <!-- Resend message -->
        <span v-if="resendMessage" class="text-sm text-white/90">
          {{ resendMessage }}
        </span>
        
        <!-- Resend button -->
        <button
          v-if="!resendMessage"
          @click="handleResend"
          :disabled="resending"
          class="px-4 py-1.5 rounded-lg bg-white/20 hover:bg-white/30 text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
        >
          <svg v-if="resending" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          {{ resending ? 'Sending...' : 'Resend email' }}
        </button>
        
        <!-- Dismiss button -->
        <button
          @click="dismiss"
          class="p-1.5 rounded-lg hover:bg-white/20 transition-colors"
          aria-label="Dismiss"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
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

