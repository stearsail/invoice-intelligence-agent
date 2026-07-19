export function formatDateTime(isoString) {
  if (!isoString) return ''
  const date = new Date(isoString)
  const day = date.getDate()
  const month = date.getMonth() + 1
  const year = date.getFullYear()
  let hours = date.getHours()
  const minutes = String(date.getMinutes()).padStart(2, '0')
  const ampm = hours >= 12 ? 'PM' : 'AM'
  hours = hours % 12 || 12
  return `${day}/${month}/${year} ${hours}:${minutes} ${ampm}`
}