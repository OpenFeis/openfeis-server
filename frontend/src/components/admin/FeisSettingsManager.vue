<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useAuthStore } from '../../stores/auth';
import type { FeisSettings, FeeItem, StripeStatus, FeeCategory } from '../../models/types';
import { formatCents } from '../../models/types';

// Props
const props = defineProps<{
  feisId: string;
  feisName: string;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
}>();

const authStore = useAuthStore();

// State
const loading = ref(true);
const saving = ref(false);
const error = ref<string | null>(null);
const successMessage = ref<string | null>(null);
const activeTab = ref<'pricing' | 'fees' | 'registration' | 'stripe'>('pricing');

// Settings data
const settings = ref<FeisSettings>({
  id: '',
  feis_id: props.feisId,
  base_entry_fee_cents: 2500,
  per_competition_fee_cents: 1000,
  family_max_cents: 15000,
  late_fee_cents: 500,
  late_fee_date: null,
  change_fee_cents: 1000,
  registration_opens: null,
  registration_closes: null,
  stripe_account_id: null,
  stripe_onboarding_complete: false
});

const feeItems = ref<FeeItem[]>([]);
const stripeStatus = ref<StripeStatus | null>(null);

// Edit form values (in dollars for easier editing)
const baseFee = ref(25);
const perCompetitionFee = ref(10);
const familyMax = ref<number | null>(150);
const noFamilyCap = ref(false);
const lateFee = ref(5);
const lateFeeDate = ref<string>('');
const changeFee = ref(10);
const registrationOpens = ref<string>('');
const registrationCloses = ref<string>('');

// Fee item editing
const showNewFeeItem = ref(false);
const newFeeItem = ref({
  name: '',
  description: '',
  amount: 0,
  category: 'non_qualifying' as FeeCategory,
  required: false,
  max_quantity: 1
});

// API functions
const API_BASE = '/api/v1';

async function fetchSettings() {
  try {
    const res = await fetch(`${API_BASE}/feis/${props.feisId}/settings`, {
      headers: authStore.authHeaders
    });
    if (res.ok) {
      const data = await res.json();
      settings.value = data;
      
      // Populate form values
      baseFee.value = data.base_entry_fee_cents / 100;
      perCompetitionFee.value = data.per_competition_fee_cents / 100;
      if (data.family_max_cents === null) {
        noFamilyCap.value = true;
        familyMax.value = 150;
      } else {
        noFamilyCap.value = false;
        familyMax.value = data.family_max_cents / 100;
      }
      lateFee.value = data.late_fee_cents / 100;
      lateFeeDate.value = data.late_fee_date || '';
      changeFee.value = data.change_fee_cents / 100;
      registrationOpens.value = data.registration_opens ? data.registration_opens.slice(0, 16) : '';
      registrationCloses.value = data.registration_closes ? data.registration_closes.slice(0, 16) : '';
    }
  } catch (err) {
    console.error('Failed to fetch settings:', err);
  }
}

async function fetchFeeItems() {
  try {
    const res = await fetch(`${API_BASE}/feis/${props.feisId}/fee-items?active_only=false`, {
      headers: authStore.authHeaders
    });
    if (res.ok) {
      feeItems.value = await res.json();
    }
  } catch (err) {
    console.error('Failed to fetch fee items:', err);
  }
}

async function fetchStripeStatus() {
  try {
    const res = await fetch(`${API_BASE}/feis/${props.feisId}/stripe-status`);
    if (res.ok) {
      stripeStatus.value = await res.json();
    }
  } catch (err) {
    console.error('Failed to fetch Stripe status:', err);
  }
}

