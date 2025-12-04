<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue';
import { useAuthStore } from '../../stores/auth';
import type { Dancer, CartItem, CartCalculationResponse, CheckoutResponse, RegistrationStatus } from '../../models/types';

// Props
const props = withDefaults(defineProps<{
  items: CartItem[];
  feisId: string;
  currency?: 'USD' | 'EUR' | 'GBP';
  isLoggedIn?: boolean;
}>(), {
  currency: 'USD',
  isLoggedIn: false
});

const emit = defineEmits<{
  (e: 'remove', item: CartItem): void;
  (e: 'checkout-complete', orderId: string): void;
  (e: 'login-required'): void;
}>();

const authStore = useAuthStore();

// State
const cartData = ref<CartCalculationResponse | null>(null);
const registrationStatus = ref<RegistrationStatus | null>(null);
const loading = ref(false);
const checkoutLoading = ref(false);
const checkoutError = ref<string | null>(null);
const processingType = ref<'stripe' | 'pay_later' | null>(null);

// Currency formatting
const currencySymbols: Record<string, string> = {
  USD: '$',
  EUR: '€',
  GBP: '£'
};

const formatCurrency = (cents: number): string => {
  const symbol = currencySymbols[props.currency] || '$';
  return `${symbol}${(cents / 100).toFixed(2)}`;
};

// Group items by dancer
const itemsByDancer = computed(() => {
  const groups: Record<string, { dancer: Dancer; items: CartItem[] }> = {};
  
  props.items.forEach(item => {
    if (!groups[item.dancer.id]) {
      groups[item.dancer.id] = {
        dancer: item.dancer as Dancer,
        items: []
      };
    }
    const group = groups[item.dancer.id]!;
    group.items.push(item);
  });
  
  return Object.values(groups);
});

// API functions
const API_BASE = '/api/v1';

async function fetchRegistrationStatus() {
  if (!props.feisId) return;
  
  try {
    const res = await fetch(`${API_BASE}/feis/${props.feisId}/registration-status`);
    if (res.ok) {
      registrationStatus.value = await res.json();
    }
  } catch (err) {
    console.error('Failed to fetch registration status:', err);
  }
}

