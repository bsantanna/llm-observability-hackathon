"""Write claim_codes.csv for the game master's scoring sheet.

Usage: python make_claim_table.py TEAM [TEAM ...]

Each row maps a team's claim code for a clue and number of hints used to the
points it is worth. Paste the file into the sheet's `key` tab (see MENTORS.md).
"""

import csv
import sys

from game import CLUES, MAX_HINTS, claim_code, flag_hash, normalize, points

# Canonical answers first, then accepted aliases. Plain text by design: see MENTORS.md.
ANSWERS = {
    "1-0": ["activity-1-retrieval"],
    "1-1": ["lf-rooster-sk205"],
    "1-2": ["lf-fishing-hat-sk101"],
    "1-3": ["16", "sixteen"],
    "1-B": ["golden-fishhook"],
    "2-1": ["not_an_object", "not-an-object"],
    "2-2": ["cabin"],
    "2-3": ["three-for-three"],
    "3-1": ["head-of-poultry-relations"],
    "3-2": ["pets-notice-old"],
    "3-3": ["quiet-flight"],
    "4-1": ["booking_id", "booking-id"],
    "4-2": ["sky-3310"],
    "4-3": ["piano-mover-check-3"],
    "vault": ["skye-is-back-online"],
}


def verify_answers():
    problems = []
    for clue, answers in ANSWERS.items():
        expected = [flag_hash(answer) for answer in answers]
        if CLUES[clue]["hashes"] != expected:
            problems.append(clue)
    if set(ANSWERS) != set(CLUES):
        problems.append("clue list differs from game.CLUES")
    return problems


def duplicate_codes(rows):
    seen, duplicates = set(), set()
    for row in rows:
        code = row[3]
        (duplicates if code in seen else seen).add(code)
    return sorted(duplicates)


def main(teams):
    problems = verify_answers()
    if problems:
        sys.exit(f"Answers do not match game.py for: {', '.join(problems)}")
    if not teams:
        sys.exit(__doc__)
    rows = []
    for team in dict.fromkeys(normalize(team) for team in teams):
        for clue, answers in ANSWERS.items():
            max_hints = min(MAX_HINTS, len(CLUES[clue]["hints"]))
            for used in range(max_hints + 1):
                rows.append([team, clue, used, claim_code(team, clue, answers[0], used), points(clue, used)])
    duplicates = duplicate_codes(rows)
    if duplicates:
        sys.exit(f"Claim codes collide ({', '.join(duplicates)}); rename one of the teams and run again.")
    with open("claim_codes.csv", "w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        writer.writerow(["team", "clue", "hints_used", "claim_code", "points"])
        writer.writerows(rows)
    print(f"wrote claim_codes.csv: {len(rows)} rows for {len(teams)} team(s)")


if __name__ == "__main__":
    main(sys.argv[1:])
