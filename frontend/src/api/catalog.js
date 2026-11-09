import request from '@/utils/request'

export const getCategoryTree = (ops = false) =>
  request.get(ops ? '/ops/categories/' : '/categories/tree/')
export function saveCategory(form, row = null) {
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
