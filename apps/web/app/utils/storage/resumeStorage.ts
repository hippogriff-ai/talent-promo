/**
 * Resume Storage
 * Manages storage of parsed resume data using IndexedDB with localStorage fallback
 */

import { openDB, DBSchema, IDBPDatabase } from 'idb';
import type { ParsedResume } from '@/app/types/resume';

const DB_NAME = 'ResumeParserDB';
const DB_VERSION = 1;
const RESUME_STORE = 'resumes';
const LS_PREFIX = 'resume_';

interface ResumeDB extends DBSchema {
  [RESUME_STORE]: {
    key: string;
    value: ParsedResume;
    indexes: { 'by-date': string };
  };
}

let dbInstance: IDBPDatabase<ResumeDB> | null = null;
let useLocalStorage = false;

/**
 * Initialize the database
 */
async function initDB(): Promise<IDBPDatabase<ResumeDB> | null> {
  if (dbInstance) return dbInstance;

  try {
    dbInstance = await openDB<ResumeDB>(DB_NAME, DB_VERSION, {
      upgrade(db) {
        // Create object store if it doesn't exist
        if (!db.objectStoreNames.contains(RESUME_STORE)) {
          const store = db.createObjectStore(RESUME_STORE, { keyPath: 'id' });
          store.createIndex('by-date', 'metadata.parsedDate');
        }
      },
    });

    return dbInstance;
  } catch (error) {
    console.warn('IndexedDB not available, falling back to localStorage:', error);
    useLocalStorage = true;
    return null;
  }
}

/**
 * Save a parsed resume
 */
export async function saveResume(resume: ParsedResume): Promise<void> {
  if (useLocalStorage) {
    try {
      localStorage.setItem(`${LS_PREFIX}${resume.id}`, JSON.stringify(resume));
      // Also update the index
      const index = getLocalStorageIndex();
      index.push(resume.id);
      localStorage.setItem(`${LS_PREFIX}index`, JSON.stringify(index));
    } catch (error) {
      throw new Error(`Failed to save resume to localStorage: ${error}`);
    }
    return;
  }

  const db = await initDB();
  if (!db) {
    // Fallback to localStorage if IndexedDB fails
    useLocalStorage = true;
    return saveResume(resume);
  }

  try {
    await db.put(RESUME_STORE, resume);
  } catch (error) {
    throw new Error(`Failed to save resume: ${error}`);
  }
}

/**
 * Get a resume by ID
 */
export async function getResume(id: string): Promise<ParsedResume | null> {
  if (useLocalStorage) {
    const data = localStorage.getItem(`${LS_PREFIX}${id}`);
    return data ? JSON.parse(data) : null;
  }

  const db = await initDB();
  if (!db) {
    useLocalStorage = true;
    return getResume(id);
  }

  try {
    const resume = await db.get(RESUME_STORE, id);
    return resume || null;
  } catch (error) {
    console.error('Failed to get resume:', error);
    return null;
  }
}

/**
 * Get all resumes
 */
export async function getAllResumes(): Promise<ParsedResume[]> {
  if (useLocalStorage) {
    const index = getLocalStorageIndex();
    const resumes: ParsedResume[] = [];

    for (const id of index) {
      const data = localStorage.getItem(`${LS_PREFIX}${id}`);
      if (data) {
        resumes.push(JSON.parse(data));
      }
    }

    return resumes;
  }

  const db = await initDB();
  if (!db) {
    useLocalStorage = true;
    return getAllResumes();
  }

  try {
    return await db.getAll(RESUME_STORE);
  } catch (error) {
    console.error('Failed to get all resumes:', error);
    return [];
  }
}

/**
 * Delete a resume by ID
 */
export async function deleteResume(id: string): Promise<void> {
  if (useLocalStorage) {
    localStorage.removeItem(`${LS_PREFIX}${id}`);

    // Update index
    const index = getLocalStorageIndex();
    const newIndex = index.filter(resumeId => resumeId !== id);
    localStorage.setItem(`${LS_PREFIX}index`, JSON.stringify(newIndex));
    return;
  }

  const db = await initDB();
  if (!db) {
    useLocalStorage = true;
    return deleteResume(id);
  }

  try {
    await db.delete(RESUME_STORE, id);
  } catch (error) {
    throw new Error(`Failed to delete resume: ${error}`);
  }
}

/**
 * Update a resume
 */
export async function updateResume(resume: ParsedResume): Promise<void> {
  // Same as save for IndexedDB (put operation)
  return saveResume(resume);
}

/**
 * Check storage quota (for IndexedDB)
 */
export async function checkStorageQuota(): Promise<{ usage: number; quota: number } | null> {
  if (useLocalStorage || !navigator.storage || !navigator.storage.estimate) {
    return null;
  }

  try {
    const estimate = await navigator.storage.estimate();
    return {
      usage: estimate.usage || 0,
      quota: estimate.quota || 0,
    };
  } catch (error) {
    console.error('Failed to check storage quota:', error);
    return null;
  }
}

/**
 * Clear all resumes
 */
export async function clearAllResumes(): Promise<void> {
  if (useLocalStorage) {
    const index = getLocalStorageIndex();
    for (const id of index) {
      localStorage.removeItem(`${LS_PREFIX}${id}`);
    }
    localStorage.removeItem(`${LS_PREFIX}index`);
    return;
  }

  const db = await initDB();
  if (!db) {
    useLocalStorage = true;
    return clearAllResumes();
  }

  try {
    await db.clear(RESUME_STORE);
  } catch (error) {
    throw new Error(`Failed to clear resumes: ${error}`);
  }
}

/**
 * Get localStorage index
 */
function getLocalStorageIndex(): string[] {
  const indexData = localStorage.getItem(`${LS_PREFIX}index`);
  return indexData ? JSON.parse(indexData) : [];
}

/**
 * Export all resumes as JSON
 */
export async function exportResumes(): Promise<string> {
  const resumes = await getAllResumes();
  return JSON.stringify(resumes, null, 2);
}

/**
 * Import resumes from JSON
 */
export async function importResumes(jsonData: string): Promise<number> {
  try {
    const resumes: ParsedResume[] = JSON.parse(jsonData);

    if (!Array.isArray(resumes)) {
      throw new Error('Invalid data format');
    }

    let count = 0;
    for (const resume of resumes) {
      await saveResume(resume);
      count++;
    }

    return count;
  } catch (error) {
    throw new Error(`Failed to import resumes: ${error}`);
  }
}
