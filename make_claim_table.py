"""Write claim_codes.csv for the game master's scoring sheet.

Usage: python make_claim_table.py TEAM [TEAM ...]

Each row maps a team's claim code for a level and number of hints used to the
points it is worth. Paste the file into the sheet's `key` tab (see MENTORS.md).
"""

import csv
import sys

from game import LEVELS, MAX_HINTS, claim_code, flag_hash, normalize, points

# Canonical answers first, then accepted aliases. Plain text by design: see MENTORS.md.
ANSWERS = {
    "1-1": ["baggage-gold"],
    "1-2": ["baggage-silver"],
    "1-3": ["20", "twenty"],
    "1-B": ["golden-suitcase"],
    "2-1": ["not_an_object", "not-an-object"],
    "2-2": ["cabin"],
    "2-3": ["five-for-five"],
    "3-1": ["two", "2"],
    "3-2": ["baggage-gold-2024"],
    "3-3": ["rule-writer"],
    "4-1": ["booking_id", "booking-id"],
    "4-2": ["sky-3310"],
    "4-3": ["partner-system-check-3"],
}


def verify_answers():
    problems = []
    for level, answers in ANSWERS.items():
        expected = [flag_hash(answer) for answer in answers]
        if LEVELS[level]["hashes"] != expected:
            problems.append(level)
    if set(ANSWERS) != set(LEVELS):
        problems.append("level list differs from game.LEVELS")
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
        for level, answers in ANSWERS.items():
            max_hints = min(MAX_HINTS, len(LEVELS[level]["hints"]))
            for used in range(max_hints + 1):
                rows.append([team, level, used, claim_code(team, level, answers[0], used), points(level, used)])
    duplicates = duplicate_codes(rows)
    if duplicates:
        sys.exit(f"Claim codes collide ({', '.join(duplicates)}); rename one of the teams and run again.")
    with open("claim_codes.csv", "w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        writer.writerow(["team", "level", "hints_used", "claim_code", "points"])
        writer.writerows(rows)
    print(f"wrote claim_codes.csv: {len(rows)} rows for {len(teams)} team(s)")


if __name__ == "__main__":
    main(sys.argv[1:])
