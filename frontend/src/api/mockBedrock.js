// Mock-only stand-in for the Bedrock extraction step and the SMS reply rules.
// The real pipeline returns the same shape from the backend; this lets the demo
// run end to end with no AWS calls. Keyword rules here are deliberately simple.

export const MODEL_ID = 'Bedrock model (simulated)'

const NEED_PATTERNS = {
  water: /\bwater\b|\bagua\b|thirst/i,
  food: /\bfood\b|\bhungry\b|\beat\b|\bmeal|\bcomida\b|groceries/i,
  charging: /charg|\bpower\b|battery|\bcargar\b|oxygen|concentrator|cpap|medical device/i,
  shelter: /shelter|place to (stay|sleep)|\brefugio\b|nowhere to (go|stay)|cold/i,
  baby_supplies: /formula|diaper|baby|pañal|bebé/i,
}

const MEDICAL = /medical device|oxygen|concentrator|insulin|dialysis|cpap|can'?t breathe|chest pain|medicine|medicina|oxígeno/i
const URGENT = /\bbaby\b|bebé|infant|urgent|emergency|elderly|grandmother|grandfather|abuela|abuelo|disabled|wheelchair/i
const SPANISH = /\b(necesit|agua|comida|estamos|tenemos|ayuda|cerca|somos|mi |por favor)/i

// Tiny demo geocoder: cross streets the demo messages mention.
const PLACES = [
  { pattern: /tully/i, label: 'Near Tully Rd', latitude: 37.3161, longitude: -121.8401 },
  { pattern: /story.*king|king.*story/i, label: 'Story Rd & King Rd', latitude: 37.3492, longitude: -121.8461 },
  { pattern: /alum rock.*white|white.*alum rock/i, label: 'Alum Rock Ave & White Rd', latitude: 37.3721, longitude: -121.8189 },
  { pattern: /senter.*capitol|capitol.*senter/i, label: 'Senter Rd & Capitol Expy', latitude: 37.2969, longitude: -121.8252 },
  { pattern: /mclaughlin|mc laughlin/i, label: 'Near McLaughlin Ave', latitude: 37.3256, longitude: -121.8558 },
  { pattern: /eastridge/i, label: 'Near Eastridge Mall', latitude: 37.3263, longitude: -121.8113 },
  { pattern: /alum rock/i, label: 'Near Alum Rock Ave', latitude: 37.3713, longitude: -121.8343 },
]

const NUMBER_WORDS = { two: 2, three: 3, four: 4, five: 5, six: 6, dos: 2, tres: 3, cuatro: 4, cinco: 5 }

function peopleCount(text) {
  const match = text.match(/(\d+|two|three|four|five|six|dos|tres|cuatro|cinco)\s*(of us|people|kids|personas|adults)/i) ?? text.match(/family of (\d+|\w+)/i)
  if (match) return Number(match[1]) || NUMBER_WORDS[match[1].toLowerCase()] || null
  if (/with my (grandmother|grandfather|mom|dad|wife|husband|son|daughter)|con mi/i.test(text)) return 2
  return null
}

export function extract(message) {
  const started = performance.now()
  const needs = Object.entries(NEED_PATTERNS)
    .filter(([, pattern]) => pattern.test(message))
    .map(([need]) => need)
  const place = PLACES.find((p) => p.pattern.test(message))
  const indicators = [...new Set([...(message.match(new RegExp(MEDICAL, 'gi')) ?? []), ...(message.match(new RegExp(URGENT, 'gi')) ?? [])])].map((s) =>
    s.toLowerCase(),
  )
  const urgency = MEDICAL.test(message) ? 'Medical' : URGENT.test(message) ? 'Urgent' : 'Normal'
  const missing = [...(needs.length ? [] : ['needs']), ...(place ? [] : ['location'])]

  return {
    fields: {
      needs,
      location_description: place?.label ?? null,
      latitude: place?.latitude ?? null,
      longitude: place?.longitude ?? null,
      people_count: peopleCount(message),
      urgency,
    },
    extraction: {
      model_id: MODEL_ID,
      language: SPANISH.test(message) ? 'es' : 'en',
      urgency_indicators: indicators,
      missing_fields: missing,
      latency_ms: Math.round(700 + Math.random() * 500 + (performance.now() - started)),
      validated: true,
    },
  }
}

const NEED_WORDS = {
  en: { water: 'water', food: 'food', charging: 'charging', shelter: 'shelter', baby_supplies: 'baby supplies' },
  es: { water: 'agua', food: 'comida', charging: 'carga', shelter: 'refugio', baby_supplies: 'artículos para bebé' },
}

// The SMS the system sends back. Rules, not the model, decide which one.
export function composeReply(request, match, language = 'en') {
  const es = language === 'es'
  const words = (needs) => needs.map((n) => NEED_WORDS[es ? 'es' : 'en'][n] ?? n).join(', ')

  if (match.next_action === 'Ask follow-up question') {
    return es
      ? '¿Qué necesita y cuál es la intersección más cercana? Ej: "agua, Tully y McLaughlin"'
      : 'What do you need, and what is your nearest cross street? Example: "water, Tully and McLaughlin"'
  }
  // Urgent and medical requests still get the nearest verified location, but a
  // coordinator always follows up and the reply leads with 911.
  if (request.urgency !== 'Normal') {
    const place = match.resource_id ? `${match.resource_name}, ${match.address} (~${match.distance_km} km)` : null
    if (es) {
      return `Si es una emergencia que pone en riesgo la vida, llame al 911. Un coordinador lo contactará pronto.${place ? ` Lugar verificado más cercano: ${place}.` : ''}`
    }
    return `If this is life-threatening, call 911. A coordinator will contact you shortly.${place ? ` Nearest verified location: ${place}.` : ''}`
  }
  if (!match.resource_id) {
    return es
      ? `No tenemos un lugar verificado con ${words(request.needs)} en este momento. Un coordinador fue notificado.`
      : `We don't have a verified location with ${words(request.needs)} right now. A coordinator has been notified and will follow up.`
  }
  return locationReply(match, request.needs, language)
}

export function locationReply(match, needs, language = 'en') {
  const es = language === 'es'
  const words = needs.map((n) => NEED_WORDS[es ? 'es' : 'en'][n] ?? n).join(', ')
  return es
    ? `${match.resource_name}, ${match.address} (~${match.distance_km} km). Tiene: ${words}. Verificado recientemente. Responda AYUDA si no le sirve.`
    : `${match.resource_name}, ${match.address} (~${match.distance_km} km). Has: ${words}. Recently verified. Reply HELP if this doesn't work for you.`
}
