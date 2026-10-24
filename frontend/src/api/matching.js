// Mock-only stand-in for Role 2's matching logic, so the demo reacts to
// inventory changes. The real backend should return suggested_match itself.

// Needs that require stock on hand, and the inventory categories that satisfy them.
const STOCKED_NEEDS = {
  water: ['Liquids'],
  food: ['CannedGoods', 'DryGoods', 'ReadyToEat', 'FreshProduce', 'Dairy', 'Refrigerated', 'Frozen'],
  baby_supplies: ['BabyFood'],
}

function distanceKm(a, b) {
  const toRad = (deg) => (deg * Math.PI) / 180
  const dLat = toRad(b.latitude - a.latitude)
  const dLon = toRad(b.longitude - a.longitude)
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(a.latitude)) * Math.cos(toRad(b.latitude)) * Math.sin(dLon / 2) ** 2
  return 6371 * 2 * Math.asin(Math.sqrt(h))
}

function coveredNeeds(resource, needs, inventory) {
  return needs.filter((need) => {
    if (!resource.services?.includes(need)) return false
    const categories = STOCKED_NEEDS[need]
    if (!categories) return true
    return inventory.some(
      (item) => item.resource_id === resource.id && categories.includes(item.category) && item.quantity > 0 && item.status !== 'OutOfStock',
    )
  })
}

export function suggestMatch(request, resources, inventory) {
  const reviewRequired = request.urgency !== 'Normal'

  if (request.processing_error) {
    return { resource_id: null, reason: 'Processing failed before matching.', next_action: 'Retry processing' }
  }
  if (!request.needs?.length || request.latitude == null) {
    return {
      resource_id: null,
      reason: !request.needs?.length ? 'Need is unclear.' : 'Location is missing.',
      next_action: 'Ask follow-up question',
    }
  }

  const candidates = resources
    .filter((resource) => resource.status === 'Active' && resource.latitude != null)
    .map((resource) => ({
      resource,
      covered: coveredNeeds(resource, request.needs, inventory),
      distance: distanceKm(request, resource),
    }))
    .filter((candidate) => candidate.covered.length > 0)
    .sort((a, b) => b.covered.length - a.covered.length || a.distance - b.distance)

  const best = candidates[0]
  if (!best) {
    return {
      resource_id: null,
      reason: 'No active, verified resource has this in stock.',
      next_action: 'Coordinator review',
    }
  }

  const missing = request.needs.filter((need) => !best.covered.includes(need))
  return {
    resource_id: best.resource.id,
    resource_name: best.resource.name,
    address: best.resource.address,
    covered_needs: best.covered,
    distance_km: Math.round(best.distance * 10) / 10,
    source: best.resource.source,
    last_verified_at: best.resource.last_verified_at,
    reason:
      `Closest active resource offering ${best.covered.join(', ')}` + (missing.length ? `. Does not cover: ${missing.join(', ')}.` : '.'),
    next_action: reviewRequired ? 'Coordinator review' : 'Send location by SMS',
  }
}