async function saveSettings() {
  saving.value = true;
  error.value = null;
  successMessage.value = null;
  
  try {
    const res = await fetch(`${API_BASE}/feis/${props.feisId}/settings`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...authStore.authHeaders
      },
      body: JSON.stringify({
        base_entry_fee_cents: Math.round(baseFee.value * 100),
        per_competition_fee_cents: Math.round(perCompetitionFee.value * 100),
        family_max_cents: noFamilyCap.value ? -1 : Math.round((familyMax.value ?? 150) * 100),
        late_fee_cents: Math.round(lateFee.value * 100),
        late_fee_date: lateFeeDate.value || null,
        change_fee_cents: Math.round(changeFee.value * 100),
        registration_opens: registrationOpens.value ? new Date(registrationOpens.value).toISOString() : null,
        registration_closes: registrationCloses.value ? new Date(registrationCloses.value).toISOString() : null
      })
    });
    
    if (!res.ok) {
      const data = await res.json();
      throw new Error(data.detail || 'Failed to save settings');
    }
    
    settings.value = await res.json();
    successMessage.value = 'Settings saved successfully!';
    setTimeout(() => { successMessage.value = null; }, 3000);
  } catch (err: any) {
    error.value = err.message || 'Failed to save settings';
  } finally {
    saving.value = false;
  }
}

async function createFeeItem() {
  saving.value = true;
  error.value = null;
  
  try {
    const res = await fetch(`${API_BASE}/feis/${props.feisId}/fee-items`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...authStore.authHeaders
      },
      body: JSON.stringify({
        feis_id: props.feisId,
        name: newFeeItem.value.name,
        description: newFeeItem.value.description || null,
        amount_cents: Math.round(newFeeItem.value.amount * 100),
        category: newFeeItem.value.category,
        required: newFeeItem.value.required,
        max_quantity: newFeeItem.value.max_quantity
      })
    });
    
    if (!res.ok) {
      const data = await res.json();
      throw new Error(data.detail || 'Failed to create fee item');
    }
    
    await fetchFeeItems();
    showNewFeeItem.value = false;
    newFeeItem.value = {
      name: '',
      description: '',
      amount: 0,
      category: 'non_qualifying',
      required: false,
      max_quantity: 1
    };
    successMessage.value = 'Fee item created!';
    setTimeout(() => { successMessage.value = null; }, 3000);
  } catch (err: any) {
    error.value = err.message || 'Failed to create fee item';
  } finally {
    saving.value = false;
  }
}

