/**
 * Cloud Sync Service
 * 
 * Handles batch synchronization of local data to the cloud server.
 * Used after running a feis in local mode to upload results.
 */

import { ref, type Ref } from 'vue';
import { dbService } from './db';
import type { JudgeScore } from '../models/types';

// ============= Types =============

export interface SyncProgress {
  phase: 'idle' | 'preparing' | 'uploading' | 'verifying' | 'complete' | 'error';
  current: number;
  total: number;
  message: string;
}

export interface SyncResult {
  success: boolean;
  uploaded: number;
  failed: number;
  conflicts: SyncConflict[];
  message: string;
}

export interface SyncConflict {
  score_id: string;
  entry_id: string;
  competition_id: string;
  local_value: number;
  server_value: number;
  local_timestamp: string;
  server_timestamp: string;
}

export interface PendingSyncData {
  scores: JudgeScore[];
  totalCount: number;
  competitionIds: string[];
}

// ============= Sync Service =============

class CloudSyncService {
  // Reactive state for UI binding
  public progress: Ref<SyncProgress> = ref({
    phase: 'idle',
    current: 0,
    total: 0,
    message: '',
  });

  public isSyncing: Ref<boolean> = ref(false);
  public lastSyncResult: Ref<SyncResult | null> = ref(null);

  private authToken: string | null = null;

  /**
   * Set the authentication token for API requests.
   */
  setAuthToken(token: string | null): void {
    this.authToken = token;
  }

  /**
   * Get all pending (unsynced) data from IndexedDB.
   */
  async getPendingData(): Promise<PendingSyncData> {
    const scores = await dbService.getUnsyncedScores();
    
    // Get unique competition IDs
    const competitionIds = [...new Set(scores.map(s => s.round_id))];
    
    return {
      scores,
      totalCount: scores.length,
      competitionIds,
    };
  }

  /**
   * Check if there's any data that needs to be synced.
   */
  async hasPendingData(): Promise<boolean> {
    const data = await this.getPendingData();
    return data.totalCount > 0;
  }

  /**
   * Perform a full sync of all pending data to the cloud.
   * 
   * @param serverUrl - The cloud server URL (e.g., https://openfeis.org)
   * @returns SyncResult with details of what was synced
   */
  async syncToCloud(serverUrl: string): Promise<SyncResult> {
    if (this.isSyncing.value) {
      return {
        success: false,
        uploaded: 0,
        failed: 0,
        conflicts: [],
        message: 'Sync already in progress',
      };
    }

    this.isSyncing.value = true;
    this.lastSyncResult.value = null;

    try {
      // Phase 1: Prepare data
      this.updateProgress('preparing', 0, 1, 'Gathering local data...');
      
      const pendingData = await this.getPendingData();
      
      if (pendingData.totalCount === 0) {
        this.updateProgress('complete', 0, 0, 'No data to sync');
        return {
          success: true,
          uploaded: 0,
          failed: 0,
          conflicts: [],
          message: 'No pending data to sync. Everything is up to date!',
        };
      }

      // Phase 2: Upload scores in batches
      this.updateProgress('uploading', 0, pendingData.totalCount, `Uploading ${pendingData.totalCount} scores...`);
      
      const batchSize = 50;
      const batches = this.chunkArray(pendingData.scores, batchSize);
      
      let uploaded = 0;
      let failed = 0;
      const conflicts: SyncConflict[] = [];
      const successfulIds: string[] = [];

      for (let i = 0; i < batches.length; i++) {
        const batch = batches[i];
        
        try {
          const result = await this.uploadBatch(serverUrl, batch);
          
          uploaded += result.uploaded;
          failed += result.failed;
          conflicts.push(...result.conflicts);
          successfulIds.push(...result.successfulIds);
          
          this.updateProgress(
            'uploading',
            uploaded + failed,
            pendingData.totalCount,
            `Uploaded ${uploaded} of ${pendingData.totalCount} scores...`
          );
        } catch (error) {
          console.error(`Batch ${i + 1} failed:`, error);
          failed += batch.length;
        }
      }

      // Phase 3: Mark successful uploads as synced
      this.updateProgress('verifying', 0, 1, 'Marking scores as synced...');
      
      if (successfulIds.length > 0) {
        await dbService.markSynced(successfulIds);
      }

      // Phase 4: Complete
      const result: SyncResult = {
        success: failed === 0 && conflicts.length === 0,
        uploaded,
        failed,
        conflicts,
        message: this.buildResultMessage(uploaded, failed, conflicts.length),
      };

      this.updateProgress('complete', pendingData.totalCount, pendingData.totalCount, result.message);
      this.lastSyncResult.value = result;
      
      return result;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
      
      this.updateProgress('error', 0, 0, `Sync failed: ${errorMessage}`);
      
      const result: SyncResult = {
        success: false,
        uploaded: 0,
        failed: 0,
        conflicts: [],
        message: `Sync failed: ${errorMessage}`,
      };
      
      this.lastSyncResult.value = result;
      return result;
    } finally {
      this.isSyncing.value = false;
    }
  }

