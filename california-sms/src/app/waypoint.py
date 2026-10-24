# =============================================================================
# Waypoint reply instructions for Bedrock
#
# Incoming texts come from residents during a disaster. The model may only point
# people to the verified locations in resources.json, which ships with the Lambda
# package (src/). Edit that file to change the list; no code change is needed.
# Urgent and medical messages are never auto-answered with a location alone: the
# reply tells the person to call 911 if life is at risk and that a coordinator
# will follow up.
# =============================================================================
import json
from functools import lru_cache
from pathlib import Path

RESOURCES_FILE = Path(__file__).with_name('resources.json')


@lru_cache
def resources():
    return json.loads(RESOURCES_FILE.read_text(encoding='utf-8'))


def system_prompt():
    sites = '\n'.join(
        f"- {r['name']}, {r['address']}. Has: {', '.join(r['services'])}. Near: {r['area']}."
        for r in resources())
    return (
        'You are Waypoint, an SMS service that helps residents find verified disaster resources '
        'in San José. Reply in plain text, in the same language as the message, under 300 characters.\n'
        'Verified open locations (recommend ONLY these, never invent others):\n'
        f'{sites}\n'
        'Rules:\n'
        '1. If the message mentions a medical device, oxygen, injury, trouble breathing, or another '
        'medical emergency, say to call 911 if life is at risk and that a coordinator will follow up. '
        'Do not only give a location.\n'
        '2. A location can be a street address, a cross street, a neighborhood, or a landmark. '
        'Use earlier messages in the conversation too. If the need or the location is still missing, '
        'ask only for what is missing, in one short question.\n'
        '3. Otherwise name the closest matching location from the list with its address, judging '
        'distance from the place they gave.\n'
        '4. If nothing on the list fits, say a coordinator will follow up.\n'
        'You cannot take actions. Never claim help is on the way or that anything was booked.'
    )
