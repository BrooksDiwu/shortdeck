import type { TableResponse, TableRulesSchema } from '@/types'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options?.headers },
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  getTables: () => apiFetch<TableResponse[]>('/api/v1/tables'),

  createTable: (token: string, rules: TableRulesSchema, name?: string) =>
    apiFetch<TableResponse>('/api/v1/tables', {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify({ rules, name: name ?? '' }),
    }),

  joinTable: (token: string, tableId: string) =>
    apiFetch<{ message: string; seat: number }>(`/api/v1/tables/${tableId}/join`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    }),

  rebuy: (token: string, tableId: string, amount: number) =>
    apiFetch<{ message: string }>(`/api/v1/tables/${tableId}/rebuy`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify({ amount }),
    }),
}
