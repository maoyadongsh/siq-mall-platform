function dateTime(value) {
  return value ? new Date(value).toLocaleString() : ''
}
function money(value) {
  return value === null || value === undefined ? '—' : `¥${value}`
}
module.exports = { dateTime, money }
