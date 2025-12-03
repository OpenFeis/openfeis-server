<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { useAuthStore } from '../../stores/auth';

const props = defineProps<{
  token?: string;
}>();

const emit = defineEmits<{
  (e: 'verified'): void;
  (e: 'go-home'): void;
}>();

const auth = useAuthStore();

const status = ref<'verifying' | 'success' | 'error' | 'no-token'>('verifying');
const message = ref('');

onMounted(async () => {
  if (!props.token) {
    status.value = 'no-token';
    message.value = 'No verification token provided.';
    return;
  }

  const result = await auth.verifyEmail(props.token);
  
  if (result.success) {
    status.value = 'success';
    message.value = result.message;
    // Emit verified event after short delay for animation
    setTimeout(() => {
      emit('verified');
    }, 2000);
  } else {
    status.value = 'error';
    message.value = result.message;
  }
});
</script>

<template>
  <div class="min-h-[60vh] flex items-center justify-center px-4">
    <div class="max-w-md w-full">
      <!-- Verifying State -->
      <div v-if="status === 'verifying'" class="text-center">
        <div class="w-20 h-20 mx-auto mb-6 relative">
          <div class="absolute inset-0 rounded-full border-4 border-slate-200"></div>
          <div class="absolute inset-0 rounded-full border-4 border-emerald-500 border-t-transparent animate-spin"></div>
        </div>
        <h2 class="text-2xl font-bold text-slate-800 mb-2">Verifying your email...</h2>
        <p class="text-slate-600">Please wait while we verify your email address.</p>
      </div>

      <!-- Success State -->
      <div v-else-if="status === 'success'" class="text-center">
        <div class="w-20 h-20 mx-auto mb-6 rounded-full bg-gradient-to-br from-emerald-400 to-teal-500 flex items-center justify-center">
          <svg class="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <h2 class="text-2xl font-bold text-slate-800 mb-2">Email Verified! ✨</h2>
        <p class="text-slate-600 mb-6">{{ message }}</p>
        <p class="text-sm text-slate-500">Redirecting you to the home page...</p>
      </div>

      <!-- Error State -->
      <div v-else-if="status === 'error'" class="text-center">
        <div class="w-20 h-20 mx-auto mb-6 rounded-full bg-gradient-to-br from-red-400 to-rose-500 flex items-center justify-center">
          <svg class="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </div>
        <h2 class="text-2xl font-bold text-slate-800 mb-2">Verification Failed</h2>
        <p class="text-slate-600 mb-6">{{ message }}</p>
        <div class="space-y-3">
          <button
            @click="emit('go-home')"
            class="w-full px-6 py-3 rounded-xl font-semibold bg-slate-800 text-white hover:bg-slate-700 transition-colors"
          >
            Go to Home
          </button>
          <p class="text-sm text-slate-500">
            Need a new verification link?
            <button 
              v-if="auth.isAuthenticated && !auth.isEmailVerified"
              @click="auth.resendVerification()"
              class="text-emerald-600 hover:text-emerald-700 font-medium"
            >
              Resend verification email
            </button>
          </p>
        </div>
      </div>

      <!-- No Token State -->
      <div v-else-if="status === 'no-token'" class="text-center">
        <div class="w-20 h-20 mx-auto mb-6 rounded-full bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center">
          <svg class="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <h2 class="text-2xl font-bold text-slate-800 mb-2">No Verification Token</h2>
        <p class="text-slate-600 mb-6">{{ message }}</p>
        <button
          @click="emit('go-home')"
          class="px-6 py-3 rounded-xl font-semibold bg-slate-800 text-white hover:bg-slate-700 transition-colors"
        >
          Go to Home
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

