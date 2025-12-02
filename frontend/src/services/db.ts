import { openDB } from 'idb';
import type { DBSchema, IDBPDatabase } from 'idb';
import type { JudgeScore } from '../models/types';

interface FeisDB extends DBSchema {
  scores: {
    key: string;
    value: JudgeScore;
    indexes: { 'by-round': string; 'synced': string };
  };
}

const DB_NAME = 'open-feis-db';
const DB_VERSION = 1;

export class LocalStorageService {
  private dbPromise: Promise<IDBPDatabase<FeisDB>>;

  constructor() {
    this.dbPromise = openDB<FeisDB>(DB_NAME, DB_VERSION, {
      upgrade(db) {
        const store = db.createObjectStore('scores', { keyPath: 'id' });
        store.createIndex('by-round', 'round_id');
        store.createIndex('synced', 'synced');
      },
    });
  }

  async saveScore(score: JudgeScore): Promise<void> {
    const db = await this.dbPromise;
    await db.put('scores', { ...score, synced: false });
  }

  async getScoresForRound(roundId: string): Promise<JudgeScore[]> {
    const db = await this.dbPromise;
    return db.getAllFromIndex('scores', 'by-round', roundId);
  }

  async getUnsyncedScores(): Promise<JudgeScore[]> {
    const db = await this.dbPromise;
    // Note: Boolean indexing in IDB can be tricky, iterating is safe for small datasets
    const all = await db.getAll('scores');
    return all.filter(s => s.synced === false);
  }

  async markSynced(ids: string[]): Promise<void> {
    const db = await this.dbPromise;
    const tx = db.transaction('scores', 'readwrite');
    await Promise.all([
      ...ids.map(async (id) => {
        const score = await tx.store.get(id);
        if (score) {
          score.synced = true;
          await tx.store.put(score);
        }
      }),
      tx.done,
    ]);
  }
}

export const dbService = new LocalStorageService();