  /**
   * Upload a batch of scores to the cloud server.
   */
  private async uploadBatch(
    serverUrl: string,
    scores: JudgeScore[]
  ): Promise<{
    uploaded: number;
    failed: number;
    conflicts: SyncConflict[];
    successfulIds: string[];
  }> {
    const url = `${serverUrl}/api/v1/sync/scores`;
    
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };
    
    if (this.authToken) {
      headers['Authorization'] = `Bearer ${this.authToken}`;
    }

    const response = await fetch(url, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        scores: scores.map(s => ({
          id: s.id,
          judge_id: s.judge_id,
          competitor_id: s.competitor_id,
          round_id: s.round_id,
          value: s.value,
          timestamp: s.timestamp,
        })),
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Server returned ${response.status}: ${errorText}`);
    }

    const result = await response.json();
    
    return {
      uploaded: result.uploaded ?? scores.length,
      failed: result.failed ?? 0,
      conflicts: result.conflicts ?? [],
      successfulIds: result.successful_ids ?? scores.map(s => s.id),
    };
  }

  /**
   * Resolve a sync conflict by choosing local or server version.
   */
  async resolveConflict(
    serverUrl: string,
    conflict: SyncConflict,
    resolution: 'use_local' | 'use_server'
  ): Promise<boolean> {
    const url = `${serverUrl}/api/v1/sync/resolve`;
    
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };
    
    if (this.authToken) {
      headers['Authorization'] = `Bearer ${this.authToken}`;
    }

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          score_id: conflict.score_id,
          resolution,
          local_value: conflict.local_value,
          local_timestamp: conflict.local_timestamp,
        }),
      });

      return response.ok;
    } catch (error) {
      console.error('Failed to resolve conflict:', error);
      return false;
    }
  }

  /**
   * Reset sync state.
   */
  reset(): void {
    this.progress.value = {
      phase: 'idle',
      current: 0,
      total: 0,
      message: '',
    };
    this.lastSyncResult.value = null;
  }

  // ============= Private Helpers =============

  private updateProgress(phase: SyncProgress['phase'], current: number, total: number, message: string): void {
    this.progress.value = { phase, current, total, message };
  }

  private chunkArray<T>(array: T[], size: number): T[][] {
    const chunks: T[][] = [];
    for (let i = 0; i < array.length; i += size) {
      chunks.push(array.slice(i, i + size));
    }
    return chunks;
  }

  private buildResultMessage(uploaded: number, failed: number, conflicts: number): string {
    const parts: string[] = [];
    
    if (uploaded > 0) {
      parts.push(`${uploaded} score${uploaded !== 1 ? 's' : ''} uploaded`);
    }
    
    if (failed > 0) {
      parts.push(`${failed} failed`);
    }
    
    if (conflicts > 0) {
      parts.push(`${conflicts} conflict${conflicts !== 1 ? 's' : ''} need resolution`);
    }
    
    if (parts.length === 0) {
      return 'Sync complete!';
    }
    
    return parts.join(', ') + '.';
  }
}

// Export singleton instance
export const syncService = new CloudSyncService();

