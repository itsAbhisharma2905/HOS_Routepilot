import { isTripPlanResult } from "./api";
import type { TripPlanResult } from "../types/trip";

const HISTORY_STORAGE_KEY = "routepilot.trip-history.v1";
const MAX_HISTORY_ITEMS = 6;

export interface StoredTripHistoryItem {
  id: string;
  saved_at: string;
  result: TripPlanResult;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isStoredTripHistoryItem(value: unknown): value is StoredTripHistoryItem {
  return isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.saved_at === "string" &&
    Number.isFinite(Date.parse(value.saved_at)) &&
    isTripPlanResult(value.result);
}

function createHistoryId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `trip-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function loadTripHistory(): StoredTripHistoryItem[] {
  try {
    const raw = localStorage.getItem(HISTORY_STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter(isStoredTripHistoryItem)
      .sort((left, right) => Date.parse(right.saved_at) - Date.parse(left.saved_at));
  } catch {
    return [];
  }
}

export function addTripToHistory(result: TripPlanResult): boolean {
  try {
    const item: StoredTripHistoryItem = {
      id: createHistoryId(),
      saved_at: new Date().toISOString(),
      result,
    };
    const items = [item, ...loadTripHistory()].slice(0, MAX_HISTORY_ITEMS);
    localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(items));
    return true;
  } catch {
    return false;
  }
}

export function deleteTripFromHistory(id: string): boolean {
  try {
    const items = loadTripHistory().filter((item) => item.id !== id);
    localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(items));
    return true;
  } catch {
    return false;
  }
}

export function clearTripHistory(): boolean {
  try {
    localStorage.removeItem(HISTORY_STORAGE_KEY);
    return true;
  } catch {
    return false;
  }
}