async function toggleFeeItemActive(item: FeeItem) {
  try {
    const res = await fetch(`${API_BASE}/fee-items/${item.id}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...authStore.authHeaders
      },
      body: JSON.stringify({ active: !item.active })
    });
    
    if (res.ok) {
      await fetchFeeItems();
    }
  } catch (err) {
    console.error('Failed to update fee item:', err);
  }
}

async function startStripeOnboarding() {
  saving.value = true;
  error.value = null;
  
  try {
    const returnUrl = `${window.location.origin}/admin?feis=${props.feisId}&stripe=complete`;
    const refreshUrl = `${window.location.origin}/admin?feis=${props.feisId}&stripe=refresh`;
    
    const res = await fetch(`${API_BASE}/feis/${props.feisId}/stripe-onboarding`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...authStore.authHeaders
      },
      body: JSON.stringify({
        feis_id: props.feisId,
        return_url: returnUrl,
        refresh_url: refreshUrl
      })
    });
    
    if (!res.ok) {
      const data = await res.json();
      throw new Error(data.detail || 'Failed to start onboarding');
    }
    
    const data = await res.json();
    
    if (data.success && data.onboarding_url) {
      // In test mode, simulate the onboarding
      if (data.is_test_mode) {
        await completeTestOnboarding();
      } else {
        // Redirect to Stripe
        window.location.href = data.onboarding_url;
      }
    } else {
      throw new Error(data.error || 'Failed to create onboarding link');
    }
  } catch (err: any) {
    error.value = err.message || 'Failed to start Stripe onboarding';
  } finally {
    saving.value = false;
  }
}

async function completeTestOnboarding() {
  try {
    const res = await fetch(`${API_BASE}/feis/${props.feisId}/stripe-onboarding/complete`, {
      method: 'POST',
      headers: authStore.authHeaders
    });
    
    if (res.ok) {
      await fetchStripeStatus();
      successMessage.value = 'Test mode: Stripe connected successfully!';
      setTimeout(() => { successMessage.value = null; }, 3000);
    }
  } catch (err) {
    console.error('Failed to complete test onboarding:', err);
  }
}

// Lifecycle
onMounted(async () => {
  loading.value = true;
  await Promise.all([
    fetchSettings(),
    fetchFeeItems(),
    fetchStripeStatus()
  ]);
  loading.value = false;
});
</script>

<template>
  <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
    <div class="bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
      <!-- Header -->
      <div class="bg-gradient-to-r from-violet-600 to-purple-600 px-6 py-5 flex items-center justify-between">
        <div>
          <h2 class="text-xl font-bold text-white">Feis Settings</h2>
          <p class="text-violet-200 text-sm">{{ feisName }}</p>
        </div>
        <button @click="emit('close')" class="text-white/80 hover:text-white transition-colors">
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
      
      <!-- Loading -->
      <div v-if="loading" class="flex-1 flex items-center justify-center p-12">
        <div class="animate-spin rounded-full h-12 w-12 border-4 border-violet-200 border-t-violet-600"></div>
      </div>
      
      <!-- Content -->
      <div v-else class="flex-1 overflow-y-auto">
        <!-- Tabs -->
        <div class="border-b border-slate-200 px-6">
          <nav class="flex gap-6">
            <button
              v-for="tab in ['pricing', 'fees', 'registration', 'stripe'] as const"
              :key="tab"
              @click="activeTab = tab"
              :class="[
                'py-4 text-sm font-medium border-b-2 transition-colors capitalize',
                activeTab === tab
                  ? 'border-violet-600 text-violet-600'
                  : 'border-transparent text-slate-500 hover:text-slate-700'
              ]"
            >
              {{ tab === 'fees' ? 'Fee Items' : tab }}
            </button>
          </nav>
        </div>
        
        <!-- Messages -->
        <div v-if="error" class="mx-6 mt-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          {{ error }}
        </div>
        <div v-if="successMessage" class="mx-6 mt-4 p-4 bg-emerald-50 border border-emerald-200 rounded-lg text-emerald-700 text-sm">
          {{ successMessage }}
        </div>
        
        <!-- Pricing Tab -->
        <div v-if="activeTab === 'pricing'" class="p-6 space-y-6">
          <div class="grid grid-cols-2 gap-6">
            <!-- Base Entry Fee -->
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-2">
                Base Entry Fee (per dancer)
              </label>
              <div class="relative">
                <span class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">$</span>
                <input
                  v-model.number="baseFee"
                  type="number"
                  min="0"
                  step="0.01"
                  class="w-full pl-8 pr-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-violet-500"
                />
              </div>
              <p class="mt-1 text-xs text-slate-500">One-time fee per dancer</p>
            </div>
            
            <!-- Per Competition Fee -->
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-2">
                Per Competition Fee
              </label>
              <div class="relative">
                <span class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">$</span>
                <input
                  v-model.number="perCompetitionFee"
                  type="number"
                  min="0"
                  step="0.01"
                  class="w-full pl-8 pr-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-violet-500"
                />
              </div>
              <p class="mt-1 text-xs text-slate-500">Fee per competition entry</p>
            </div>
          </div>
          
          <!-- Family Cap -->
          <div class="border-t border-slate-200 pt-6">
            <div class="flex items-center justify-between mb-4">
              <div>
                <h3 class="font-medium text-slate-800">Family Maximum Cap</h3>
                <p class="text-sm text-slate-500">Maximum total a family pays for qualifying fees</p>
              </div>
              <label class="flex items-center gap-2 cursor-pointer">
                <input
                  v-model="noFamilyCap"
                  type="checkbox"
                  class="w-4 h-4 text-violet-600 border-slate-300 rounded focus:ring-violet-500"
                />
                <span class="text-sm text-slate-600">No cap</span>
              </label>
            </div>
            
            <div v-if="!noFamilyCap" class="relative max-w-xs">
              <span class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">$</span>
              <input
                v-model.number="familyMax"
                type="number"
                min="0"
                step="0.01"
                class="w-full pl-8 pr-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-violet-500"
              />
            </div>
          </div>
          
          <!-- Late & Change Fees -->
          <div class="border-t border-slate-200 pt-6">
            <h3 class="font-medium text-slate-800 mb-4">Late & Change Fees</h3>
            <div class="grid grid-cols-2 gap-6">
              <div>
                <label class="block text-sm font-medium text-slate-700 mb-2">
                  Late Registration Fee
                </label>
                <div class="relative">
                  <span class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">$</span>
                  <input
                    v-model.number="lateFee"
                    type="number"
                    min="0"
                    step="0.01"
                    class="w-full pl-8 pr-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-violet-500"
                  />
                </div>
                <p class="mt-1 text-xs text-slate-500">Per entry after late date</p>
              </div>
              
              <div>
                <label class="block text-sm font-medium text-slate-700 mb-2">
                  Late Fee Date
                </label>
                <input
                  v-model="lateFeeDate"
                  type="date"
                  class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-violet-500"
                />
                <p class="mt-1 text-xs text-slate-500">Late fee applies after this date</p>
              </div>
              
              <div>
                <label class="block text-sm font-medium text-slate-700 mb-2">
                  Change Fee
                </label>
                <div class="relative">
                  <span class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">$</span>
                  <input
                    v-model.number="changeFee"
                    type="number"
                    min="0"
                    step="0.01"
                    class="w-full pl-8 pr-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-violet-500"
                  />
                </div>
                <p class="mt-1 text-xs text-slate-500">Fee to modify registration</p>
              </div>
            </div>
          </div>
          
          <!-- Save Button -->
          <div class="border-t border-slate-200 pt-6">
            <button
              @click="saveSettings"
              :disabled="saving"
              class="px-6 py-2.5 bg-violet-600 text-white font-medium rounded-lg hover:bg-violet-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {{ saving ? 'Saving...' : 'Save Pricing Settings' }}
            </button>
          </div>
        </div>
        
        <!-- Fee Items Tab -->
        <div v-if="activeTab === 'fees'" class="p-6 space-y-6">
          <div class="flex items-center justify-between">
            <div>
              <h3 class="font-medium text-slate-800">Additional Fee Items</h3>
              <p class="text-sm text-slate-500">Venue levies, program books, merchandise, etc.</p>
            </div>
            <button
              @click="showNewFeeItem = true"
              class="px-4 py-2 bg-violet-600 text-white text-sm font-medium rounded-lg hover:bg-violet-700 transition-colors"
            >
              + Add Fee Item
            </button>
          </div>
          
          <!-- New Fee Item Form -->
          <div v-if="showNewFeeItem" class="bg-slate-50 rounded-xl p-4 border border-slate-200">
            <h4 class="font-medium text-slate-800 mb-4">New Fee Item</h4>
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">Name</label>
                <input
                  v-model="newFeeItem.name"
                  type="text"
                  placeholder="e.g., Venue Levy"
                  class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-violet-500"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">Amount</label>
                <div class="relative">
                  <span class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">$</span>
                  <input
                    v-model.number="newFeeItem.amount"
                    type="number"
                    min="0"
                    step="0.01"
                    class="w-full pl-8 pr-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-violet-500"
                  />
                </div>
              </div>
              <div class="col-span-2">
                <label class="block text-sm font-medium text-slate-700 mb-1">Description (optional)</label>
                <input
                  v-model="newFeeItem.description"
                  type="text"
                  placeholder="e.g., Per-dancer venue access fee"
                  class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-violet-500"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">Category</label>
                <select
                  v-model="newFeeItem.category"
                  class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-violet-500"
                >
                  <option value="non_qualifying">Non-Qualifying (not affected by family cap)</option>
                  <option value="qualifying">Qualifying (counts toward family cap)</option>
                </select>
              </div>
              <div>
                <label class="block text-sm font-medium text-slate-700 mb-1">Max Quantity</label>
                <input
                  v-model.number="newFeeItem.max_quantity"
                  type="number"
                  min="1"
                  class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-violet-500"
                />
              </div>
              <div class="col-span-2">
                <label class="flex items-center gap-2 cursor-pointer">
                  <input
                    v-model="newFeeItem.required"
                    type="checkbox"
                    class="w-4 h-4 text-violet-600 border-slate-300 rounded focus:ring-violet-500"
                  />
                  <span class="text-sm text-slate-700">Required (auto-added to every order)</span>
                </label>
              </div>
            </div>
            <div class="flex gap-3 mt-4">
              <button
                @click="createFeeItem"
                :disabled="!newFeeItem.name || newFeeItem.amount <= 0 || saving"
                class="px-4 py-2 bg-violet-600 text-white text-sm font-medium rounded-lg hover:bg-violet-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {{ saving ? 'Creating...' : 'Create Fee Item' }}
              </button>
              <button
                @click="showNewFeeItem = false"
                class="px-4 py-2 text-slate-600 text-sm font-medium hover:text-slate-800 transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
          
          <!-- Fee Items List -->
          <div v-if="feeItems.length === 0" class="text-center py-8 text-slate-500">
            No fee items yet. Add venue levies, program books, or other fees.
          </div>
          <div v-else class="space-y-3">
            <div
              v-for="item in feeItems"
              :key="item.id"
              :class="[
                'flex items-center justify-between p-4 rounded-xl border',
                item.active ? 'bg-white border-slate-200' : 'bg-slate-50 border-slate-100 opacity-60'
              ]"
            >
              <div class="flex-1">
                <div class="flex items-center gap-2">
                  <span class="font-medium text-slate-800">{{ item.name }}</span>
                  <span v-if="item.required" class="px-2 py-0.5 text-xs bg-amber-100 text-amber-700 rounded">Required</span>
                  <span
                    :class="[
                      'px-2 py-0.5 text-xs rounded',
                      item.category === 'qualifying' ? 'bg-violet-100 text-violet-700' : 'bg-slate-100 text-slate-600'
                    ]"
                  >
                    {{ item.category === 'qualifying' ? 'Qualifying' : 'Non-Qualifying' }}
                  </span>
                </div>
                <p v-if="item.description" class="text-sm text-slate-500 mt-1">{{ item.description }}</p>
              </div>
              <div class="flex items-center gap-4">
                <span class="font-semibold text-slate-800">{{ formatCents(item.amount_cents) }}</span>
                <button
                  @click="toggleFeeItemActive(item)"
                  :class="[
                    'px-3 py-1.5 text-sm font-medium rounded-lg transition-colors',
                    item.active
                      ? 'text-red-600 hover:bg-red-50'
                      : 'text-emerald-600 hover:bg-emerald-50'
                  ]"
                >
                  {{ item.active ? 'Deactivate' : 'Activate' }}
                </button>
              </div>
            </div>
          </div>
        </div>
        
        <!-- Registration Tab -->
        <div v-if="activeTab === 'registration'" class="p-6 space-y-6">
          <div>
            <h3 class="font-medium text-slate-800 mb-4">Registration Window</h3>
            <p class="text-sm text-slate-500 mb-6">
              Set when registration opens and closes. Leave empty for always open.
            </p>
            
            <div class="grid grid-cols-2 gap-6">
              <div>
                <label class="block text-sm font-medium text-slate-700 mb-2">
                  Registration Opens
                </label>
                <input
                  v-model="registrationOpens"
                  type="datetime-local"
                  class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-violet-500"
                />
              </div>
              
              <div>
                <label class="block text-sm font-medium text-slate-700 mb-2">
                  Registration Closes
                </label>
                <input
                  v-model="registrationCloses"
                  type="datetime-local"
                  class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-violet-500"
                />
              </div>
            </div>
          </div>
          
          <!-- Save Button -->
          <div class="border-t border-slate-200 pt-6">
            <button
              @click="saveSettings"
              :disabled="saving"
              class="px-6 py-2.5 bg-violet-600 text-white font-medium rounded-lg hover:bg-violet-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {{ saving ? 'Saving...' : 'Save Registration Settings' }}
            </button>
          </div>
        </div>
        
        <!-- Stripe Tab -->
        <div v-if="activeTab === 'stripe'" class="p-6 space-y-6">
          <div>
            <h3 class="font-medium text-slate-800 mb-2">Payment Processing</h3>
            <p class="text-sm text-slate-500">
              Connect your Stripe account to accept online payments for registrations.
            </p>
          </div>
          
          <!-- Stripe Status Card -->
          <div
            :class="[
              'rounded-xl p-6 border',
              stripeStatus?.stripe_configured && stripeStatus?.onboarding_complete
                ? 'bg-emerald-50 border-emerald-200'
                : stripeStatus?.stripe_mode === 'disabled'
                  ? 'bg-amber-50 border-amber-200'
                  : 'bg-slate-50 border-slate-200'
            ]"
          >
            <div class="flex items-start gap-4">
              <div
                :class="[
                  'w-12 h-12 rounded-full flex items-center justify-center',
                  stripeStatus?.onboarding_complete
                    ? 'bg-emerald-500'
                    : stripeStatus?.stripe_mode === 'disabled'
                      ? 'bg-amber-500'
                      : 'bg-slate-400'
                ]"
              >
                <svg v-if="stripeStatus?.onboarding_complete" class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                </svg>
                <svg v-else class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
                </svg>
              </div>
              <div class="flex-1">
                <h4 class="font-semibold text-slate-800">
                  {{ stripeStatus?.onboarding_complete ? 'Stripe Connected' : 'Connect Stripe' }}
                </h4>
                <p class="text-sm text-slate-600 mt-1">
                  {{ stripeStatus?.message }}
                </p>
                
                <!-- Mode Badge -->
                <div class="flex items-center gap-2 mt-3">
                  <span
                    :class="[
                      'px-2 py-1 text-xs font-medium rounded',
                      stripeStatus?.stripe_mode === 'live'
                        ? 'bg-emerald-100 text-emerald-700'
                        : stripeStatus?.stripe_mode === 'test'
                          ? 'bg-blue-100 text-blue-700'
                          : 'bg-slate-100 text-slate-600'
                    ]"
                  >
                    {{ stripeStatus?.stripe_mode === 'live' ? 'Live Mode' : stripeStatus?.stripe_mode === 'test' ? 'Test Mode' : 'Disabled' }}
                  </span>
                  <span v-if="!stripeStatus?.stripe_configured" class="text-xs text-amber-600">
                    Configure STRIPE_SECRET_KEY to enable
                  </span>
                </div>
              </div>
            </div>
            
            <!-- Connect Button -->
            <div v-if="!stripeStatus?.onboarding_complete" class="mt-6">
              <button
                @click="startStripeOnboarding"
                :disabled="saving"
                class="w-full py-3 bg-[#635BFF] text-white font-semibold rounded-lg hover:bg-[#5851e0] disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
              >
                <svg class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M13.976 9.15c-2.172-.806-3.356-1.426-3.356-2.409 0-.831.683-1.305 1.901-1.305 2.227 0 4.515.858 6.09 1.631l.89-5.494C18.252.975 15.697 0 12.165 0 9.667 0 7.589.654 6.104 1.872 4.56 3.147 3.757 4.992 3.757 7.218c0 4.039 2.467 5.76 6.476 7.219 2.585.92 3.445 1.574 3.445 2.583 0 .98-.84 1.545-2.354 1.545-1.875 0-4.965-.921-6.99-2.109l-.9 5.555C5.175 22.99 8.385 24 11.714 24c2.641 0 4.843-.624 6.328-1.813 1.664-1.305 2.525-3.236 2.525-5.732 0-4.128-2.524-5.851-6.591-7.305z"/>
                </svg>
                {{ saving ? 'Starting...' : stripeStatus?.stripe_mode === 'disabled' ? 'Simulate Connection (Test Mode)' : 'Connect with Stripe' }}
              </button>
              <p class="text-xs text-slate-500 text-center mt-2">
                {{ stripeStatus?.stripe_mode === 'disabled' 
                  ? "Stripe is not configured. This will simulate a connected account for testing."
                  : "You'll be redirected to Stripe to complete account setup."
                }}
              </p>
            </div>
          </div>
          
          <!-- Pay at Door Info -->
          <div class="bg-slate-50 rounded-xl p-6 border border-slate-200">
            <div class="flex items-start gap-4">
              <div class="w-12 h-12 rounded-full bg-emerald-500 flex items-center justify-center">
                <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
              </div>
              <div>
                <h4 class="font-semibold text-slate-800">Pay at Door</h4>
                <p class="text-sm text-slate-600 mt-1">
                  This option is always available. Registrants can complete their registration and pay at the event check-in.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

