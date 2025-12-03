<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import JudgePad from './components/judge/JudgePad.vue';
import TabulatorDashboard from './components/tabulator/TabulatorDashboard.vue';
import DancerProfileForm from './components/registration/DancerProfileForm.vue';
import EligibilityPicker from './components/registration/EligibilityPicker.vue';
import CartSummary from './components/registration/CartSummary.vue';
import SyllabusGenerator from './components/admin/SyllabusGenerator.vue';
import FeisManager from './components/admin/FeisManager.vue';
import EntryManager from './components/admin/EntryManager.vue';
import CompetitionManager from './components/admin/CompetitionManager.vue';
import SiteSettings from './components/admin/SiteSettings.vue';
import AuthModal from './components/auth/AuthModal.vue';
import EmailVerification from './components/auth/EmailVerification.vue';
import EmailVerificationBanner from './components/auth/EmailVerificationBanner.vue';
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
type ViewType = 'home' | 'registration' | 'judge' | 'tabulator' | 'admin' | 'verify-email';
const view = ref<ViewType>('home');

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
type AdminViewType = 'feis-list' | 'feis-detail' | 'entries' | 'competitions' | 'syllabus' | 'settings';
const adminView = ref<AdminViewType>('feis-list');
const selectedFeis = ref<{ id: string; name: string } | null>(null);

// Registration flow state
const currentDancer = ref<Partial<Dancer>>({});
const selectedCompetitions = ref<Competition[]>([]);
const registrationStep = ref<'profile' | 'select' | 'cart'>('profile');

// Mock data for demo
const mockFeisId = 'feis-001';
const mockCompetitions: Competition[] = [
  { id: 'c1', feis_id: mockFeisId, name: 'Girls U8 Reel (Beginner)', min_age: 6, max_age: 8, level: 'beginner', gender: 'female' },
  { id: 'c2', feis_id: mockFeisId, name: 'Girls U8 Light Jig (Beginner)', min_age: 6, max_age: 8, level: 'beginner', gender: 'female' },
  { id: 'c3', feis_id: mockFeisId, name: 'Girls U8 Slip Jig (Beginner)', min_age: 6, max_age: 8, level: 'beginner', gender: 'female' },
  { id: 'c4', feis_id: mockFeisId, name: 'Girls U10 Reel (Novice)', min_age: 8, max_age: 10, level: 'novice', gender: 'female' },
  { id: 'c5', feis_id: mockFeisId, name: 'Girls U10 Light Jig (Novice)', min_age: 8, max_age: 10, level: 'novice', gender: 'female' },
  { id: 'c6', feis_id: mockFeisId, name: 'Boys U10 Reel (Beginner)', min_age: 8, max_age: 10, level: 'beginner', gender: 'male' },
  { id: 'c7', feis_id: mockFeisId, name: 'Boys U10 Light Jig (Beginner)', min_age: 8, max_age: 10, level: 'beginner', gender: 'male' },
  { id: 'c8', feis_id: mockFeisId, name: 'Girls U12 Reel (Prizewinner)', min_age: 10, max_age: 12, level: 'prizewinner', gender: 'female' },
  { id: 'c9', feis_id: mockFeisId, name: 'Girls U12 Hornpipe (Prizewinner)', min_age: 10, max_age: 12, level: 'prizewinner', gender: 'female' },
  { id: 'c10', feis_id: mockFeisId, name: 'Boys U12 Championship', min_age: 10, max_age: 12, level: 'championship', gender: 'male' },
];

// Cart items
const cartItems = computed<CartItem[]>(() => {
  return selectedCompetitions.value.map(comp => ({
    competition: comp,
    dancer: currentDancer.value as Dancer,
    fee: 10
  }));
});

// Handlers
const handleDancerSubmit = (dancer: Partial<Dancer>) => {
  currentDancer.value = dancer;
  registrationStep.value = 'select';
};

const handleCompetitionSelect = (comps: Competition[]) => {
  selectedCompetitions.value = comps;
};

const handleCartRemove = (item: CartItem) => {
  selectedCompetitions.value = selectedCompetitions.value.filter(
    c => c.id !== item.competition.id
  );
};

const handleCheckout = () => {
  alert('Checkout flow would open Stripe here!');
};

const goToCart = () => {
  registrationStep.value = 'cart';
};

const backToProfile = () => {
  registrationStep.value = 'profile';
};

