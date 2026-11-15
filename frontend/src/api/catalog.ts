import type { Category } from '@/types/models'
import request from '@/utils/request'

export interface CategoryForm {
  name: string
  parent_id?: string | null
  sort_order: number
  enabled: boolean
}

export const getCategoryTree = (ops = false): Promise<Category[]> =>
  request.get(ops ? '/ops/categories/' : '/categories/tree/')

export function saveCategory(form: CategoryForm, row: Category | null = null): Promise<Category> {
  const data = {
    name: form.name,
    parent_id: form.parent_id || null,
    sort_order: form.sort_order,
    enabled: form.enabled,
  }
  return row
    ? request.patch(`/ops/categories/${row.id}/`, { ...data, expected_version: row.version })
    : request.post('/ops/categories/', data)
}
