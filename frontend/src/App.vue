<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import JudgePad from './components/judge/JudgePad.vue';
import TabulatorDashboard from './components/tabulator/TabulatorDashboard.vue';
import DancerProfileForm from './components/registration/DancerProfileForm.vue';
import DanceRegistrationTable from './components/registration/DanceRegistrationTable.vue';
import CartSummary from './components/registration/CartSummary.vue';
import SyllabusGenerator from './components/admin/SyllabusGenerator.vue';
import FeisManager from './components/admin/FeisManager.vue';
import EntryManager from './components/admin/EntryManager.vue';
import CompetitionManager from './components/admin/CompetitionManager.vue';
import SiteSettings from './components/admin/SiteSettings.vue';
import CloudSync from './components/admin/CloudSync.vue';
import ScheduleGantt from './components/admin/ScheduleGantt.vue';
import FeisSettingsManager from './components/admin/FeisSettingsManager.vue';
import UserManager from './components/admin/UserManager.vue';
import AdjudicatorManager from './components/admin/AdjudicatorManager.vue';
import TeacherDashboard from './components/teacher/TeacherDashboard.vue';
import CheckInDashboard from './components/checkin/CheckInDashboard.vue';
import StageMonitor from './components/checkin/StageMonitor.vue';
import AuthModal from './components/auth/AuthModal.vue';
import EmailVerification from './components/auth/EmailVerification.vue';
import EmailVerificationBanner from './components/auth/EmailVerificationBanner.vue';
import AccountPage from './components/account/AccountPage.vue';
import { useAuthStore } from './stores/auth';
import type { Dancer, Competition, CartItem } from './models/types';

// Auth store
const auth = useAuthStore();

// Auth modal state
const showAuthModal = ref(false);
const authModalMode = ref<'login' | 'register'>('login');

// Initialize auth on mount and check for verification token in URL
onMounted(async () => {
  await auth.initialize();
  
  // Check for email verification token in URL
  const urlParams = new URLSearchParams(window.location.search);
  const token = urlParams.get('token');
  const path = window.location.pathname;
  
  if (path === '/verify-email' && token) {
    verificationToken.value = token;
    view.value = 'verify-email';
  }
});

// Handle email verification success
const handleVerified = () => {
  // Clear the URL params
  window.history.replaceState({}, '', '/');
  view.value = 'home';
};

const handleVerifyGoHome = () => {
  window.history.replaceState({}, '', '/');
  view.value = 'home';
};

// Auth modal handlers
const openLogin = () => {
  authModalMode.value = 'login';
  showAuthModal.value = true;
};

const openRegister = () => {
  authModalMode.value = 'register';
  showAuthModal.value = true;
};

const handleAuthSuccess = () => {
  showAuthModal.value = false;
};

// Navigation state
type ViewType = 'home' | 'registration' | 'judge' | 'tabulator' | 'admin' | 'teacher' | 'checkin' | 'stage-monitor' | 'verify-email' | 'account';
const view = ref<ViewType>('home');

// Stage Monitor Fullscreen state
const isStageFullscreen = ref(false);
const handleStageFullscreenChange = (isFullscreen: boolean) => {
  isStageFullscreen.value = isFullscreen;
};

// Mobile menu state
const mobileMenuOpen = ref(false);

// Close mobile menu when navigating
const navigateTo = (newView: ViewType) => {
  view.value = newView;
  mobileMenuOpen.value = false;
};

// Email verification token from URL
const verificationToken = ref<string | undefined>(undefined);

// Admin navigation state
type AdminViewType = 'feis-list' | 'feis-detail' | 'entries' | 'competitions' | 'syllabus' | 'settings' | 'cloud-sync' | 'scheduler' | 'feis-settings' | 'users' | 'adjudicators';
const adminView = ref<AdminViewType>('feis-list');
const selectedFeis = ref<{ id: string; name: string } | null>(null);

// Registration flow state
const currentDancer = ref<Partial<Dancer>>({});
const savedDancer = ref<Dancer | null>(null); // Dancer after saving to API
const selectedCompetitions = ref<Competition[]>([]);
const registrationStep = ref<'feis' | 'dancer-select' | 'profile' | 'select' | 'cart' | 'success'>('feis');
const registrationError = ref<string | null>(null);
const registrationLoading = ref(false);

// Existing dancers for selection
const existingDancers = ref<Dancer[]>([]);
const existingDancersLoading = ref(false);

// Feis selection for registration
interface FeisOption {
  id: string;
  name: string;
  date: string;
  location: string;
  competition_count: number;
}
const availableFeiseanna = ref<FeisOption[]>([]);
const selectedRegistrationFeis = ref<FeisOption | null>(null);
const feisCompetitions = ref<Competition[]>([]);
const feisLoading = ref(false);

// Fetch available feiseanna for registration
const fetchFeiseanna = async () => {
  feisLoading.value = true;
  try {
    const response = await fetch('/api/v1/feis');
    if (response.ok) {
      availableFeiseanna.value = await response.json();
      // Auto-select if only one feis
      if (availableFeiseanna.value.length === 1 && availableFeiseanna.value[0]) {
        await selectRegistrationFeis(availableFeiseanna.value[0]);
      }
    }
  } catch (error) {
    console.error('Failed to fetch feiseanna:', error);
  } finally {
    feisLoading.value = false;
  }
};

// Select a feis and load its competitions
const selectRegistrationFeis = async (feis: FeisOption) => {
  selectedRegistrationFeis.value = feis;
  feisLoading.value = true;
  try {
    const response = await fetch(`/api/v1/feis/${feis.id}/competitions`);
    if (response.ok) {
      feisCompetitions.value = await response.json();
      
      // If logged in, fetch existing dancers and show selection
      if (auth.isAuthenticated) {
        await fetchExistingDancers();
        registrationStep.value = 'dancer-select';
      } else {
        // Not logged in - go straight to profile creation
        registrationStep.value = 'profile';
      }
    }
  } catch (error) {
    console.error('Failed to fetch competitions:', error);
  } finally {
    feisLoading.value = false;
  }
};

// Fetch existing dancers for the logged-in user
const fetchExistingDancers = async () => {
  if (!auth.isAuthenticated) return;
  
  existingDancersLoading.value = true;
  try {
    const response = await auth.authFetch('/api/v1/dancers/mine');
    if (response.ok) {
      existingDancers.value = await response.json();
    }
  } catch (error) {
    console.error('Failed to fetch dancers:', error);
  } finally {
    existingDancersLoading.value = false;
  }
};

// Select an existing dancer for registration
const selectExistingDancer = (dancer: Dancer) => {
  savedDancer.value = dancer;
  currentDancer.value = dancer;
  registrationStep.value = 'select';
};

// Choose to create a new dancer
const createNewDancer = () => {
  currentDancer.value = {};
  savedDancer.value = null;
  registrationStep.value = 'profile';
};

// Cart items
const cartItems = computed<CartItem[]>(() => {
  const dancer = savedDancer.value || currentDancer.value as Dancer;
  return selectedCompetitions.value.map(comp => ({
    competition: comp,
    dancer: dancer,
    fee: 10
  }));
});

// Cart summary ref for resetting processing state
const cartSummaryRef = ref<{ resetProcessing: () => void } | null>(null);

