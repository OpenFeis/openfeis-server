<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { useAuthStore } from '../../stores/auth';
import type { User, RoleType } from '../../models/types';

const auth = useAuthStore();

const emit = defineEmits<{
  (e: 'back'): void;
}>();

// State
const loading = ref(false);
const users = ref<User[]>([]);
const searchQuery = ref('');
const searchTimeout = ref<number | null>(null);
const selectedRole = ref<RoleType | ''>('');

// Modal state
const showEditModal = ref(false);
const editingUser = ref<User | null>(null);
const newRole = ref<RoleType | ''>('');
const saving = ref(false);
const saveError = ref<string | null>(null);
const saveSuccess = ref(false);

// Role options
const roleOptions: { value: RoleType; label: string; color: string }[] = [
  { value: 'parent', label: 'Parent', color: 'bg-slate-100 text-slate-700' },
  { value: 'teacher', label: 'Teacher', color: 'bg-violet-100 text-violet-700' },
  { value: 'adjudicator', label: 'Adjudicator', color: 'bg-amber-100 text-amber-700' },
  { value: 'organizer', label: 'Organizer', color: 'bg-indigo-100 text-indigo-700' },
  { value: 'super_admin', label: 'Super Admin', color: 'bg-rose-100 text-rose-700' },
];

// Get role color
const getRoleColor = (role: RoleType): string => {
  return roleOptions.find(r => r.value === role)?.color || 'bg-slate-100 text-slate-700';
};

// Search users
const searchUsers = async () => {
  loading.value = true;
  
  try {
    const params = new URLSearchParams();
    if (searchQuery.value) params.append('search', searchQuery.value);
    if (selectedRole.value) params.append('role', selectedRole.value);
    params.append('limit', '100');
    
    const response = await fetch(`/api/v1/users?${params.toString()}`);
    if (response.ok) {
      users.value = await response.json();
    }
  } catch (e) {
    console.error('Failed to search users:', e);
  } finally {
    loading.value = false;
  }
};

// Debounced search
const onSearchInput = () => {
  if (searchTimeout.value) {
    clearTimeout(searchTimeout.value);
  }
  searchTimeout.value = window.setTimeout(() => {
    searchUsers();
  }, 300);
};

// Open edit modal
const openEditModal = (user: User) => {
  editingUser.value = user;
  newRole.value = user.role;
  saveError.value = null;
  saveSuccess.value = false;
  showEditModal.value = true;
};

// Save role change
const saveRoleChange = async () => {
  if (!editingUser.value || !newRole.value) return;
  
  saving.value = true;
  saveError.value = null;
  saveSuccess.value = false;
  
  try {
    const response = await auth.authFetch(`/api/v1/users/${editingUser.value.id}`, {
      method: 'PUT',
      body: JSON.stringify({ role: newRole.value })
    });
    
    if (response.ok) {
      // Update local list
      const idx = users.value.findIndex(u => u.id === editingUser.value!.id);
      const existingUser = users.value[idx];
      if (idx !== -1 && newRole.value && existingUser) {
        users.value[idx] = { 
          id: existingUser.id,
          email: existingUser.email,
          name: existingUser.name,
          role: newRole.value,
          email_verified: existingUser.email_verified
        };
      }
      saveSuccess.value = true;
      
      // Close after brief delay
      setTimeout(() => {
        showEditModal.value = false;
      }, 1000);
    } else {
      const err = await response.json();
      saveError.value = err.detail || 'Failed to update user role';
    }
  } catch (e) {
    saveError.value = 'Network error. Please try again.';
  } finally {
    saving.value = false;
  }
};

// Stats
const stats = computed(() => {
  const byRole: Record<string, number> = {};
  for (const user of users.value) {
    byRole[user.role] = (byRole[user.role] || 0) + 1;
  }
  return byRole;
});