const backToSelect = () => {
  registrationStep.value = 'select';
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
    <nav class="bg-gradient-to-r from-slate-800 to-slate-900 text-white shadow-xl sticky top-0 z-50">
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
              @click="view = 'registration'; registrationStep = 'profile'"
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
              v-if="!auth.isAuthenticated || auth.canAccessJudge"
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
                  ? 'bg-violet-500 text-white' 
                  : 'text-slate-300 hover:text-white hover:bg-white/5'
              ]"
            >
              Tabulator
            </button>
            <!-- Admin - show for organizers/admins or in demo mode when not logged in -->
            <button 
              v-if="!auth.isAuthenticated || auth.canAccessAdmin"
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

            <!-- Separator -->
            <div class="w-px h-6 bg-white/20 mx-2"></div>

            <!-- Auth Section -->
            <template v-if="auth.isAuthenticated">
              <!-- User Menu -->
              <div class="flex items-center gap-3">
                <div class="text-right hidden sm:block">
                  <p class="text-sm font-medium text-white">{{ auth.user?.name }}</p>
                  <p class="text-xs text-slate-400 capitalize">{{ auth.user?.role?.replace('_', ' ') }}</p>
                </div>
                <button
                  @click="auth.logout"
                  class="px-4 py-2 rounded-lg font-medium text-slate-300 hover:text-white hover:bg-white/5 transition-all flex items-center gap-2"
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
              @click="navigateTo('registration'); registrationStep = 'profile'"
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
              v-if="!auth.isAuthenticated || auth.canAccessJudge"
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
                  ? 'bg-violet-500 text-white' 
                  : 'text-slate-300 hover:text-white hover:bg-white/5'
              ]"
            >
              Tabulator
            </button>
            <!-- Admin - show for organizers/admins or in demo mode when not logged in -->
            <button 
              v-if="!auth.isAuthenticated || auth.canAccessAdmin"
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

            <!-- Separator -->
            <div class="h-px bg-white/10 my-3"></div>

            <!-- Auth Section -->
            <template v-if="auth.isAuthenticated">
              <!-- User Info -->
              <div class="px-4 py-3">
                <p class="text-sm font-medium text-white">{{ auth.user?.name }}</p>
                <p class="text-xs text-slate-400 capitalize">{{ auth.user?.role?.replace('_', ' ') }}</p>
              </div>
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
            A modern, local-first Irish Dance competition platform. 
            Resilient scoring, seamless registration, and transparent results.
          </p>
        </div>

        <div class="grid md:grid-cols-3 gap-6 max-w-4xl mx-auto">
          <!-- Register Card -->
          <button 
            @click="view = 'registration'"
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

          <!-- Judge Card - only show to adjudicators or when not logged in (demo mode) -->
          <button 
            v-if="!auth.isAuthenticated || auth.canAccessJudge"
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
            class="group bg-white rounded-2xl p-6 shadow-lg border border-slate-100 hover:shadow-xl hover:border-violet-200 transition-all text-left"
          >
            <div class="w-14 h-14 rounded-xl bg-gradient-to-br from-violet-400 to-purple-500 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
              <span class="text-2xl">📊</span>
            </div>
            <h3 class="text-xl font-bold text-slate-800 mb-2">Tabulator</h3>
            <p class="text-slate-600 text-sm">
              Real-time results with Irish Points calculation, including Drop High/Low.
            </p>
          </button>
        </div>

        <!-- Admin Link (only for organizers/admins) -->
        <div v-if="!auth.isAuthenticated || auth.canAccessAdmin" class="text-center mt-8">
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
          <div class="flex items-center gap-2">
            <button 
              @click="registrationStep = 'profile'"
              :class="[
                'flex items-center gap-2 px-4 py-2 rounded-full font-medium transition-all',
                registrationStep === 'profile'
                  ? 'bg-emerald-600 text-white'
                  : 'bg-slate-200 text-slate-600 hover:bg-slate-300'
              ]"
            >
              <span class="w-6 h-6 rounded-full bg-white/20 flex items-center justify-center text-sm">1</span>
              Profile
            </button>
            <div class="w-8 h-0.5 bg-slate-300"></div>
            <button 
              @click="currentDancer.name ? registrationStep = 'select' : null"
              :class="[
                'flex items-center gap-2 px-4 py-2 rounded-full font-medium transition-all',
                registrationStep === 'select'
                  ? 'bg-emerald-600 text-white'
                  : currentDancer.name
                    ? 'bg-slate-200 text-slate-600 hover:bg-slate-300'
                    : 'bg-slate-100 text-slate-400 cursor-not-allowed'
              ]"
            >
              <span class="w-6 h-6 rounded-full bg-white/20 flex items-center justify-center text-sm">2</span>
              Select
            </button>
            <div class="w-8 h-0.5 bg-slate-300"></div>
            <button 
              @click="selectedCompetitions.length > 0 ? registrationStep = 'cart' : null"
              :class="[
                'flex items-center gap-2 px-4 py-2 rounded-full font-medium transition-all',
                registrationStep === 'cart'
                  ? 'bg-emerald-600 text-white'
                  : selectedCompetitions.length > 0
                    ? 'bg-slate-200 text-slate-600 hover:bg-slate-300'
                    : 'bg-slate-100 text-slate-400 cursor-not-allowed'
              ]"
            >
              <span class="w-6 h-6 rounded-full bg-white/20 flex items-center justify-center text-sm">3</span>
              Checkout
            </button>
          </div>
        </div>

        <!-- Step Content -->
        <div class="max-w-xl mx-auto">
          <!-- Step 1: Dancer Profile -->
          <div v-if="registrationStep === 'profile'">
            <DancerProfileForm 
              v-model="currentDancer"
              @submit="handleDancerSubmit"
            />
          </div>

          <!-- Step 2: Competition Selection -->
          <div v-else-if="registrationStep === 'select'" class="space-y-4">
            <button 
              @click="backToProfile"
              class="text-slate-600 hover:text-slate-800 text-sm font-medium flex items-center gap-1"
            >
              ← Back to Profile
            </button>
            <EligibilityPicker
              :dancer="currentDancer"
              :feis-id="mockFeisId"
              :competitions="mockCompetitions"
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
              :items="cartItems"
              @remove="handleCartRemove"
              @checkout="handleCheckout"
            />
          </div>
        </div>
      </div>

      <!-- Judge View -->
      <div v-else-if="view === 'judge'">
        <!-- Access control: show JudgePad only for adjudicators or unauthenticated (demo mode) -->
        <template v-if="!auth.isAuthenticated || auth.canAccessJudge">
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
        <template v-if="!auth.isAuthenticated || auth.canAccessAdmin">
        <div class="max-w-6xl mx-auto">
          <!-- Feis List View -->
          <div v-if="adminView === 'feis-list'">
            <div class="flex items-center justify-between mb-6">
              <div>
                <h1 class="text-2xl font-bold text-slate-800">Admin Dashboard</h1>
                <p class="text-slate-600">Manage feiseanna, competitions, and entries</p>
              </div>
              <div class="flex gap-2">
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
              <a 
                href="/admin" 
                target="_blank"
                class="px-4 py-2 rounded-lg bg-slate-200 text-slate-700 font-medium hover:bg-slate-300 transition-colors flex items-center gap-2"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
                SQLAdmin
              </a>
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

            <div class="grid md:grid-cols-3 gap-6">
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

              <!-- Syllabus Generator -->
              <button
                @click="adminView = 'syllabus'"
                class="bg-white rounded-xl p-6 shadow-lg border border-slate-200 hover:border-violet-300 hover:shadow-xl transition-all text-left"
              >
                <div class="w-12 h-12 rounded-lg bg-violet-100 flex items-center justify-center mb-4">
                  <svg class="w-6 h-6 text-violet-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                  </svg>
                </div>
                <h3 class="text-lg font-bold text-slate-800 mb-1">Generate Syllabus</h3>
                <p class="text-slate-600 text-sm">Auto-create competitions from template</p>
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

          <!-- Site Settings View (Super Admin Only) -->
          <div v-else-if="adminView === 'settings'">
            <SiteSettings @back="adminView = 'feis-list'" />
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

      <!-- Email Verification View -->
      <div v-else-if="view === 'verify-email'" class="py-8">
        <EmailVerification 
          :token="verificationToken"
          @verified="handleVerified"
          @go-home="handleVerifyGoHome"
        />
      </div>
    </main>

    <!-- Footer -->
    <footer class="mt-auto py-6 text-center text-slate-500 text-sm">
      <p>
        Open Feis v0.2.0 • Built with ☘️ for the Irish Dance Community
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
