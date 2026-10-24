# =============================================================================
# Optional link to the Waypoint backend API (backend/ in this repository)
#
# When WAYPOINT_BACKEND_URL is set, /sms/reply saves each text as a request in
# the backend, lets the backend's Bedrock extraction and resource matcher run,
# and hands the match to the reply writer as facts. The backend owns the request
# record, the verified resource list, and the coordinator review queue, so a text
# shows up for coordinators the same way a dashboard request does.
# Any failure returns None and the caller falls back to resources.json.
# =============================================================================
import json
import os
import re
import time
import urllib.request

POLL_SECONDS = 15
SIM_MARK = re.compile(r'\s*\((?:SIM)[^)]*\)')


def base_url():
    return os.getenv('WAYPOINT_BACKEND_URL', '').rstrip('/')


def _call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(base_url() + path, data=data, method=method,
                                     headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read())['data']


def match(sender, message):
    # Save, process, wait for the background attempt, then read the match.
    created = _call('POST', '/api/requests',
                    {'source_phone': sender, 'message': message[:2000], 'channel': 'SMS'})
    request_id = created['id']
    _call('POST', f'/api/requests/{request_id}/process')
    deadline = time.monotonic() + POLL_SECONDS
    while time.monotonic() < deadline:
        status = _call('GET', f'/api/requests/{request_id}/processing')['status']
        if status != 'Processing':
            break
        time.sleep(0.5)
    else:
        return None
    return _call('GET', f'/api/requests/{request_id}/match')


def facts(result):
    # Turn the matcher's decision into instructions the reply writer must follow.
    # Names and addresses come from the backend's sourced records only.
    if not result:
        return None
    action, place = result.get('action'), result.get('resource')
    where = None
    if place:
        name, address = SIM_MARK.sub('', place['name']), SIM_MARK.sub('', place['address'])
        where = f"{name}, {address} (about {place['distance_km']:.1f} km away)"
    if action == 'direct_to_location' and where:
        return f'Recommend exactly this verified location: {where}.'
    if action == 'follow_up' and result.get('follow_up_message'):
        return ('Ask only for the missing details, in the sender\'s language (English unless they clearly write in another). '
                f"The matcher's question: {result['follow_up_message']}")
    if action == 'coordinator_review':
        nearest = f' You may also name the nearest open site: {where}.' if where else ''
        return ('This request is flagged for a coordinator. Say to call 911 if life is at '
                f'risk and that a coordinator will contact them.{nearest}')
    if action == 'no_match':
        return ('No verified open location has this in stock. Do not name any site. '
                'Say a coordinator will follow up.')
    return None