// Handlers
const handleDancerSubmit = async (dancer: Partial<Dancer>) => {
  currentDancer.value = dancer;
  
  // If logged in, save dancer to API immediately
  if (auth.isAuthenticated) {
    registrationLoading.value = true;
    registrationError.value = null;
    try {
      const response = await auth.authFetch('/api/v1/dancers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: dancer.name,
          dob: dancer.dob,
          gender: dancer.gender,
          current_level: dancer.current_level,
          clrg_number: dancer.clrg_number || null
        })
      });
      
      if (response.ok) {
        savedDancer.value = await response.json();
        registrationStep.value = 'select';
      } else {
        const error = await response.json();
        registrationError.value = error.detail || 'Failed to save dancer profile';
      }
    } catch (error) {
      registrationError.value = 'Network error. Please try again.';
      console.error('Failed to create dancer:', error);
    } finally {
      registrationLoading.value = false;
    }
  } else {
    // Not logged in - proceed to selection (will prompt for login at checkout)
    registrationStep.value = 'select';
  }
};

const handleCompetitionSelect = (comps: Competition[]) => {
  selectedCompetitions.value = comps;
};

const handleCartRemove = (item: CartItem) => {
  selectedCompetitions.value = selectedCompetitions.value.filter(
    c => c.id !== item.competition.id
  );
};

const handleLoginRequired = () => {
  openLogin();
};

// Handle checkout completion from CartSummary (new Phase 3 flow)
const handleCheckoutComplete = (orderId: string) => {
  console.log('Checkout complete, order:', orderId);
  registrationStep.value = 'success';
};

const goToCart = () => {
  registrationStep.value = 'cart';
};

const backToFeis = () => {
  registrationStep.value = 'feis';
};

const backToDancerSelect = () => {
  registrationStep.value = 'dancer-select';
};

const backToProfile = () => {
  registrationStep.value = 'profile';
};

const backToSelect = () => {
  registrationStep.value = 'select';
};

const startNewRegistration = () => {
  // Reset registration state
  currentDancer.value = {};
  savedDancer.value = null;
  selectedCompetitions.value = [];
  registrationError.value = null;
  registrationStep.value = 'feis';
  fetchFeiseanna();
};

// Admin handlers
const handleFeisSelect = (feis: { id: string; name: string }) => {
  selectedFeis.value = feis;
  adminView.value = 'feis-detail';
};

const handleBackToFeisList = () => {
  selectedFeis.value = null;
  adminView.value = 'feis-list';
};

const handleSyllabusGenerated = (response: { generated_count: number; message: string }) => {
  console.log('Syllabus generated:', response);
  // Go back to competition view to see the new competitions
  adminView.value = 'competitions';
};
</script>

