export function timeAgo(iso) {
  if (!iso) return 'Unknown'
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.round(minutes / 60)
  return hours < 24 ? `${hours} hr ago` : `${Math.round(hours / 24)} d ago`
}

// Only show the last four digits of a phone number on screen.
export const maskPhone = (phone) => (phone ? `•••• ${phone.slice(-4)}` : 'Unknown')

export const NEED_LABELS = {
  water: 'Water',
  food: 'Food',
  charging: 'Charging',
  shelter: 'Shelter',
  medical: 'Medical',
  baby_supplies: 'Baby supplies',
}

export const needLabel = (need) => NEED_LABELS[need] ?? need

export const splitWords = (value) => value?.replace(/([a-z])([A-Z])/g, '$1 $2') ?? ''
