/**
 * Job Posting Storage
 * Manages storage of job posting data using IndexedDB with localStorage fallback
 */

import { openDB, DBSchema, IDBPDatabase } from 'idb';
import type { JobPosting } from '@/app/types/jobPosting';

const DB_NAME = 'JobPostingDB';
const DB_VERSION = 1;
const JOB_STORE = 'jobs';
const LS_PREFIX = 'job_';

interface JobDB extends DBSchema {
  [JOB_STORE]: {
    key: string;
    value: JobPosting;
    indexes: {
      'by-date': string;
      'by-platform': string;
      'by-company': string;
    };
  };
}

let dbInstance: IDBPDatabase<JobDB> | null = null;
let useLocalStorage = false;

/**
 * Initialize the database
 */
async function initDB(): Promise<IDBPDatabase<JobDB> | null> {
  if (dbInstance) return dbInstance;

  try {
    dbInstance = await openDB<JobDB>(DB_NAME, DB_VERSION, {
      upgrade(db) {
        if (!db.objectStoreNames.contains(JOB_STORE)) {
          const store = db.createObjectStore(JOB_STORE, { keyPath: 'id' });
          store.createIndex('by-date', 'metadata.retrievedDate');
          store.createIndex('by-platform', 'platform');
          store.createIndex('by-company', 'company.name');
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
 * Save a job posting
 */
export async function saveJob(job: JobPosting): Promise<void> {
  if (useLocalStorage) {
    try {
      localStorage.setItem(`${LS_PREFIX}${job.id}`, JSON.stringify(job));
      const index = getLocalStorageIndex();
      if (!index.includes(job.id)) {
        index.push(job.id);
        localStorage.setItem(`${LS_PREFIX}index`, JSON.stringify(index));
      }
    } catch (error) {
      throw new Error(`Failed to save job to localStorage: ${error}`);
    }
    return;
  }

  const db = await initDB();
  if (!db) {
    useLocalStorage = true;
    return saveJob(job);
  }

  try {
    await db.put(JOB_STORE, job);
  } catch (error) {
    throw new Error(`Failed to save job posting: ${error}`);
  }
}

/**
 * Get a job posting by ID
 */
export async function getJob(id: string): Promise<JobPosting | null> {
  if (useLocalStorage) {
    const data = localStorage.getItem(`${LS_PREFIX}${id}`);
    return data ? JSON.parse(data) : null;
  }

  const db = await initDB();
  if (!db) {
    useLocalStorage = true;
    return getJob(id);
  }

  try {
    const job = await db.get(JOB_STORE, id);
    return job || null;
  } catch (error) {
    console.error('Failed to get job posting:', error);
    return null;
  }
}

/**
 * Get job posting by source URL (for caching)
 */
export async function getJobByUrl(url: string): Promise<JobPosting | null> {
  if (useLocalStorage) {
    const index = getLocalStorageIndex();
    for (const id of index) {
      const data = localStorage.getItem(`${LS_PREFIX}${id}`);
      if (data) {
        const job: JobPosting = JSON.parse(data);
        if (job.sourceUrl === url) {
          return job;
        }
      }
    }
    return null;
  }

  const db = await initDB();
  if (!db) {
    useLocalStorage = true;
    return getJobByUrl(url);
  }

  try {
    const allJobs = await db.getAll(JOB_STORE);
    return allJobs.find(job => job.sourceUrl === url) || null;
  } catch (error) {
    console.error('Failed to get job by URL:', error);
    return null;
  }
}

/**
 * Get all job postings
 */
export async function getAllJobs(): Promise<JobPosting[]> {
  if (useLocalStorage) {
    const index = getLocalStorageIndex();
    const jobs: JobPosting[] = [];

    for (const id of index) {
      const data = localStorage.getItem(`${LS_PREFIX}${id}`);
      if (data) {
        jobs.push(JSON.parse(data));
      }
    }

    return jobs;
  }

  const db = await initDB();
  if (!db) {
    useLocalStorage = true;
    return getAllJobs();
  }

  try {
    return await db.getAll(JOB_STORE);
  } catch (error) {
    console.error('Failed to get all jobs:', error);
    return [];
  }
}

/**
 * Delete a job posting by ID
 */
export async function deleteJob(id: string): Promise<void> {
  if (useLocalStorage) {
    localStorage.removeItem(`${LS_PREFIX}${id}`);

    const index = getLocalStorageIndex();
    const newIndex = index.filter(jobId => jobId !== id);
    localStorage.setItem(`${LS_PREFIX}index`, JSON.stringify(newIndex));
    return;
  }

  const db = await initDB();
  if (!db) {
    useLocalStorage = true;
    return deleteJob(id);
  }

  try {
    await db.delete(JOB_STORE, id);
  } catch (error) {
    throw new Error(`Failed to delete job posting: ${error}`);
  }
}

/**
 * Clear all job postings
 */
export async function clearAllJobs(): Promise<void> {
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
    return clearAllJobs();
  }

  try {
    await db.clear(JOB_STORE);
  } catch (error) {
    throw new Error(`Failed to clear job postings: ${error}`);
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
 * Check if a job is cached and recent (within 24 hours)
 */
export async function isCached(url: string, maxAgeHours: number = 24): Promise<boolean> {
  const job = await getJobByUrl(url);
  if (!job) return false;

  const retrievedDate = new Date(job.metadata.retrievedDate);
  const ageHours = (Date.now() - retrievedDate.getTime()) / (1000 * 60 * 60);

  return ageHours < maxAgeHours;
}