<template>
  <div class="min-h-screen bg-gradient-to-br from-slate-50 via-slate-100 to-slate-50">
    <!-- Navigation Bar -->
    <nav v-show="!isStageFullscreen" class="bg-gradient-to-r from-slate-800 to-slate-900 text-white shadow-xl sticky top-0 z-50">
      <div class="max-w-7xl mx-auto px-4">
        <div class="flex justify-between items-center h-16">
          <!-- Logo -->
          <button 
            @click="navigateTo('home')"
            class="font-black text-xl tracking-tight flex items-center gap-2 hover:text-emerald-400 transition-colors"
          >
            <span class="text-2xl">☘️</span>
            <span>Open<span class="text-emerald-400">Feis</span></span>
          </button>

          <!-- Desktop Navigation Links (hidden on mobile) -->
          <div class="hidden md:flex items-center gap-1">
            <button 
              @click="view = 'home'"
              :class="[
                'px-4 py-2 rounded-lg font-medium transition-all',
                view === 'home' 
                  ? 'bg-white/10 text-white' 
                  : 'text-slate-300 hover:text-white hover:bg-white/5'
              ]"
            >
              Home
            </button>
            <button 
              @click="view = 'registration'; startNewRegistration()"
              :class="[
                'px-4 py-2 rounded-lg font-medium transition-all',
                view === 'registration' 
                  ? 'bg-emerald-500 text-white' 
                  : 'text-slate-300 hover:text-white hover:bg-white/5'
              ]"
            >
              Register
            </button>
            <!-- Judge - show for adjudicators or in demo mode when not logged in -->
            <button 
              v-if="auth.canAccessJudge"
              @click="view = 'judge'"
              :class="[
                'px-4 py-2 rounded-lg font-medium transition-all',
                view === 'judge' 
                  ? 'bg-amber-500 text-white' 
                  : 'text-slate-300 hover:text-white hover:bg-white/5'
              ]"
            >
              Judge
            </button>
            <button 
              @click="view = 'tabulator'"
              :class="[
                'px-4 py-2 rounded-lg font-medium transition-all',
                view === 'tabulator' 
                  ? 'bg-orange-500 text-white' 
                  : 'text-slate-300 hover:text-white hover:bg-white/5'
              ]"
            >
              Tabulator
            </button>
            <!-- Teacher - show for teachers or in demo mode when not logged in -->
            <button 
              v-if="auth.canAccessTeacher"
              @click="view = 'teacher'"
              :class="[
                'px-4 py-2 rounded-lg font-medium transition-all',
                view === 'teacher' 
                  ? 'bg-violet-500 text-white' 
                  : 'text-slate-300 hover:text-white hover:bg-white/5'
              ]"
            >
              Teacher
            </button>
            <!-- Admin - show for organizers/admins or in demo mode when not logged in -->
            <button 
              v-if="auth.canAccessAdmin"
              @click="view = 'admin'; adminView = 'feis-list'"
              :class="[
                'px-4 py-2 rounded-lg font-medium transition-all',
                view === 'admin' 
                  ? 'bg-indigo-500 text-white' 
                  : 'text-slate-300 hover:text-white hover:bg-white/5'
              ]"
            >
              Admin
            </button>
            <!-- Check-In - show for organizers/admins or in demo mode when not logged in -->
            <button 
              v-if="auth.canAccessAdmin"
              @click="view = 'checkin'"
              :class="[
                'px-4 py-2 rounded-lg font-medium transition-all',
                view === 'checkin' 
                  ? 'bg-teal-500 text-white' 
                  : 'text-slate-300 hover:text-white hover:bg-white/5'
              ]"
            >
              Check-In
            </button>
            <!-- Stage Monitor - public access -->
            <button 
              @click="view = 'stage-monitor'"
              :class="[
                'px-4 py-2 rounded-lg font-medium transition-all',
                view === 'stage-monitor' 
                  ? 'bg-emerald-500 text-white' 
                  : 'text-slate-300 hover:text-white hover:bg-white/5'
              ]"
            >
              Stage
            </button>

            <!-- Separator -->
            <div class="w-px h-6 bg-white/20 mx-2"></div>

            <!-- Auth Section -->
            <template v-if="auth.isAuthenticated">
              <!-- User Menu -->
              <div class="flex items-center gap-3">
                <button
                  @click="view = 'account'"
                  :class="[
                    'px-4 py-2 rounded-lg font-medium transition-all flex items-center gap-2',
                    view === 'account' 
                      ? 'bg-white/10 text-white' 
                      : 'text-slate-300 hover:text-white hover:bg-white/5'
                  ]"
                >
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                  </svg>
                  <span class="hidden sm:inline">{{ auth.user?.name }}</span>
                </button>
                <button
                  @click="auth.logout"
                  class="px-4 py-2 rounded-lg font-medium text-slate-300 hover:text-white hover:bg-white/5 transition-all flex items-center gap-2"
                  title="Sign Out"
                >
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                  </svg>
                  <span class="hidden sm:inline">Sign Out</span>
                </button>
              </div>
            </template>
            <template v-else>
              <!-- Login/Register Buttons -->
              <button
                @click="openLogin"
                class="px-4 py-2 rounded-lg font-medium text-slate-300 hover:text-white hover:bg-white/5 transition-all"
              >
                Sign In
              </button>
              <button
                @click="openRegister"
                class="px-4 py-2 rounded-lg font-medium bg-emerald-500 text-white hover:bg-emerald-600 transition-all"
              >
                Register
              </button>
            </template>
          </div>

          <!-- Mobile Menu Button -->
          <button
            @click="mobileMenuOpen = !mobileMenuOpen"
            class="md:hidden p-2 rounded-lg text-slate-300 hover:text-white hover:bg-white/10 transition-all"
            :aria-expanded="mobileMenuOpen"
            aria-label="Toggle navigation menu"
          >
            <!-- Hamburger icon (shown when menu is closed) -->
            <svg v-if="!mobileMenuOpen" class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
            <!-- X icon (shown when menu is open) -->
            <svg v-else class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      <!-- Mobile Menu Panel -->
      <Transition
        enter-active-class="transition duration-200 ease-out"
        enter-from-class="opacity-0 -translate-y-2"
        enter-to-class="opacity-100 translate-y-0"
        leave-active-class="transition duration-150 ease-in"
        leave-from-class="opacity-100 translate-y-0"
        leave-to-class="opacity-0 -translate-y-2"
      >
        <div v-if="mobileMenuOpen" class="md:hidden border-t border-white/10">
          <div class="px-4 py-3 space-y-1">
            <!-- Navigation Links -->
            <button 
              @click="navigateTo('home')"
              :class="[
                'w-full text-left px-4 py-3 rounded-lg font-medium transition-all',
                view === 'home' 
                  ? 'bg-white/10 text-white' 
                  : 'text-slate-300 hover:text-white hover:bg-white/5'
              ]"
            >
              Home
            </button>
            <button 
              @click="navigateTo('registration'); startNewRegistration()"
              :class="[
                'w-full text-left px-4 py-3 rounded-lg font-medium transition-all',
                view === 'registration' 
                  ? 'bg-emerald-500 text-white' 
                  : 'text-slate-300 hover:text-white hover:bg-white/5'
              ]"
            >
              Register
            </button>
            <!-- Judge - show for adjudicators or in demo mode when not logged in -->
            <button 
              v-if="auth.canAccessJudge"
              @click="navigateTo('judge')"
              :class="[
                'w-full text-left px-4 py-3 rounded-lg font-medium transition-all',
                view === 'judge' 
                  ? 'bg-amber-500 text-white' 
                  : 'text-slate-300 hover:text-white hover:bg-white/5'
              ]"
            >
              Judge
            </button>
            <button 
              @click="navigateTo('tabulator')"
              :class="[
                'w-full text-left px-4 py-3 rounded-lg font-medium transition-all',
                view === 'tabulator' 
                  ? 'bg-orange-500 text-white' 
                  : 'text-slate-300 hover:text-white hover:bg-white/5'
              ]"
            >
              Tabulator
            </button>
            <!-- Teacher - show for teachers or in demo mode when not logged in -->
            <button 
              v-if="auth.canAccessTeacher"
              @click="navigateTo('teacher')"
              :class="[
                'w-full text-left px-4 py-3 rounded-lg font-medium transition-all',
                view === 'teacher' 
                  ? 'bg-violet-500 text-white' 
                  : 'text-slate-300 hover:text-white hover:bg-white/5'
              ]"
            >
              Teacher
            </button>
            <!-- Admin - show for organizers/admins or in demo mode when not logged in -->
            <button 
              v-if="auth.canAccessAdmin"
              @click="navigateTo('admin'); adminView = 'feis-list'"
              :class="[
                'w-full text-left px-4 py-3 rounded-lg font-medium transition-all',
                view === 'admin' 
                  ? 'bg-indigo-500 text-white' 
                  : 'text-slate-300 hover:text-white hover:bg-white/5'
              ]"
            >
              Admin
            </button>
            <!-- Check-In - show for organizers/admins or in demo mode when not logged in -->
            <button 
              v-if="auth.canAccessAdmin"
              @click="navigateTo('checkin')"
              :class="[
                'w-full text-left px-4 py-3 rounded-lg font-medium transition-all',
                view === 'checkin' 
                  ? 'bg-teal-500 text-white' 
                  : 'text-slate-300 hover:text-white hover:bg-white/5'
              ]"
            >
              Check-In
            </button>
            <!-- Stage Monitor - public access -->
            <button 
              @click="navigateTo('stage-monitor')"
              :class="[
                'w-full text-left px-4 py-3 rounded-lg font-medium transition-all',
                view === 'stage-monitor' 
                  ? 'bg-emerald-500 text-white' 
                  : 'text-slate-300 hover:text-white hover:bg-white/5'
              ]"
            >
              Stage Monitor
            </button>

            <!-- Separator -->
            <div class="h-px bg-white/10 my-3"></div>

            <!-- Auth Section -->
            <template v-if="auth.isAuthenticated">
              <!-- Account Link -->
              <button 
                @click="navigateTo('account')"
                :class="[
                  'w-full text-left px-4 py-3 rounded-lg font-medium transition-all flex items-center gap-2',
                  view === 'account' 
                    ? 'bg-white/10 text-white' 
                    : 'text-slate-300 hover:text-white hover:bg-white/5'
                ]"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
                My Account
              </button>
              <button
                @click="auth.logout(); mobileMenuOpen = false"
                class="w-full text-left px-4 py-3 rounded-lg font-medium text-slate-300 hover:text-white hover:bg-white/5 transition-all flex items-center gap-2"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                </svg>
                Sign Out
              </button>
            </template>
            <template v-else>
              <!-- Login/Register Buttons -->
              <button
                @click="openLogin(); mobileMenuOpen = false"
                class="w-full text-left px-4 py-3 rounded-lg font-medium text-slate-300 hover:text-white hover:bg-white/5 transition-all"
              >
                Sign In
              </button>
              <button
                @click="openRegister(); mobileMenuOpen = false"
                class="w-full px-4 py-3 rounded-lg font-medium bg-emerald-500 text-white hover:bg-emerald-600 transition-all text-center"
              >
                Create Account
              </button>
            </template>
          </div>
        </div>
      </Transition>
    </nav>

    <!-- Email Verification Banner -->
    <EmailVerificationBanner />

    <!-- Auth Warning Banner (e.g., default local admin password) -->
    <div v-if="auth.warning" class="max-w-7xl mx-auto px-4 pt-4">
      <div class="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-start gap-3">
        <svg class="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <p class="text-amber-800 text-sm font-medium flex-1">{{ auth.warning }}</p>
        <button
          type="button"
          @click="auth.dismissWarning()"
          class="text-amber-700/70 hover:text-amber-900"
          aria-label="Dismiss warning"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>

    <!-- Auth Modal -->
    <AuthModal 
      :show="showAuthModal" 
      :initial-mode="authModalMode"
      @close="showAuthModal = false"
      @success="handleAuthSuccess"
    />

    <!-- Main Content -->
    <main class="max-w-7xl mx-auto p-4 md:p-6">
      <!-- Home View -->
      <div v-if="view === 'home'" class="py-12">
        <div class="text-center mb-12">
          <h1 class="text-5xl font-black text-slate-800 mb-4">
            Welcome to <span class="text-emerald-600">Open</span><span class="text-slate-700">Feis</span>
          </h1>
          <p class="text-xl text-slate-600 max-w-2xl mx-auto">
            The modern standard for Irish Dance. Simple registration for parents, live schedules for dancers, and real-time results for everyone.
          </p>
        </div>

        <div class="grid md:grid-cols-3 gap-6 max-w-5xl mx-auto">
          <!-- Register Card -->
          <button 
            @click="view = 'registration'; startNewRegistration()"
            class="group bg-white rounded-2xl p-6 shadow-lg border border-slate-100 hover:shadow-xl hover:border-emerald-200 transition-all text-left"
          >
            <div class="w-14 h-14 rounded-xl bg-gradient-to-br from-emerald-400 to-teal-500 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
              <span class="text-2xl">📝</span>
            </div>
            <h3 class="text-xl font-bold text-slate-800 mb-2">Register Dancers</h3>
            <p class="text-slate-600 text-sm">
              Add dancer profiles and register for competitions with our smart eligibility picker.
            </p>
          </button>

          <!-- Stage Monitor Card - Public -->
          <button 
            @click="view = 'stage-monitor'"
            class="group bg-white rounded-2xl p-6 shadow-lg border border-slate-100 hover:shadow-xl hover:border-sky-200 transition-all text-left"
          >
            <div class="w-14 h-14 rounded-xl bg-gradient-to-br from-sky-400 to-blue-500 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
              <span class="text-2xl">📺</span>
            </div>
            <h3 class="text-xl font-bold text-slate-800 mb-2">Live Stage Monitor</h3>
            <p class="text-slate-600 text-sm">
              Track the action in real-time. See which competitions are on stage right now.
            </p>
          </button>

          <!-- Judge Card - only show to adjudicators or when not logged in (demo mode) -->
          <button 
            v-if="auth.canAccessJudge"
            @click="view = 'judge'"
            class="group bg-white rounded-2xl p-6 shadow-lg border border-slate-100 hover:shadow-xl hover:border-amber-200 transition-all text-left"
          >
            <div class="w-14 h-14 rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
              <span class="text-2xl">⚖️</span>
            </div>
            <h3 class="text-xl font-bold text-slate-800 mb-2">Judge Pad</h3>
            <p class="text-slate-600 text-sm">
              Offline-capable scoring pad for adjudicators. Syncs automatically when online.
            </p>
          </button>

          <!-- Tabulator Card - results are public, show to everyone -->
          <button 
            @click="view = 'tabulator'"
            class="group bg-white rounded-2xl p-6 shadow-lg border border-slate-100 hover:shadow-xl hover:border-orange-200 transition-all text-left"
          >
            <div class="w-14 h-14 rounded-xl bg-gradient-to-br from-orange-500 to-amber-600 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
              <span class="text-2xl">📊</span>
            </div>
            <h3 class="text-xl font-bold text-slate-800 mb-2">Tabulator</h3>
            <p class="text-slate-600 text-sm">
              Real-time results with Irish Points calculation, including Drop High/Low.
            </p>
          </button>
        </div>

        <!-- Admin Link (only for organizers/admins) -->
        <div v-if="auth.canAccessAdmin" class="text-center mt-8">
          <button 
            @click="view = 'admin'"
            class="text-slate-500 hover:text-indigo-600 text-sm font-medium transition-colors"
          >
            Go to Admin Dashboard →
          </button>
        </div>

        <!-- Login Prompt for non-authenticated users -->
        <div v-if="!auth.isAuthenticated" class="text-center mt-12 p-6 bg-white rounded-2xl shadow-lg max-w-md mx-auto border border-slate-100">
          <h3 class="text-lg font-bold text-slate-800 mb-2">Ready to get started?</h3>
          <p class="text-slate-600 text-sm mb-4">
            Create an account or sign in to register dancers and manage your feis experience.
          </p>
          <div class="flex gap-3 justify-center">
            <button
              @click="openLogin"
              class="px-6 py-2.5 rounded-xl font-medium border border-slate-300 text-slate-700 hover:bg-slate-50 transition-all"
            >
              Sign In
            </button>
            <button
              @click="openRegister"
              class="px-6 py-2.5 rounded-xl font-medium bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow-lg shadow-emerald-200 hover:shadow-xl transition-all"
            >
              Create Account
            </button>
          </div>
        </div>
      </div>

      <!-- Registration Flow -->
      <div v-else-if="view === 'registration'" class="py-8">
        <!-- Progress Steps -->
        <div class="flex items-center justify-center mb-8">
          <div class="flex items-center gap-1 sm:gap-2 flex-wrap justify-center">
            <!-- Step 1: Feis -->
            <button 
              @click="registrationStep = 'feis'"
              :class="[
                'flex items-center gap-1 sm:gap-2 px-3 sm:px-4 py-2 rounded-full font-medium transition-all text-sm',
                registrationStep === 'feis'
                  ? 'bg-emerald-600 text-white'
                  : selectedRegistrationFeis
                    ? 'bg-slate-200 text-slate-600 hover:bg-slate-300'
                    : 'bg-slate-100 text-slate-400'
              ]"
            >
              <span class="w-5 h-5 sm:w-6 sm:h-6 rounded-full bg-white/20 flex items-center justify-center text-xs sm:text-sm">1</span>
              <span class="hidden sm:inline">Feis</span>
            </button>
            <div class="w-2 sm:w-6 h-0.5 bg-slate-300"></div>
            
            <!-- Step 2: Dancer (only for authenticated users) -->
            <button 
              v-if="auth.isAuthenticated"
              @click="selectedRegistrationFeis ? registrationStep = 'dancer-select' : null"
              :class="[
                'flex items-center gap-1 sm:gap-2 px-3 sm:px-4 py-2 rounded-full font-medium transition-all text-sm',
                registrationStep === 'dancer-select'
                  ? 'bg-emerald-600 text-white'
                  : selectedRegistrationFeis
                    ? 'bg-slate-200 text-slate-600 hover:bg-slate-300'
                    : 'bg-slate-100 text-slate-400 cursor-not-allowed'
              ]"
            >
              <span class="w-5 h-5 sm:w-6 sm:h-6 rounded-full bg-white/20 flex items-center justify-center text-xs sm:text-sm">2</span>
              <span class="hidden sm:inline">Dancer</span>
            </button>
            <div v-if="auth.isAuthenticated" class="w-2 sm:w-6 h-0.5 bg-slate-300"></div>
            
            <!-- Step 3: Profile (only for new dancers) -->
            <button 
              v-if="!auth.isAuthenticated || registrationStep === 'profile' || (!savedDancer && registrationStep !== 'feis' && registrationStep !== 'dancer-select')"
              @click="selectedRegistrationFeis ? registrationStep = 'profile' : null"
              :class="[
                'flex items-center gap-1 sm:gap-2 px-3 sm:px-4 py-2 rounded-full font-medium transition-all text-sm',
                registrationStep === 'profile'
                  ? 'bg-emerald-600 text-white'
                  : selectedRegistrationFeis
                    ? 'bg-slate-200 text-slate-600 hover:bg-slate-300'
                    : 'bg-slate-100 text-slate-400 cursor-not-allowed'
              ]"
            >
              <span class="w-5 h-5 sm:w-6 sm:h-6 rounded-full bg-white/20 flex items-center justify-center text-xs sm:text-sm">{{ auth.isAuthenticated ? '3' : '2' }}</span>
              <span class="hidden sm:inline">Profile</span>
            </button>
            <div v-if="!auth.isAuthenticated || registrationStep === 'profile' || (!savedDancer && registrationStep !== 'feis' && registrationStep !== 'dancer-select')" class="w-2 sm:w-6 h-0.5 bg-slate-300"></div>
            
            <!-- Step 4: Select Competitions -->
            <button 
              @click="(savedDancer || currentDancer.name) ? registrationStep = 'select' : null"
              :class="[
                'flex items-center gap-1 sm:gap-2 px-3 sm:px-4 py-2 rounded-full font-medium transition-all text-sm',
                registrationStep === 'select'
                  ? 'bg-emerald-600 text-white'
                  : (savedDancer || currentDancer.name)
                    ? 'bg-slate-200 text-slate-600 hover:bg-slate-300'
                    : 'bg-slate-100 text-slate-400 cursor-not-allowed'
              ]"
            >
              <span class="w-5 h-5 sm:w-6 sm:h-6 rounded-full bg-white/20 flex items-center justify-center text-xs sm:text-sm">{{ auth.isAuthenticated ? (registrationStep === 'profile' || (!savedDancer && registrationStep !== 'feis' && registrationStep !== 'dancer-select') ? '4' : '3') : '3' }}</span>
              <span class="hidden sm:inline">Select</span>
            </button>
            <div class="w-2 sm:w-6 h-0.5 bg-slate-300"></div>
            
            <!-- Step 5: Checkout -->
            <button 
              @click="selectedCompetitions.length > 0 ? registrationStep = 'cart' : null"
              :class="[
                'flex items-center gap-1 sm:gap-2 px-3 sm:px-4 py-2 rounded-full font-medium transition-all text-sm',
                registrationStep === 'cart'
                  ? 'bg-emerald-600 text-white'
                  : selectedCompetitions.length > 0
                    ? 'bg-slate-200 text-slate-600 hover:bg-slate-300'
                    : 'bg-slate-100 text-slate-400 cursor-not-allowed'
              ]"
            >
              <span class="w-5 h-5 sm:w-6 sm:h-6 rounded-full bg-white/20 flex items-center justify-center text-xs sm:text-sm">{{ auth.isAuthenticated ? (registrationStep === 'profile' || (!savedDancer && registrationStep !== 'feis' && registrationStep !== 'dancer-select') ? '5' : '4') : '4' }}</span>
              <span class="hidden sm:inline">Checkout</span>
            </button>
          </div>
        </div>

        <!-- Error Banner -->
        <div v-if="registrationError" class="max-w-xl mx-auto mb-6">
          <div class="bg-red-50 border border-red-200 rounded-xl p-4 flex items-center gap-3">
            <svg class="w-5 h-5 text-red-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p class="text-red-700 text-sm font-medium">{{ registrationError }}</p>
            <button @click="registrationError = null" class="ml-auto text-red-400 hover:text-red-600">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        <!-- Step Content -->
        <div class="max-w-xl mx-auto">
          <!-- Step 0: Select Feis -->
          <div v-if="registrationStep === 'feis'" class="space-y-4">
            <div class="bg-white rounded-2xl shadow-lg border border-slate-100 overflow-hidden">
              <div class="bg-gradient-to-r from-emerald-600 to-teal-600 px-6 py-5">
                <h2 class="text-xl font-bold text-white flex items-center gap-2">
                  <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                  Select a Feis
                </h2>
                <p class="text-emerald-100 text-sm mt-1">Choose the feis you want to register for</p>
              </div>
              
              <div class="p-6">
                <div v-if="feisLoading" class="flex items-center justify-center py-12">
                  <div class="animate-spin rounded-full h-10 w-10 border-4 border-emerald-200 border-t-emerald-600"></div>
                </div>
                
                <div v-else-if="availableFeiseanna.length === 0" class="text-center py-12">
                  <div class="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4">
                    <svg class="w-8 h-8 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                  </div>
                  <h3 class="text-lg font-semibold text-slate-700 mb-2">No Feiseanna Available</h3>
                  <p class="text-slate-500 text-sm">
                    There are no feiseanna open for registration at this time.
                  </p>
                </div>
                
                <div v-else class="space-y-3">
                  <button
                    v-for="feis in availableFeiseanna"
                    :key="feis.id"
                    @click="selectRegistrationFeis(feis)"
                    class="w-full p-4 rounded-xl border-2 border-slate-200 hover:border-emerald-400 hover:bg-emerald-50 transition-all text-left"
                  >
                    <div class="flex items-center justify-between">
                      <div>
                        <h3 class="font-bold text-slate-800">{{ feis.name }}</h3>
                        <p class="text-sm text-slate-500">{{ feis.location }} • {{ feis.date }}</p>
                        <p class="text-xs text-emerald-600 mt-1">{{ feis.competition_count }} competitions</p>
                      </div>
                      <svg class="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                      </svg>
                    </div>
                  </button>
                </div>
              </div>
            </div>
          </div>

          <!-- Step: Dancer Selection (for authenticated users) -->
          <div v-else-if="registrationStep === 'dancer-select'" class="space-y-4">
            <button 
              @click="backToFeis"
              class="text-slate-600 hover:text-slate-800 text-sm font-medium flex items-center gap-1"
            >
              ← Back to Feis Selection
            </button>
            <div v-if="selectedRegistrationFeis" class="bg-emerald-50 border border-emerald-200 rounded-xl p-3 flex items-center gap-3">
              <svg class="w-5 h-5 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              <span class="text-sm font-medium text-emerald-700">Registering for: {{ selectedRegistrationFeis.name }}</span>
            </div>
            
            <div class="bg-white rounded-2xl shadow-lg border border-slate-100 overflow-hidden">
              <div class="bg-gradient-to-r from-emerald-600 to-teal-600 px-6 py-5">
                <h2 class="text-xl font-bold text-white flex items-center gap-2">
                  <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                  </svg>
                  Select a Dancer
                </h2>
                <p class="text-emerald-100 text-sm mt-1">Choose an existing dancer or create a new profile</p>
              </div>
              
              <div class="p-6">
                <!-- Loading -->
                <div v-if="existingDancersLoading" class="flex items-center justify-center py-8">
                  <div class="animate-spin rounded-full h-8 w-8 border-4 border-emerald-200 border-t-emerald-600"></div>
                </div>
                
                <div v-else class="space-y-4">
                  <!-- Existing Dancers -->
                  <div v-if="existingDancers.length > 0" class="space-y-3">
                    <h3 class="text-sm font-semibold text-slate-600 uppercase tracking-wide">Your Dancers</h3>
                    <button
                      v-for="dancer in existingDancers"
                      :key="dancer.id"
                      @click="selectExistingDancer(dancer)"
                      class="w-full p-4 rounded-xl border-2 border-slate-200 hover:border-emerald-400 hover:bg-emerald-50 transition-all text-left"
                    >
                      <div class="flex items-center justify-between">
                        <div>
                          <h4 class="font-bold text-slate-800">{{ dancer.name }}</h4>
                          <div class="flex flex-wrap gap-2 mt-1">
                            <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-800">
                              {{ dancer.gender === 'female' ? 'Girl' : dancer.gender === 'male' ? 'Boy' : 'Other' }}
                            </span>
                            <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-indigo-100 text-indigo-800 capitalize">
                              {{ dancer.current_level }}
                            </span>
                          </div>
                        </div>
                        <svg class="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                        </svg>
                      </div>
                    </button>
                  </div>
                  
                  <!-- Divider -->
                  <div v-if="existingDancers.length > 0" class="relative">
                    <div class="absolute inset-0 flex items-center">
                      <div class="w-full border-t border-slate-200"></div>
                    </div>
                    <div class="relative flex justify-center text-sm">
                      <span class="px-4 bg-white text-slate-500">or</span>
                    </div>
                  </div>
                  
                  <!-- Add New Dancer Button -->
                  <button
                    @click="createNewDancer"
                    class="w-full p-4 rounded-xl border-2 border-dashed border-slate-300 hover:border-emerald-400 hover:bg-emerald-50 transition-all text-center"
                  >
                    <div class="flex items-center justify-center gap-2 text-slate-600 hover:text-emerald-600">
                      <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
                      </svg>
                      <span class="font-semibold">Add a New Dancer</span>
                    </div>
                  </button>
                  
                  <!-- Tip for managing dancers -->
                  <p class="text-xs text-slate-500 text-center mt-4">
                    💡 Tip: You can manage all your dancers in <button @click="view = 'account'" class="text-emerald-600 hover:underline font-medium">My Account</button>
                  </p>
                </div>
              </div>
            </div>
          </div>

          <!-- Step 1: Dancer Profile -->
          <div v-else-if="registrationStep === 'profile'" class="space-y-4">
            <button 
              @click="auth.isAuthenticated ? backToDancerSelect() : backToFeis()"
              class="text-slate-600 hover:text-slate-800 text-sm font-medium flex items-center gap-1"
            >
              ← {{ auth.isAuthenticated ? 'Back to Dancer Selection' : 'Back to Feis Selection' }}
            </button>
            <div v-if="selectedRegistrationFeis" class="bg-emerald-50 border border-emerald-200 rounded-xl p-3 flex items-center gap-3">
              <svg class="w-5 h-5 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              <span class="text-sm font-medium text-emerald-700">Registering for: {{ selectedRegistrationFeis.name }}</span>
            </div>
            <DancerProfileForm 
              v-model="currentDancer"
              :feis-date="selectedRegistrationFeis?.date"
              @submit="handleDancerSubmit"
            />
            <div v-if="registrationLoading" class="flex items-center justify-center py-4">
              <div class="animate-spin rounded-full h-6 w-6 border-2 border-emerald-200 border-t-emerald-600 mr-2"></div>
              <span class="text-slate-600">Saving dancer profile...</span>
            </div>
          </div>

          <!-- Step 2: Competition Selection -->
          <div v-else-if="registrationStep === 'select'" class="space-y-4">
            <button 
              @click="auth.isAuthenticated && savedDancer && !currentDancer.name ? backToDancerSelect() : backToProfile()"
              class="text-slate-600 hover:text-slate-800 text-sm font-medium flex items-center gap-1"
            >
              ← {{ auth.isAuthenticated && savedDancer && !currentDancer.name ? 'Back to Dancer Selection' : 'Back to Profile' }}
            </button>
            <DanceRegistrationTable
              :dancer="savedDancer || currentDancer"
              :feis-id="selectedRegistrationFeis?.id || ''"
              :competitions="feisCompetitions"
              @select="handleCompetitionSelect"
            />
            <button
              v-if="selectedCompetitions.length > 0"
              @click="goToCart"
              class="w-full py-4 rounded-xl font-bold text-lg bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow-lg shadow-emerald-200 hover:shadow-xl transition-all"
            >
              Continue to Cart ({{ selectedCompetitions.length }})
            </button>
          </div>

          <!-- Step 3: Cart & Checkout -->
          <div v-else-if="registrationStep === 'cart'" class="space-y-4">
            <button 
              @click="backToSelect"
              class="text-slate-600 hover:text-slate-800 text-sm font-medium flex items-center gap-1"
            >
              ← Back to Selection
            </button>
            <CartSummary
              ref="cartSummaryRef"
              :items="cartItems"
              :feis-id="selectedRegistrationFeis?.id || ''"
              :is-logged-in="auth.isAuthenticated"
              @remove="handleCartRemove"
              @checkout-complete="handleCheckoutComplete"
              @login-required="handleLoginRequired"
            />
          </div>

          <!-- Step 4: Success -->
          <div v-else-if="registrationStep === 'success'" class="space-y-4">
            <div class="bg-white rounded-2xl shadow-lg border border-slate-100 overflow-hidden">
              <div class="bg-gradient-to-r from-emerald-500 to-teal-500 px-6 py-8 text-center">
                <div class="w-16 h-16 bg-white/20 rounded-full flex items-center justify-center mx-auto mb-4">
                  <svg class="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <h2 class="text-2xl font-bold text-white mb-2">Registration Complete! 🎉</h2>
                <p class="text-emerald-100">{{ savedDancer?.name }} is registered for {{ selectedRegistrationFeis?.name }}</p>
              </div>
              
              <div class="p-6 space-y-4">
                <div class="bg-slate-50 rounded-xl p-4">
                  <h3 class="font-semibold text-slate-700 mb-2">Registered Competitions:</h3>
                  <ul class="space-y-1">
                    <li v-for="comp in selectedCompetitions" :key="comp.id" class="text-sm text-slate-600 flex items-center gap-2">
                      <svg class="w-4 h-4 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                      </svg>
                      {{ comp.name }}
                    </li>
                  </ul>
                </div>
                
                <div class="bg-amber-50 border border-amber-200 rounded-xl p-4">
                  <div class="flex items-start gap-3">
                    <svg class="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <div>
                      <p class="font-medium text-amber-800">Next Steps</p>
                      <p class="text-sm text-amber-700 mt-1">
                        Your competitor number will be assigned by the organizer. You'll receive it at check-in on the day of the feis.
                      </p>
                    </div>
                  </div>
                </div>
                
                <div class="flex gap-3">
                  <button
                    @click="startNewRegistration"
                    class="flex-1 py-3 rounded-xl font-semibold bg-emerald-600 text-white hover:bg-emerald-700 transition-colors"
                  >
                    Register Another Dancer
                  </button>
                  <button
                    @click="view = 'home'"
                    class="flex-1 py-3 rounded-xl font-semibold bg-slate-200 text-slate-700 hover:bg-slate-300 transition-colors"
                  >
                    Return Home
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Judge View -->
      <div v-else-if="view === 'judge'">
        <!-- Access control: show JudgePad only for adjudicators or unauthenticated (demo mode) -->
        <template v-if="auth.canAccessJudge">
          <JudgePad />
        </template>
        <template v-else>
          <!-- Access Denied for non-adjudicators -->
          <div class="py-12">
            <div class="max-w-md mx-auto text-center">
              <div class="w-20 h-20 rounded-2xl bg-amber-100 flex items-center justify-center mx-auto mb-6">
                <svg class="w-10 h-10 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
              </div>
              <h2 class="text-2xl font-bold text-slate-800 mb-3">Adjudicator Access Only</h2>
              <p class="text-slate-600 mb-6">
                The Judge Pad is only available to registered adjudicators. 
                If you're an adjudicator, please contact the organizer to update your account role.
              </p>
              <button
                @click="view = 'home'"
                class="px-6 py-3 rounded-xl font-semibold bg-slate-800 text-white hover:bg-slate-700 transition-colors"
              >
                Return Home
              </button>
            </div>
          </div>
        </template>
      </div>

      <!-- Tabulator View -->
      <div v-else-if="view === 'tabulator'">
        <TabulatorDashboard />
      </div>

      <!-- Admin View -->
      <div v-else-if="view === 'admin'" class="py-8">
        <!-- Access control: show admin only for organizers/admins or unauthenticated (demo mode) -->
        <template v-if="auth.canAccessAdmin">
        <div class="max-w-6xl mx-auto">
          <!-- Feis List View -->
          <div v-if="adminView === 'feis-list'">
            <div class="flex items-center justify-between mb-6">
              <div>
                <h1 class="text-2xl font-bold text-slate-800">Admin Dashboard</h1>
                <p class="text-slate-600">Manage feiseanna, competitions, and entries</p>
              </div>
              <div class="flex gap-2">
              <!-- Users Button (Super Admin only) -->
              <button
                v-if="auth.isAdmin"
                @click="adminView = 'users'"
                class="px-4 py-2 rounded-lg bg-violet-100 text-violet-700 font-medium hover:bg-violet-200 transition-colors flex items-center gap-2"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                </svg>
                Users
              </button>
              <!-- Cloud Sync Button -->
              <button
                @click="adminView = 'cloud-sync'"
                class="px-4 py-2 rounded-lg bg-blue-100 text-blue-700 font-medium hover:bg-blue-200 transition-colors flex items-center gap-2"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
                Cloud Sync
              </button>
              <button
                v-if="auth.isAdmin"
                @click="adminView = 'settings'"
                class="px-4 py-2 rounded-lg bg-emerald-100 text-emerald-700 font-medium hover:bg-emerald-200 transition-colors flex items-center gap-2"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
                Settings
              </button>
            </div>
            </div>
            <FeisManager @select="handleFeisSelect" />
          </div>

          <!-- Feis Detail View (Action Selection) -->
          <div v-else-if="adminView === 'feis-detail' && selectedFeis">
            <div class="mb-6">
              <button
                @click="handleBackToFeisList"
                class="text-slate-600 hover:text-slate-800 text-sm font-medium flex items-center gap-1 mb-2"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
                </svg>
                Back to Feis List
              </button>
              <h1 class="text-2xl font-bold text-slate-800">{{ selectedFeis.name }}</h1>
              <p class="text-slate-600">Select what you'd like to manage</p>
            </div>

            <div class="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
              <!-- Entries -->
              <button
                @click="adminView = 'entries'"
                class="bg-white rounded-xl p-6 shadow-lg border border-slate-200 hover:border-emerald-300 hover:shadow-xl transition-all text-left"
              >
                <div class="w-12 h-12 rounded-lg bg-emerald-100 flex items-center justify-center mb-4">
                  <svg class="w-6 h-6 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                  </svg>
                </div>
                <h3 class="text-lg font-bold text-slate-800 mb-1">Registrations</h3>
                <p class="text-slate-600 text-sm">View entries, assign numbers, mark payments</p>
              </button>

              <!-- Competitions -->
              <button
                @click="adminView = 'competitions'"
                class="bg-white rounded-xl p-6 shadow-lg border border-slate-200 hover:border-indigo-300 hover:shadow-xl transition-all text-left"
              >
                <div class="w-12 h-12 rounded-lg bg-indigo-100 flex items-center justify-center mb-4">
                  <svg class="w-6 h-6 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                  </svg>
                </div>
                <h3 class="text-lg font-bold text-slate-800 mb-1">Competitions</h3>
                <p class="text-slate-600 text-sm">Edit, delete, or manage competitions</p>
              </button>

              <!-- Scheduler -->
              <button
                @click="adminView = 'scheduler'"
                class="bg-white rounded-xl p-6 shadow-lg border border-slate-200 hover:border-violet-300 hover:shadow-xl transition-all text-left"
              >
                <div class="w-12 h-12 rounded-lg bg-violet-100 flex items-center justify-center mb-4">
                  <svg class="w-6 h-6 text-violet-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                </div>
                <h3 class="text-lg font-bold text-slate-800 mb-1">Schedule Builder</h3>
                <p class="text-slate-600 text-sm">Visual drag-and-drop scheduler</p>
              </button>

              <!-- Syllabus Generator -->
              <button
                @click="adminView = 'syllabus'"
                class="bg-white rounded-xl p-6 shadow-lg border border-slate-200 hover:border-orange-300 hover:shadow-xl transition-all text-left"
              >
                <div class="w-12 h-12 rounded-lg bg-orange-100 flex items-center justify-center mb-4">
                  <svg class="w-6 h-6 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                  </svg>
                </div>
                <h3 class="text-lg font-bold text-slate-800 mb-1">Generate Syllabus</h3>
                <p class="text-slate-600 text-sm">Auto-create competitions from template</p>
              </button>

              <!-- Feis Settings -->
              <button
                @click="adminView = 'feis-settings'"
                class="bg-white rounded-xl p-6 shadow-lg border border-slate-200 hover:border-rose-300 hover:shadow-xl transition-all text-left"
              >
                <div class="w-12 h-12 rounded-lg bg-rose-100 flex items-center justify-center mb-4">
                  <svg class="w-6 h-6 text-rose-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                </div>
                <h3 class="text-lg font-bold text-slate-800 mb-1">Settings</h3>
                <p class="text-slate-600 text-sm">Pricing, fees, registration & payments</p>
              </button>

              <!-- Adjudicators -->
              <button
                @click="adminView = 'adjudicators'"
                class="bg-white rounded-xl p-6 shadow-lg border border-slate-200 hover:border-blue-300 hover:shadow-xl transition-all text-left"
              >
                <div class="w-12 h-12 rounded-lg bg-blue-100 flex items-center justify-center mb-4">
                  <svg class="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                  </svg>
                </div>
                <h3 class="text-lg font-bold text-slate-800 mb-1">Adjudicators</h3>
                <p class="text-slate-600 text-sm">Manage judge roster & availability</p>
              </button>
            </div>
          </div>

          <!-- Entry Manager View -->
          <div v-else-if="adminView === 'entries' && selectedFeis">
            <EntryManager
              :feis-id="selectedFeis.id"
              :feis-name="selectedFeis.name"
              @back="adminView = 'feis-detail'"
            />
          </div>

          <!-- Competition Manager View -->
          <div v-else-if="adminView === 'competitions' && selectedFeis">
            <CompetitionManager
              :feis-id="selectedFeis.id"
              :feis-name="selectedFeis.name"
              @back="adminView = 'feis-detail'"
              @generate-syllabus="adminView = 'syllabus'"
            />
          </div>

          <!-- Syllabus Generator View -->
          <div v-else-if="adminView === 'syllabus' && selectedFeis">
            <div class="mb-6">
              <button
                @click="adminView = 'feis-detail'"
                class="text-slate-600 hover:text-slate-800 text-sm font-medium flex items-center gap-1 mb-2"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
                </svg>
                Back to {{ selectedFeis.name }}
              </button>
            </div>
            <SyllabusGenerator
              :feis-id="selectedFeis.id"
              :feis-name="selectedFeis.name"
              @generated="handleSyllabusGenerated"
            />
          </div>

          <!-- Schedule Builder View -->
          <div v-else-if="adminView === 'scheduler' && selectedFeis">
            <div class="mb-6">
              <button
                @click="adminView = 'feis-detail'"
                class="text-slate-600 hover:text-slate-800 text-sm font-medium flex items-center gap-1 mb-2"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
                </svg>
                Back to {{ selectedFeis.name }}
              </button>
            </div>
            <ScheduleGantt
              :feis-id="selectedFeis.id"
              :feis-name="selectedFeis.name"
              @saved="() => {}"
            />
          </div>

          <!-- Feis Settings View -->
          <div v-else-if="adminView === 'feis-settings' && selectedFeis">
            <div class="mb-6">
              <button
                @click="adminView = 'feis-detail'"
                class="text-slate-600 hover:text-slate-800 text-sm font-medium flex items-center gap-1 mb-2"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
                </svg>
                Back to {{ selectedFeis.name }}
              </button>
            </div>
            <FeisSettingsManager
              :feis-id="selectedFeis.id"
              :feis-name="selectedFeis.name"
              @close="adminView = 'feis-detail'"
            />
          </div>

          <!-- Adjudicator Manager View -->
          <div v-else-if="adminView === 'adjudicators' && selectedFeis">
            <div class="mb-6">
              <button
                @click="adminView = 'feis-detail'"
                class="text-slate-600 hover:text-slate-800 text-sm font-medium flex items-center gap-1 mb-2"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
                </svg>
                Back to {{ selectedFeis.name }}
              </button>
            </div>
            <AdjudicatorManager
              :feis-id="selectedFeis.id"
              :feis-name="selectedFeis.name"
              @close="adminView = 'feis-detail'"
            />
          </div>

          <!-- Site Settings View (Super Admin Only) -->
          <div v-else-if="adminView === 'settings'">
            <SiteSettings @back="adminView = 'feis-list'" />
          </div>

          <!-- Cloud Sync View -->
          <div v-else-if="adminView === 'cloud-sync'">
            <div class="mb-6">
              <button
                @click="adminView = 'feis-list'"
                class="text-slate-600 hover:text-slate-800 text-sm font-medium flex items-center gap-1 mb-2"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
                </svg>
                Back to Admin Dashboard
              </button>
            </div>
            <CloudSync />
          </div>

          <!-- User Manager View (Super Admin Only) -->
          <div v-else-if="adminView === 'users'">
            <UserManager @back="adminView = 'feis-list'" />
          </div>
        </div>
        </template>
        <template v-else>
          <!-- Access Denied for non-organizers -->
          <div class="py-12">
            <div class="max-w-md mx-auto text-center">
              <div class="w-20 h-20 rounded-2xl bg-indigo-100 flex items-center justify-center mx-auto mb-6">
                <svg class="w-10 h-10 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
              </div>
              <h2 class="text-2xl font-bold text-slate-800 mb-3">Organizer Access Only</h2>
              <p class="text-slate-600 mb-6">
                The Admin Dashboard is only available to feis organizers and administrators.
                If you're an organizer, please contact an administrator to update your account role.
              </p>
              <button
                @click="view = 'home'"
                class="px-6 py-3 rounded-xl font-semibold bg-slate-800 text-white hover:bg-slate-700 transition-colors"
              >
                Return Home
              </button>
            </div>
          </div>
        </template>
      </div>

      <!-- Teacher View -->
      <div v-else-if="view === 'teacher'" class="py-8">
        <!-- Access control: show teacher dashboard only for teachers or unauthenticated (demo mode) -->
        <template v-if="auth.canAccessTeacher">
          <TeacherDashboard />
        </template>
        <template v-else>
          <!-- Access Denied for non-teachers -->
          <div class="py-12">
            <div class="max-w-md mx-auto text-center">
              <div class="w-20 h-20 rounded-2xl bg-violet-100 flex items-center justify-center mx-auto mb-6">
                <svg class="w-10 h-10 text-violet-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
              </div>
              <h2 class="text-2xl font-bold text-slate-800 mb-3">Teacher Access Only</h2>
              <p class="text-slate-600 mb-6">
                The Teacher Dashboard is only available to registered teachers. 
                If you're a teacher, please contact an administrator to update your account role.
              </p>
              <button
                @click="view = 'home'"
                class="px-6 py-3 rounded-xl font-semibold bg-slate-800 text-white hover:bg-slate-700 transition-colors"
              >
                Return Home
              </button>
            </div>
          </div>
        </template>
      </div>

      <!-- Check-In Dashboard View -->
      <div v-else-if="view === 'checkin'" class="py-8">
        <!-- Access control: show check-in only for organizers/admins or unauthenticated (demo mode) -->
        <template v-if="auth.canAccessAdmin">
          <CheckInDashboard />
        </template>
        <template v-else>
          <!-- Access Denied -->
          <div class="py-12">
            <div class="max-w-md mx-auto text-center">
              <div class="w-20 h-20 rounded-2xl bg-teal-100 flex items-center justify-center mx-auto mb-6">
                <svg class="w-10 h-10 text-teal-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
              </div>
              <h2 class="text-2xl font-bold text-slate-800 mb-3">Organizer Access Only</h2>
              <p class="text-slate-600 mb-6">
                The Check-In Dashboard is only available to event organizers and administrators.
              </p>
              <button
                @click="view = 'home'"
                class="px-6 py-3 rounded-xl font-semibold bg-slate-800 text-white hover:bg-slate-700 transition-colors"
              >
                Return Home
              </button>
            </div>
          </div>
        </template>
      </div>

      <!-- Stage Monitor View (Public) -->
      <div v-else-if="view === 'stage-monitor'" class="min-h-screen -mt-8 -mx-4 sm:-mx-6 lg:-mx-8">
        <StageMonitor @fullscreen-change="handleStageFullscreenChange" />
      </div>

      <!-- Email Verification View -->
      <div v-else-if="view === 'verify-email'" class="py-8">
        <EmailVerification 
          :token="verificationToken"
          @verified="handleVerified"
          @go-home="handleVerifyGoHome"
        />
      </div>

      <!-- Account View -->
      <div v-else-if="view === 'account'" class="py-8">
        <template v-if="auth.isAuthenticated">
          <AccountPage />
        </template>
        <template v-else>
          <!-- Not logged in - prompt to log in -->
          <div class="py-12">
            <div class="max-w-md mx-auto text-center">
              <div class="w-20 h-20 rounded-2xl bg-slate-100 flex items-center justify-center mx-auto mb-6">
                <svg class="w-10 h-10 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
              </div>
              <h2 class="text-2xl font-bold text-slate-800 mb-3">Sign In Required</h2>
              <p class="text-slate-600 mb-6">
                Please sign in to access your account settings, manage dancers, and view registration history.
              </p>
              <div class="flex gap-3 justify-center">
                <button
                  @click="openLogin"
                  class="px-6 py-3 rounded-xl font-semibold bg-emerald-600 text-white hover:bg-emerald-700 transition-colors"
                >
                  Sign In
                </button>
                <button
                  @click="openRegister"
                  class="px-6 py-3 rounded-xl font-semibold bg-slate-200 text-slate-700 hover:bg-slate-300 transition-colors"
                >
                  Create Account
                </button>
              </div>
            </div>
          </div>
        </template>
      </div>
    </main>

    <!-- Footer -->
    <footer class="mt-auto py-6 text-center text-slate-500 text-sm">
      <p>
        Open Feis v0.2.1 • Built with ☘️ for the Irish Dance Community
      </p>
    </footer>
  </div>
</template>

<style>
/* Base Styles */
body {
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  margin: 0;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* Custom scrollbar */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: #f1f5f9;
  border-radius: 4px;
}

::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}
</style>
