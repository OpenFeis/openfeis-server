<script setup lang="ts">
import { ref, computed } from 'vue';
import type { Dancer, CartItem } from '../../models/types';

// Props
const props = withDefaults(defineProps<{
  items: CartItem[];
  familyCap?: number;
  baseEntryFee?: number;
  perCompetitionFee?: number;
  currency?: 'USD' | 'EUR' | 'GBP';
  isLoggedIn?: boolean;
}>(), {
  familyCap: 150,
  baseEntryFee: 25,
  perCompetitionFee: 10,
  currency: 'USD',
  isLoggedIn: false
});

const emit = defineEmits<{
  (e: 'remove', item: CartItem): void;
  (e: 'checkout', payLater: boolean): void;
  (e: 'login-required'): void;
}>();

// Currency formatting
const currencySymbols: Record<string, string> = {
  USD: '$',
  EUR: '€',
  GBP: '£'
};

const formatCurrency = (amount: number): string => {
  const symbol = currencySymbols[props.currency] || '$';
  return `${symbol}${amount.toFixed(2)}`;
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
    // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
    const group = groups[item.dancer.id]!;
    group.items.push(item);
  });
  
  return Object.values(groups);
});

// Calculate fees
const subtotal = computed(() => {
  if (props.items.length === 0) return 0;
  
  // Base entry fee per dancer
  const dancers = new Set(props.items.map(i => i.dancer.id));
  const baseFees = dancers.size * props.baseEntryFee;
  
  // Per-competition fee
  const competitionFees = props.items.length * props.perCompetitionFee;
  
  return baseFees + competitionFees;
});

// Family cap discount
const familyCapDiscount = computed(() => {
  if (subtotal.value <= props.familyCap) return 0;
  return subtotal.value - props.familyCap;
});

// Is cap applied?
const isCapApplied = computed(() => familyCapDiscount.value > 0);

// Final total
const total = computed(() => {
  return Math.min(subtotal.value, props.familyCap);
});

// Savings percentage
const savingsPercent = computed(() => {
  if (subtotal.value === 0) return 0;
  return Math.round((familyCapDiscount.value / subtotal.value) * 100);
});

// Processing state
const isProcessing = ref(false);
const processingType = ref<'stripe' | 'pay_later' | null>(null);

const handleCheckout = () => {
  if (props.items.length === 0) return;
  if (!props.isLoggedIn) {
    emit('login-required');
    return;
  }
  isProcessing.value = true;
  processingType.value = 'stripe';
  emit('checkout', false);  // payLater = false
};

const handlePayLater = () => {
  if (props.items.length === 0) return;
  if (!props.isLoggedIn) {
    emit('login-required');
    return;
  }
  isProcessing.value = true;
  processingType.value = 'pay_later';
  emit('checkout', true);  // payLater = true
};

// Reset processing state (called from parent after API call completes)
const resetProcessing = () => {
  isProcessing.value = false;
  processingType.value = null;
};

// Expose reset function to parent
defineExpose({ resetProcessing });

// Get dancer's total competitions
const getDancerTotal = (dancerId: string): number => {
  return props.items.filter(i => i.dancer.id === dancerId).length * props.perCompetitionFee + props.baseEntryFee;
};
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
              <div class="text-xs text-slate-500">
                {{ formatCurrency(baseEntryFee) }} base + {{ formatCurrency(group.items.length * perCompetitionFee) }}
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
                <span class="text-sm text-slate-600">{{ formatCurrency(perCompetitionFee) }}</span>
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
          <!-- Subtotal -->
          <div class="flex justify-between text-sm">
            <span class="text-slate-600">Subtotal</span>
            <span class="text-slate-800 font-medium">{{ formatCurrency(subtotal) }}</span>
          </div>
          
          <!-- Fee explanation -->
          <div class="flex justify-between text-xs text-slate-500">
            <span>{{ itemsByDancer.length }} dancer{{ itemsByDancer.length !== 1 ? 's' : '' }} × {{ formatCurrency(baseEntryFee) }} base</span>
            <span>{{ formatCurrency(itemsByDancer.length * baseEntryFee) }}</span>
          </div>
          <div class="flex justify-between text-xs text-slate-500">
            <span>{{ items.length }} competition{{ items.length !== 1 ? 's' : '' }} × {{ formatCurrency(perCompetitionFee) }}</span>
            <span>{{ formatCurrency(items.length * perCompetitionFee) }}</span>
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
            v-if="!isCapApplied && subtotal > 0"
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

          <!-- Total -->
          <div class="flex justify-between items-center pt-3 border-t border-slate-200">
            <span class="text-lg font-bold text-slate-800">Total</span>
            <div class="text-right">
              <span class="text-2xl font-black text-rose-600">{{ formatCurrency(total) }}</span>
              <div v-if="isCapApplied" class="text-xs text-slate-500">
                <span class="line-through">{{ formatCurrency(subtotal) }}</span>
              </div>
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
          <!-- Pay Now Button (Stripe - Coming Soon) -->
          <button
            @click="handleCheckout"
            :disabled="isProcessing || items.length === 0"
            :class="[
              'w-full py-4 rounded-xl font-bold text-lg transition-all flex items-center justify-center gap-2',
              isProcessing || items.length === 0
                ? 'bg-slate-200 text-slate-400 cursor-not-allowed'
                : 'bg-gradient-to-r from-rose-600 to-pink-600 text-white shadow-lg shadow-rose-200 hover:shadow-xl hover:shadow-rose-300 transform hover:-translate-y-0.5'
            ]"
          >
            <template v-if="isProcessing && processingType === 'stripe'">
              <div class="animate-spin rounded-full h-5 w-5 border-2 border-white border-t-transparent"></div>
              Processing...
            </template>
            <template v-else>
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z" />
              </svg>
              Pay Now {{ formatCurrency(total) }}
            </template>
          </button>

          <!-- Divider -->
          <div class="flex items-center gap-4">
            <div class="flex-1 h-px bg-slate-200"></div>
            <span class="text-sm text-slate-400 font-medium">or</span>
            <div class="flex-1 h-px bg-slate-200"></div>
          </div>

          <!-- Pay at Door Button -->
          <button
            @click="handlePayLater"
            :disabled="isProcessing || items.length === 0"
            :class="[
              'w-full py-4 rounded-xl font-bold text-lg transition-all flex items-center justify-center gap-2 border-2',
              isProcessing || items.length === 0
                ? 'bg-slate-50 text-slate-400 border-slate-200 cursor-not-allowed'
                : 'bg-white text-emerald-700 border-emerald-500 hover:bg-emerald-50 hover:border-emerald-600'
            ]"
          >
            <template v-if="isProcessing && processingType === 'pay_later'">
              <div class="animate-spin rounded-full h-5 w-5 border-2 border-emerald-600 border-t-transparent"></div>
              Registering...
            </template>
            <template v-else>
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              Pay at Door (Check-in)
            </template>
          </button>

          <p class="text-xs text-slate-500 text-center">
            Choose "Pay at Door" to complete registration now and pay at the event check-in.
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