onMounted(() => {
  searchUsers();
});
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <button
          @click="emit('back')"
          class="text-slate-600 hover:text-slate-800 text-sm font-medium flex items-center gap-1 mb-2"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
          </svg>
          Back to Admin Dashboard
        </button>
        <h1 class="text-2xl font-bold text-slate-800">User Management</h1>
        <p class="text-slate-600">Search users and manage their roles</p>
      </div>
    </div>

    <!-- Search & Filters -->
    <div class="bg-white rounded-xl shadow border border-slate-100 p-4">
      <div class="flex flex-wrap items-end gap-4">
        <!-- Search Input -->
        <div class="flex-1 min-w-[250px]">
          <label class="block text-sm font-medium text-slate-600 mb-1">Search by Email or Name</label>
          <div class="relative">
            <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              v-model="searchQuery"
              @input="onSearchInput"
              type="text"
              placeholder="john@example.com or John Smith..."
              class="w-full pl-10 pr-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            />
          </div>
        </div>
        
        <!-- Role Filter -->
        <div class="w-48">
          <label class="block text-sm font-medium text-slate-600 mb-1">Filter by Role</label>
          <select
            v-model="selectedRole"
            @change="searchUsers"
            class="w-full px-3 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
          >
            <option value="">All Roles</option>
            <option v-for="role in roleOptions" :key="role.value" :value="role.value">
              {{ role.label }}
            </option>
          </select>
        </div>
        
        <!-- Search Button -->
        <button
          @click="searchUsers"
          :disabled="loading"
          class="px-4 py-2.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium disabled:opacity-50"
        >
          <span v-if="loading" class="flex items-center gap-2">
            <svg class="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            Searching...
          </span>
          <span v-else>Search</span>
        </button>
      </div>
      
      <!-- Quick Stats -->
      <div v-if="Object.keys(stats).length > 0" class="mt-4 flex flex-wrap gap-2">
        <span 
          v-for="(count, role) in stats" 
          :key="role"
          :class="['px-3 py-1 rounded-full text-sm font-medium', getRoleColor(role as RoleType)]"
        >
          {{ roleOptions.find(r => r.value === role)?.label || role }}: {{ count }}
        </span>
      </div>
    </div>

    <!-- Results -->
    <div class="bg-white rounded-xl shadow border border-slate-100 overflow-hidden">
      <div v-if="loading && users.length === 0" class="flex items-center justify-center py-12">
        <div class="animate-spin rounded-full h-10 w-10 border-4 border-indigo-200 border-t-indigo-600"></div>
      </div>
      
      <div v-else-if="users.length === 0" class="text-center py-12">
        <div class="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg class="w-8 h-8 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
          </svg>
        </div>
        <h3 class="text-lg font-semibold text-slate-700 mb-2">No Users Found</h3>
        <p class="text-slate-500 text-sm">Try adjusting your search or filters.</p>
      </div>
      
      <table v-else class="w-full">
        <thead class="bg-slate-50 text-left">
          <tr>
            <th class="px-6 py-3 text-xs font-semibold text-slate-500 uppercase">User</th>
            <th class="px-6 py-3 text-xs font-semibold text-slate-500 uppercase">Email</th>
            <th class="px-6 py-3 text-xs font-semibold text-slate-500 uppercase">Role</th>
            <th class="px-6 py-3 text-xs font-semibold text-slate-500 uppercase">Verified</th>
            <th class="px-6 py-3 text-xs font-semibold text-slate-500 uppercase">Actions</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-100">
          <tr 
            v-for="user in users" 
            :key="user.id"
            class="hover:bg-slate-50"
          >
            <td class="px-6 py-4">
              <span class="font-medium text-slate-800">{{ user.name }}</span>
            </td>
            <td class="px-6 py-4">
              <span class="text-slate-600 font-mono text-sm">{{ user.email }}</span>
            </td>
            <td class="px-6 py-4">
              <span :class="['px-2 py-1 rounded text-xs font-medium capitalize', getRoleColor(user.role)]">
                {{ user.role.replace('_', ' ') }}
              </span>
            </td>
            <td class="px-6 py-4">
              <span v-if="user.email_verified" class="text-green-600">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                </svg>
              </span>
              <span v-else class="text-slate-400">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </span>
            </td>
            <td class="px-6 py-4">
              <button
                @click="openEditModal(user)"
                class="px-3 py-1.5 bg-indigo-50 text-indigo-700 rounded-lg hover:bg-indigo-100 transition-colors text-sm font-medium"
              >
                Change Role
              </button>
            </td>
          </tr>
        </tbody>
      </table>
      
      <!-- Result count -->
      <div v-if="users.length > 0" class="px-6 py-3 bg-slate-50 border-t border-slate-100 text-sm text-slate-500">
        Showing {{ users.length }} user{{ users.length === 1 ? '' : 's' }}
      </div>
    </div>

    <!-- Edit Role Modal -->
    <Teleport to="body">
      <Transition
        enter-active-class="transition duration-200 ease-out"
        enter-from-class="opacity-0"
        enter-to-class="opacity-100"
        leave-active-class="transition duration-150 ease-in"
        leave-from-class="opacity-100"
        leave-to-class="opacity-0"
      >
        <div 
          v-if="showEditModal" 
          class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          @click.self="showEditModal = false"
        >
          <div class="bg-white rounded-2xl shadow-xl max-w-md w-full overflow-hidden">
            <!-- Modal Header -->
            <div class="bg-gradient-to-r from-indigo-600 to-violet-600 px-6 py-4">
              <h2 class="text-lg font-bold text-white">Change User Role</h2>
              <p class="text-indigo-200 text-sm">{{ editingUser?.name }}</p>
            </div>
            
            <!-- Modal Content -->
            <div class="p-6">
              <!-- Current Info -->
              <div class="bg-slate-50 rounded-lg p-4 mb-4">
                <div class="text-sm text-slate-500 mb-1">Email</div>
                <div class="font-mono text-slate-700">{{ editingUser?.email }}</div>
              </div>
              
              <!-- Role Selection -->
              <div class="space-y-3">
                <label class="block text-sm font-medium text-slate-700">Select New Role</label>
                <div class="grid grid-cols-1 gap-2">
                  <button
                    v-for="role in roleOptions"
                    :key="role.value"
                    @click="newRole = role.value"
                    :class="[
                      'px-4 py-3 rounded-lg border-2 text-left transition-all',
                      newRole === role.value
                        ? 'border-indigo-500 bg-indigo-50'
                        : 'border-slate-200 hover:border-slate-300'
                    ]"
                  >
                    <div class="flex items-center justify-between">
                      <div>
                        <span class="font-medium text-slate-800">{{ role.label }}</span>
                        <span :class="['ml-2 px-2 py-0.5 rounded text-xs font-medium', role.color]">
                          {{ role.value }}
                        </span>
                      </div>
                      <div v-if="newRole === role.value" class="text-indigo-600">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                        </svg>
                      </div>
                    </div>
                  </button>
                </div>
              </div>
              
              <!-- Error -->
              <div v-if="saveError" class="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                {{ saveError }}
              </div>
              
              <!-- Success -->
              <div v-if="saveSuccess" class="mt-4 p-3 bg-green-50 border border-green-200 rounded-lg text-green-700 text-sm flex items-center gap-2">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                </svg>
                Role updated successfully!
              </div>
            </div>
            
            <!-- Modal Footer -->
            <div class="px-6 py-4 bg-slate-50 border-t border-slate-200 flex justify-end gap-3">
              <button
                @click="showEditModal = false"
                class="px-4 py-2 text-slate-700 hover:text-slate-900 font-medium"
              >
                Cancel
              </button>
              <button
                @click="saveRoleChange"
                :disabled="saving || !newRole || newRole === editingUser?.role"
                class="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <span v-if="saving" class="flex items-center gap-2">
                  <svg class="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Saving...
                </span>
                <span v-else>Save Changes</span>
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

