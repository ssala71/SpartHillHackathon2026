// SIMULATED DEMO DATA. Not real resources, people, or phone numbers.
// Field names follow the backend schemas in backend/app/api/schemas.
// Fields marked "proposed" are not in the backend schemas yet.

const minutesAgo = (minutes) => new Date(Date.now() - minutes * 60_000).toISOString()

export const incidents = [
  {
    id: 'inc-1',
    name: 'San José power outage',
    description: 'PG&E reports a widespread outage in south and east San José.',
    affected_area: 'San José 95111, 95122, 95127',
    alert_text:
      'Waypoint: Power is out in your area. Reply with what you need (water, food, charging, shelter) and your nearest cross street. Reply STOP to opt out.', // proposed
    status: 'Active',
    created_at: minutesAgo(180),
    updated_at: minutesAgo(175),
  },
  {
    id: 'inc-2',
    name: 'Coyote Creek flood watch',
    description: 'Draft alert in case water levels rise overnight.',
    affected_area: 'Coyote Creek corridor',
    alert_text: '',
    status: 'Draft',
    created_at: minutesAgo(60),
    updated_at: minutesAgo(60),
  },
]

export const resources = [
  {
    id: 'res-1',
    name: 'Tully Community Center',
    resource_type: 'Community center',
    address: '1580 Tully Rd, San José, CA',
    latitude: 37.3155,
    longitude: -121.8284,
    status: 'Active',
    services: ['water', 'charging', 'shelter'], // proposed
    source: 'City of San José Office of Emergency Management (simulated)', // proposed
    last_verified_at: minutesAgo(25), // proposed
  },
  {
    id: 'res-2',
    name: 'Eastside Food Pantry',
    resource_type: 'Food bank',
    address: '2200 Story Rd, San José, CA',
    latitude: 37.3482,
    longitude: -121.8441,
    status: 'Active',
    services: ['food', 'water', 'baby_supplies'],
    source: 'Second Harvest partner list (simulated)',
    last_verified_at: minutesAgo(70),
  },
  {
    id: 'res-3',
    name: 'Seven Trees Library',
    resource_type: 'Library',
    address: '3590 Cas Dr, San José, CA',
    latitude: 37.2862,
    longitude: -121.8279,
    status: 'TemporarilyClosed',
    services: ['charging'],
    source: 'San José Public Library (simulated)',
    last_verified_at: minutesAgo(40),
  },
  {
    id: 'res-4',
    name: 'Alum Rock Warming Shelter',
    resource_type: 'Shelter',
    address: '3020 Alum Rock Ave, San José, CA',
    latitude: 37.3713,
    longitude: -121.8343,
    status: 'NeedsVerification',
    services: ['shelter', 'food', 'charging'],
    source: 'Volunteer report (simulated)',
    last_verified_at: minutesAgo(600),
  },
]

export const inventoryItems = [
  { id: 'inv-1', resource_id: 'res-1', item_name: 'Bottled water', category: 'Liquids', quantity: 120, unit: 'bottles', status: 'Available', expiration_date: null },
  { id: 'inv-2', resource_id: 'res-2', item_name: 'Bottled water', category: 'Liquids', quantity: 40, unit: 'bottles', status: 'Available', expiration_date: null },
  { id: 'inv-3', resource_id: 'res-2', item_name: 'Canned soup', category: 'CannedGoods', quantity: 85, unit: 'cans', status: 'Available', expiration_date: '2027-08-01' },
  { id: 'inv-4', resource_id: 'res-2', item_name: 'Infant formula', category: 'BabyFood', quantity: 6, unit: 'tins', status: 'Low', expiration_date: '2027-02-15' },
  { id: 'inv-5', resource_id: 'res-4', item_name: 'Ready meals', category: 'ReadyToEat', quantity: 30, unit: 'meals', status: 'Available', expiration_date: '2026-10-30' },
]

export const requests = [
  {
    id: 'req-1',
    incident_id: 'inc-1',
    source_phone: '+14085550142',
    message: "I'm near Tully Road with my grandmother. We need water and somewhere to charge her medical device.",
    location_description: 'Near Tully Rd',
    latitude: 37.3161, // proposed: geocoded location
    longitude: -121.8401,
    needs: ['water', 'charging'],
    people_count: 2,
    urgency: 'Medical',
    status: 'NeedsReview',
    processing_error: null, // proposed
    created_at: minutesAgo(12),
    updated_at: minutesAgo(11),
  },
  {
    id: 'req-2',
    incident_id: 'inc-1',
    source_phone: '+14085550188',
    message: 'Family of 4 near Story and King. Need food, kids are hungry.',
    location_description: 'Story Rd & King Rd',
    latitude: 37.3492,
    longitude: -121.8461,
    needs: ['food'],
    people_count: 4,
    urgency: 'Normal',
    status: 'Matched',
    processing_error: null,
    created_at: minutesAgo(30),
    updated_at: minutesAgo(29),
  },
  {
    id: 'req-3',
    incident_id: 'inc-1',
    source_phone: '+14085550107',
    message: 'need help',
    location_description: null,
    latitude: null,
    longitude: null,
    needs: [],
    people_count: null,
    urgency: 'Normal',
    status: 'NeedsReview',
    processing_error: null,
    created_at: minutesAgo(8),
    updated_at: minutesAgo(8),
  },
  {
    id: 'req-4',
    incident_id: 'inc-1',
    source_phone: '+14085550163',
    message: 'my baby needs formula, we are by alum rock and white rd',
    location_description: 'Alum Rock Ave & White Rd',
    latitude: 37.3721,
    longitude: -121.8189,
    needs: ['baby_supplies'],
    people_count: 3,
    urgency: 'Urgent',
    status: 'NeedsReview',
    processing_error: null,
    created_at: minutesAgo(5),
    updated_at: minutesAgo(5),
  },
  {
    id: 'req-6',
    incident_id: 'inc-1',
    source_phone: '+14085550121',
    message: 'Somos 5 personas cerca de Eastridge. Necesitamos agua y comida por favor.',
    location_description: 'Near Eastridge Mall',
    latitude: 37.3263,
    longitude: -121.8113,
    needs: ['water', 'food'],
    people_count: 5,
    urgency: 'Normal',
    status: 'Matched',
    processing_error: null,
    created_at: minutesAgo(20),
    updated_at: minutesAgo(19),
  },
  {
    id: 'req-5',
    incident_id: 'inc-1',
    source_phone: '+14085550199',
    message: 'Out of water at Senter and Capitol, 3 of us',
    location_description: null,
    latitude: null,
    longitude: null,
    needs: [],
    people_count: null,
    urgency: 'Normal',
    status: 'Processing',
    processing_error: 'Bedrock request timed out after 10s', // shows the retry flow
    created_at: minutesAgo(3),
    updated_at: minutesAgo(3),
  },
]

export const assignments = [
  {
    id: 'asg-1',
    request_id: 'req-2',
    resource_id: 'res-2',
    coordinator_name: null,
    notes: 'Pickup at the pantry; SMS sent with address and hours.',
    status: 'Pending',
    created_at: minutesAgo(28),
    updated_at: minutesAgo(28),
  },
]
