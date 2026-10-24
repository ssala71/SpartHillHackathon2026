"""
Local test harness for Group 2 — simulates full SMS conversations with NO AWS
and NO real SMS. This is how you develop and demo your own component.

Run offline (keyword fake, no AWS needed):
    USE_FAKE_BEDROCK=1 python3 demo.py

Run against real Bedrock (needs AWS creds + model access in your region):
    python3 demo.py

Each scenario is a list of SMS messages the user sends, in order. The harness
feeds them one at a time, prints the system's reply, and when the request is
complete it runs matching and prints the result.
"""

from __future__ import annotations

from conversation import ConversationStore, handle_message
from matching import load_resources, match_request


# phone, [messages in order], label
CONVERSATIONS = [
    ("+15550001", [
        "I need insulin",
        "near Tully Road, 2 of us, high",
        "deliver",
    ], "Medicine -> asks delivery mode -> review queue (delivery)"),

    ("+15550005", [
        "I need my blood pressure medication near McKee Rd, just me, low",
        "I can collect",
    ], "Medicine, low urgency -> still asks delivery mode -> review queue (collect)"),

    ("+15550002", [
        "we need food for 3 people near McKee Rd, low urgency",
    ], "Food, everything in one text -> match"),

    ("+15550003", [
        "I need water",
        "near Tully Rd",
        "just me, medium",
    ], "Food, gathered over 3 texts -> match"),

    ("+15550004", [
        "I need shelter near Story Rd for 200 people, low",
    ], "Other, group too big for any capacity -> honest no-match"),
]


def run():
    resources = load_resources()
    print(f"Loaded {len(resources)} verified (simulated) resources.\n")

    for phone, messages, label in CONVERSATIONS:
        store = ConversationStore()  # fresh store per scenario for clarity
        print("=" * 72)
        print(f"{label}   [{phone}]")
        result = None
        for msg in messages:
            print(f"  USER: {msg!r}")
            result = handle_message(store, phone, msg)
            if result.reply_text:
                print(f"  SYS : {result.reply_text}")
            if result.complete:
                print("  SYS : (all info gathered -> matching)")
                break

        if result and result.complete:
            print("  --- structured request ---")
            print(_indent(result.request.to_json()))
            match = match_request(result.request, resources)
            print("  --- match result ---")
            print(_indent(match.to_json()))
        print()


def _indent(text: str, pad: str = "    ") -> str:
    return "\n".join(pad + line for line in text.splitlines())


if __name__ == "__main__":
    run()
