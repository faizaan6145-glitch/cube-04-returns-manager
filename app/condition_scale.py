"""Amazon's published condition scale.

We do not invent a scale (README: "Do not invent your own condition scale").
Definitions are quoted from Amazon's own pages, retrieved 2026-09-25:
  - https://sell.amazon.com/blog/amazon-condition-guidelines
  - https://www.amazon.com/gp/help/customer/display.html?nodeId=201889720
    (Marketplace Items Condition Guidelines; returned HTTP 503 on the retrieval date)

"unacceptable" is not a sellable grade. It is Amazon's list of items that may not
be listed at all, and we use it as the grade for units that cannot be resold.
"""

SOURCE_URLS = [
    "https://sell.amazon.com/blog/amazon-condition-guidelines",
    "https://www.amazon.com/gp/help/customer/display.html?nodeId=201889720",
]
RETRIEVED_AT = "2026-09-25"

# Ordered best -> worst.
GRADES: dict[str, dict[str, str]] = {
    "new": {
        "label": "New",
        "definition": "As if you walked into a store and bought it right off the shelf "
        "in its factory packaging.",
    },
    "used_like_new": {
        "label": "Used - Like New",
        "definition": "In perfect working condition and may be missing its original "
        "shrink wrap, but overall it's intact and fully functional.",
    },
    "used_very_good": {
        "label": "Used - Very Good",
        "definition": "Still in good working condition despite the odd blemish; shows "
        "some wear and tear.",
    },
    "used_good": {
        "label": "Used - Good",
        "definition": "May show some wear from consistent use, like minor cosmetic "
        "damage, but it's still functional.",
    },
    "used_acceptable": {
        "label": "Used - Acceptable",
        "definition": "May be pretty worn with damaged packaging; can include worn "
        "corners, scratches, and dents.",
    },
    "unacceptable": {
        "label": "Unacceptable (cannot be listed)",
        "definition": "Dirty, moldy, damaged beyond use, missing essential parts, needs "
        "repair, counterfeit, expired, or otherwise prohibited for sale.",
    },
}

GRADE_KEYS = list(GRADES)


def prompt_text() -> str:
    lines = [f"- {k} ({v['label']}): {v['definition']}" for k, v in GRADES.items()]
    return "\n".join(lines)