async function calculateCart() {
  if (props.items.length === 0 || !props.isLoggedIn || !props.feisId) {
    cartData.value = null;
    return;
  }
  
  loading.value = true;
  
  try {
    const res = await fetch(`${API_BASE}/cart/calculate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...authStore.authHeaders
      },
      body: JSON.stringify({
        feis_id: props.feisId,
        items: props.items.map(item => ({
          competition_id: item.competition.id,
          dancer_id: item.dancer.id
        }))
      })
    });
    
    if (res.ok) {
      cartData.value = await res.json();
    } else {
      console.error('Cart calculation failed');
      cartData.value = null;
    }
  } catch (err) {
    console.error('Failed to calculate cart:', err);
    cartData.value = null;
  } finally {
    loading.value = false;
  }
}

async function handleCheckout(payAtDoor: boolean) {
  if (props.items.length === 0) return;
  if (!props.isLoggedIn) {
    emit('login-required');
    return;
  }
  
  checkoutLoading.value = true;
  checkoutError.value = null;
  processingType.value = payAtDoor ? 'pay_later' : 'stripe';
  
  try {
    const res = await fetch(`${API_BASE}/checkout`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...authStore.authHeaders
      },
      body: JSON.stringify({
        feis_id: props.feisId,
        items: props.items.map(item => ({
          competition_id: item.competition.id,
          dancer_id: item.dancer.id
        })),
        pay_at_door: payAtDoor
      })
    });
    
    const data: CheckoutResponse = await res.json();
    
    if (!data.success) {
      checkoutError.value = data.message;
      return;
    }
    
    if (payAtDoor || data.is_test_mode) {
      // Complete - registration done
      if (data.order_id) {
        emit('checkout-complete', data.order_id);
      }
    } else if (data.checkout_url) {
      // Redirect to Stripe
      window.location.href = data.checkout_url;
    }
  } catch (err: any) {
    checkoutError.value = err.message || 'Checkout failed. Please try again.';
  } finally {
    checkoutLoading.value = false;
    processingType.value = null;
  }
}

// Watch for cart changes
watch(() => props.items, calculateCart, { deep: true });

// Also watch for login state changes
watch(() => props.isLoggedIn, calculateCart);

// Fetch on mount
onMounted(() => {
  fetchRegistrationStatus();
  if (props.isLoggedIn && props.items.length > 0) {
    calculateCart();
  }
});

// Get dancer's total from cart data
const getDancerTotal = (dancerId: string): number => {
  if (!cartData.value) {
    // Fallback to simple calculation
    const items = props.items.filter(i => i.dancer.id === dancerId);
    return items.reduce((sum, item) => sum + (item.competition.price_cents || 1000), 0);
  }
  
  // Sum line items for this dancer
  return cartData.value.line_items
    .filter(li => li.dancer_id === dancerId)
    .reduce((sum, li) => sum + li.total_cents, 0);
};

// Computed values from cart data (with fallbacks)
const subtotal = computed(() => cartData.value?.subtotal_cents || 0);
const familyCapDiscount = computed(() => cartData.value?.family_discount_cents || 0);
const isCapApplied = computed(() => cartData.value?.family_cap_applied || false);
const familyCap = computed(() => cartData.value?.family_cap_cents || 15000);
const lateFee = computed(() => cartData.value?.late_fee_cents || 0);
const isLate = computed(() => cartData.value?.late_fee_applied || false);
const total = computed(() => cartData.value?.total_cents || 0);
const savingsPercent = computed(() => cartData.value?.savings_percent || 0);

// Check if online payments are available
const canPayOnline = computed(() => {
  return registrationStatus.value?.payment_methods.includes('stripe') || false;
});

// Reset processing state (called from parent after API call completes)
const resetProcessing = () => {
  checkoutLoading.value = false;
  processingType.value = null;
};

// Expose reset function to parent
defineExpose({ resetProcessing });
</script>

<template>
  <div class="bg-white rounded-2xl shadow-lg border border-slate-100 overflow-hidden">
    <!-- Header -->
    <div class="bg-gradient-to-r from-rose-600 to-pink-600 px-6 py-5">
      <h2 class="text-xl font-bold text-white flex items-center gap-2">
        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z" />
        </svg>
        Registration Cart
      </h2>
      <p class="text-rose-100 text-sm mt-1">
        {{ items.length }} competition{{ items.length !== 1 ? 's' : '' }} selected
      </p>
    </div>

    <div class="p-6">
      <!-- Empty Cart -->
      <div v-if="items.length === 0" class="text-center py-12">
        <div class="w-20 h-20 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg class="w-10 h-10 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z" />
          </svg>
        </div>
        <h3 class="text-lg font-semibold text-slate-700 mb-2">Your cart is empty</h3>
        <p class="text-slate-500 text-sm">
          Select competitions from the eligibility picker to add them to your cart.
        </p>
      </div>

      <!-- Cart Items by Dancer -->
      <div v-else class="space-y-6">
        <!-- Registration Closed Warning -->
        <div v-if="registrationStatus && !registrationStatus.is_open" class="p-4 bg-red-50 border border-red-200 rounded-xl">
          <div class="flex items-center gap-3">
            <svg class="w-6 h-6 text-red-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <div>
              <p class="font-semibold text-red-800">Registration Closed</p>
              <p class="text-sm text-red-600">{{ registrationStatus.message }}</p>
            </div>
          </div>
        </div>

        <!-- Late Fee Warning -->
        <div v-else-if="isLate && lateFee > 0" class="p-4 bg-amber-50 border border-amber-200 rounded-xl">
          <div class="flex items-center gap-3">
            <svg class="w-6 h-6 text-amber-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
              <p class="font-semibold text-amber-800">Late Registration</p>
              <p class="text-sm text-amber-600">A late fee of {{ formatCurrency(lateFee) }} has been applied.</p>
            </div>
          </div>
        </div>

        <!-- Dancer Groups -->
        <div 
          v-for="group in itemsByDancer" 
          :key="group.dancer.id"
          class="border border-slate-200 rounded-xl overflow-hidden"
        >
          <!-- Dancer Header -->
          <div class="bg-slate-50 px-4 py-3 flex items-center justify-between border-b border-slate-200">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 rounded-full bg-gradient-to-br from-rose-400 to-pink-500 flex items-center justify-center text-white font-bold">
                {{ group.dancer.name.charAt(0) }}
              </div>
              <div>
                <div class="font-semibold text-slate-800">{{ group.dancer.name }}</div>
                <div class="text-xs text-slate-500">
                  {{ group.items.length }} competition{{ group.items.length !== 1 ? 's' : '' }}
                </div>
              </div>
            </div>
            <div class="text-right">
              <div class="text-sm font-semibold text-slate-700">
                {{ formatCurrency(getDancerTotal(group.dancer.id)) }}
              </div>
            </div>
          </div>

          <!-- Competition Items -->
          <div class="divide-y divide-slate-100">
            <div 
              v-for="item in group.items" 
              :key="item.competition.id"
              class="px-4 py-3 flex items-center justify-between hover:bg-slate-50 transition-colors"
            >
              <div class="flex-1">
                <div class="font-medium text-slate-700 text-sm">
                  {{ item.competition.name }}
                </div>
                <div class="text-xs text-slate-500">
                  {{ item.competition.level.charAt(0).toUpperCase() + item.competition.level.slice(1) }}
                </div>
              </div>
              <div class="flex items-center gap-3">
                <span class="text-sm text-slate-600">{{ formatCurrency(item.competition.price_cents || 1000) }}</span>
                <button 
                  @click="emit('remove', item)"
                  class="w-6 h-6 rounded-full bg-slate-100 hover:bg-red-100 text-slate-400 hover:text-red-500 flex items-center justify-center transition-colors"
                >
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Fee Breakdown -->
        <div class="border-t border-slate-200 pt-4 space-y-3">
          <!-- Loading indicator -->
          <div v-if="loading" class="flex items-center justify-center py-4">
            <div class="animate-spin rounded-full h-6 w-6 border-2 border-rose-200 border-t-rose-600"></div>
            <span class="ml-2 text-sm text-slate-500">Calculating...</span>
          </div>
          
          <template v-else-if="cartData">
            <!-- Subtotal -->
            <div class="flex justify-between text-sm">
              <span class="text-slate-600">Subtotal</span>
              <span class="text-slate-800 font-medium">{{ formatCurrency(subtotal) }}</span>
            </div>
            
            <!-- Fee breakdown from line items -->
            <div class="flex justify-between text-xs text-slate-500">
              <span>{{ cartData.dancer_count }} dancer{{ cartData.dancer_count !== 1 ? 's' : '' }} base fee</span>
              <span>{{ formatCurrency(cartData.line_items.filter(li => li.type === 'base_fee').reduce((sum, li) => sum + li.total_cents, 0)) }}</span>
            </div>
            <div class="flex justify-between text-xs text-slate-500">
              <span>{{ cartData.competition_count }} competition{{ cartData.competition_count !== 1 ? 's' : '' }}</span>
              <span>{{ formatCurrency(cartData.line_items.filter(li => li.type === 'competition').reduce((sum, li) => sum + li.total_cents, 0)) }}</span>
            </div>

            <!-- Family Cap Discount -->
            <div 
              v-if="isCapApplied"
              class="flex justify-between text-sm bg-gradient-to-r from-emerald-50 to-teal-50 -mx-6 px-6 py-3 border-y border-emerald-100"
            >
              <div class="flex items-center gap-2">
                <span class="inline-flex items-center justify-center w-6 h-6 rounded-full bg-emerald-500 text-white">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                  </svg>
                </span>
                <div>
                  <span class="text-emerald-700 font-semibold">Family Cap Applied!</span>
                  <span class="text-emerald-600 text-xs ml-2">Save {{ savingsPercent }}%</span>
                </div>
              </div>
              <span class="text-emerald-700 font-semibold">-{{ formatCurrency(familyCapDiscount) }}</span>
            </div>

            <!-- Family Cap Info -->
            <div 
              v-if="!isCapApplied && subtotal > 0 && familyCap"
              class="text-xs text-slate-500 bg-slate-50 rounded-lg p-3"
            >
              <div class="flex items-center gap-2">
                <svg class="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>
                  <strong>Family Cap:</strong> Add {{ formatCurrency(familyCap - subtotal) }} more to reach {{ formatCurrency(familyCap) }} max
                </span>
              </div>
            </div>

            <!-- Late Fee -->
            <div v-if="isLate && lateFee > 0" class="flex justify-between text-sm text-amber-700">
              <span>Late Fee</span>
              <span>+{{ formatCurrency(lateFee) }}</span>
            </div>

            <!-- Total -->
            <div class="flex justify-between items-center pt-3 border-t border-slate-200">
              <span class="text-lg font-bold text-slate-800">Total</span>
              <div class="text-right">
                <span class="text-2xl font-black text-rose-600">{{ formatCurrency(total) }}</span>
                <div v-if="isCapApplied" class="text-xs text-slate-500">
                  <span class="line-through">{{ formatCurrency(subtotal + familyCapDiscount) }}</span>
                </div>
              </div>
            </div>
          </template>
          
          <!-- Fallback for logged out users -->
          <template v-else-if="!isLoggedIn">
            <div class="text-center py-4 text-sm text-slate-500">
              Sign in to see your cart total with family cap applied
            </div>
          </template>
        </div>

        <!-- Checkout Error -->
        <div v-if="checkoutError" class="p-4 bg-red-50 border border-red-200 rounded-xl">
          <div class="flex items-start gap-3">
            <svg class="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
              <p class="font-medium text-red-800">Checkout Error</p>
              <p class="text-sm text-red-600">{{ checkoutError }}</p>
            </div>
          </div>
        </div>

        <!-- Login Required Message -->
        <div v-if="!isLoggedIn" class="mb-4 p-4 bg-amber-50 border border-amber-200 rounded-xl">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center flex-shrink-0">
              <svg class="w-5 h-5 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
              </svg>
            </div>
            <div>
              <p class="font-semibold text-amber-800">Sign in to complete registration</p>
              <p class="text-sm text-amber-600">Create an account or sign in to register your dancer</p>
            </div>
          </div>
        </div>

        <!-- Checkout Buttons -->
        <div class="space-y-3">
          <!-- Pay Now Button (Stripe) -->
          <button
            v-if="canPayOnline"
            @click="handleCheckout(false)"
            :disabled="checkoutLoading || items.length === 0 || !!(registrationStatus && !registrationStatus.is_open)"
            :class="[
              'w-full py-4 rounded-xl font-bold text-lg transition-all flex items-center justify-center gap-2',
              checkoutLoading || items.length === 0 || !!(registrationStatus && !registrationStatus.is_open)
                ? 'bg-slate-200 text-slate-400 cursor-not-allowed'
                : 'bg-gradient-to-r from-rose-600 to-pink-600 text-white shadow-lg shadow-rose-200 hover:shadow-xl hover:shadow-rose-300 transform hover:-translate-y-0.5'
            ]"
          >
            <template v-if="checkoutLoading && processingType === 'stripe'">
              <div class="animate-spin rounded-full h-5 w-5 border-2 border-white border-t-transparent"></div>
              Processing...
            </template>
            <template v-else>
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z" />
              </svg>
              Pay Now {{ cartData ? formatCurrency(total) : '' }}
            </template>
          </button>

          <!-- Divider (only if both options available) -->
          <div v-if="canPayOnline" class="flex items-center gap-4">
            <div class="flex-1 h-px bg-slate-200"></div>
            <span class="text-sm text-slate-400 font-medium">or</span>
            <div class="flex-1 h-px bg-slate-200"></div>
          </div>

          <!-- Pay at Door Button -->
          <button
            @click="handleCheckout(true)"
            :disabled="checkoutLoading || items.length === 0 || !!(registrationStatus && !registrationStatus.is_open)"
            :class="[
              'w-full py-4 rounded-xl font-bold text-lg transition-all flex items-center justify-center gap-2 border-2',
              checkoutLoading || items.length === 0 || !!(registrationStatus && !registrationStatus.is_open)
                ? 'bg-slate-50 text-slate-400 border-slate-200 cursor-not-allowed'
                : canPayOnline
                  ? 'bg-white text-emerald-700 border-emerald-500 hover:bg-emerald-50 hover:border-emerald-600'
                  : 'bg-gradient-to-r from-emerald-600 to-teal-600 text-white border-transparent shadow-lg shadow-emerald-200 hover:shadow-xl hover:shadow-emerald-300 transform hover:-translate-y-0.5'
            ]"
          >
            <template v-if="checkoutLoading && processingType === 'pay_later'">
              <div class="animate-spin rounded-full h-5 w-5 border-2 border-emerald-600 border-t-transparent"></div>
              Registering...
            </template>
            <template v-else>
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              {{ canPayOnline ? 'Pay at Door (Check-in)' : 'Register Now - Pay at Door' }}
              <span v-if="!canPayOnline && cartData" class="ml-1">{{ formatCurrency(total) }}</span>
            </template>
          </button>

          <p class="text-xs text-slate-500 text-center">
            {{ canPayOnline 
              ? 'Choose "Pay at Door" to complete registration now and pay at the event check-in.'
              : 'Complete your registration now and pay at the event check-in desk.'
            }}
          </p>
        </div>

        <!-- Security Badge -->
        <div class="flex items-center justify-center gap-2 text-xs text-slate-500 mt-4">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
          </svg>
          <span>Your registration is secure</span>
        </div>
      </div>
    </div>
  </div>
</template>
