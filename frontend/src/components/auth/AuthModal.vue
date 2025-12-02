<script setup lang="ts">
import { ref, watch } from 'vue';
import LoginForm from './LoginForm.vue';
import RegisterForm from './RegisterForm.vue';

const props = defineProps<{
  show: boolean;
  initialMode?: 'login' | 'register';
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'success'): void;
}>();

const mode = ref<'login' | 'register'>(props.initialMode || 'login');

// Reset mode when modal opens
watch(() => props.show, (newVal) => {
  if (newVal) {
    mode.value = props.initialMode || 'login';
  }
});

function handleSuccess() {
  emit('success');
  emit('close');
}

function handleBackdropClick(e: MouseEvent) {
  // Only close if clicking the backdrop itself
  if (e.target === e.currentTarget) {
    emit('close');
  }
}
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition-opacity duration-200"
      leave-active-class="transition-opacity duration-200"
      enter-from-class="opacity-0"
      leave-to-class="opacity-0"
    >
      <div
        v-if="show"
        class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm"
        @click="handleBackdropClick"
      >
        <Transition
          enter-active-class="transition-all duration-200"
          leave-active-class="transition-all duration-200"
          enter-from-class="opacity-0 scale-95"
          leave-to-class="opacity-0 scale-95"
        >
          <div v-if="show" class="relative">
            <!-- Close Button -->
            <button
              @click="emit('close')"
              class="absolute -top-2 -right-2 z-10 w-8 h-8 rounded-full bg-white shadow-lg border border-slate-200 flex items-center justify-center text-slate-400 hover:text-slate-600 hover:bg-slate-50 transition-all"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>

            <!-- Login Form -->
            <LoginForm
              v-if="mode === 'login'"
              @success="handleSuccess"
              @switch-to-register="mode = 'register'"
            />

            <!-- Register Form -->
            <RegisterForm
              v-else
              @success="handleSuccess"
              @switch-to-login="mode = 'login'"
            />
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

