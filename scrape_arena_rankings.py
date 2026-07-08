"""
Scrapes model rankings from https://arena.ai/leaderboard/text for all categories.
Outputs a JSON file with rankings per model per category.

Usage:
    python scrape_arena_rankings.py [--output rankings.json]
"""

import argparse
import json
import re
import time
import sys
from typing import Optional
import requests

# Single source of truth: arena.ai rankings key → litellm-config.yaml model name.
ARENA_TO_LITELLM: dict[str, str] = {
    "claude-haiku-4-5-20251001": "Claude 4.5 Haiku",
    "claude-opus-4-6": "Claude Opus 4.6",
    "claude-opus-4-8": "Claude Opus 4.8",
    "claude-sonnet-4-5-20250929": "Claude Sonnet 4.5",
    "claude-sonnet-4-6": "Claude Sonnet 4.6",
    "claude-sonnet-5-thinking": "Claude Sonnet 5",
    "deepseek-r1": "DeepSeek R1",
    "deepseek-r1-0528": "DeepSeek R1-0528",
    "deepseek-v3.2": "DeepSeek-V3.2",
    "gemini-2.5-flash": "Gemini 2.5 Flash",
    "gemini-2.5-pro": "Gemini 2.5 Pro",
    "gemini-3-flash": "Gemini 3 Flash",
    "gemini-3-pro": "Gemini 3 Pro",
    "gemini-3.1-flash-lite-preview": "Gemini 3.1 Flash-Lite",
    "gemini-3.1-pro-preview": "Gemini 3.1 Pro",
    "gemini-3.5-flash": "Gemini 3.5 Flash",
    "gpt-5-high": "GPT-5",
    "gpt-5-mini-high": "GPT-5 mini",
    "gpt-5.4": "GPT-5.4",
    "gpt-5.5": "GPT-5.5",
    "o3-2025-04-16": "GPT o3",
    "o4-mini-2025-04-16": "GPT o4-mini",
    "mistral-large-3": "Mistral Large 3",
    "mistral-small-2506": "Mistral Small 4"
}

# All categories available on arena.ai/leaderboard/text
# "overall" maps to the root URL /leaderboard/text
CATEGORIES = [
    "overall",
    "expert",
    "industry-software-and-it-services",
    "industry-writing-and-literature-and-language",
    "industry-life-and-physical-and-social-science",
    "industry-entertainment-and-sports-and-media",
    "industry-business-and-management-and-financial-operations",
    "industry-mathematical",
    "industry-legal-and-government",
    "industry-medicine-and-healthcare",
    "math",
    "instruction-following",
    "multi-turn",
    "creative-writing",
    "coding"
]

BASE_URL = "https://arena.ai/leaderboard/text"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch_category(session: requests.Session, category: str) -> Optional[str]:
    """Fetch HTML for a given category page."""
    if category == "overall":
        url = BASE_URL
    else:
        url = f"{BASE_URL}/{category}"
    try:
        resp = session.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as e:
        print(f"  ERROR fetching {url}: {e}", file=sys.stderr)
        return None


def parse_rankings(html: str) -> dict[str, int]:
    """
    Parse model rankings from the Next.js RSC payload embedded in the HTML.
    Returns {modelDisplayName: rank} for all entries found.
    """
    # The RSC payload double-escapes JSON inside <script> tags.
    # Entry format: {"rank":N,...,"modelDisplayName":"name",...}
    # In raw HTML this appears as: {\"rank\":N,...,\"modelDisplayName\":\"name\",...}
    # We can extract rank+name pairs with a targeted regex.
    rank_name_pairs = re.findall(
        r'\\"rank\\":(\d+)(?:,\\"rankUpper\\":\d+,\\"rankLower\\":\d+)?'
        r'.*?'
        r'\\"modelDisplayName\\":\\"([^\\"]+)\\"',
        html,
    )
    result: dict[str, int] = {}
    for rank_str, name in rank_name_pairs:
        # Only keep first occurrence (entries are ordered, rank is the authoritative value)
        if name not in result:
            result[name] = int(rank_str)
    return result


def scrape_all_categories(delay: float = 0.5) -> dict[str, dict[str, int]]:
    """
    Scrape rankings for all categories.
    Returns {litellm_model_name: {category: rank}}.
    """
    results: dict[str, dict[str, int]] = {litellm: {} for litellm in ARENA_TO_LITELLM.values()}

    session = requests.Session()
    total = len(CATEGORIES)

    for i, category in enumerate(CATEGORIES, 1):
        print(f"[{i}/{total}] Scraping category: {category}")
        html = fetch_category(session, category)
        if html is None:
            print(f"  Skipping {category} due to fetch error.")
            continue

        rankings = parse_rankings(html)
        if not rankings:
            print(f"  WARNING: No rankings parsed for {category}")
            continue

        found = 0
        for arena_key, litellm_name in ARENA_TO_LITELLM.items():
            if arena_key in rankings:
                results[litellm_name][category] = rankings[arena_key]
                found += 1

        print(f"  Found {found}/{len(ARENA_TO_LITELLM)} target models (total models: {len(rankings)})")

        if i < total:
            time.sleep(delay)

    return results


def main():
    parser = argparse.ArgumentParser(description="Scrape arena.ai leaderboard rankings")
    parser.add_argument(
        "--output",
        default="arena_rankings.json",
        help="Output JSON file path (default: arena_rankings.json)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Delay in seconds between requests (default: 0.5)",
    )
    args = parser.parse_args()

    print(f"Scraping {len(CATEGORIES)} categories for {len(ARENA_TO_LITELLM)} models...")
    print()

    rankings = scrape_all_categories(delay=args.delay)

    # Fill in null for categories where a model has no data
    for model in rankings:
        for category in CATEGORIES:
            if category not in rankings[model]:
                rankings[model][category] = None

    # Sort by model name for deterministic output
    sorted_rankings = dict(sorted(rankings.items()))

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(sorted_rankings, f, indent=2, ensure_ascii=False)

    print()
    print(f"Done. Rankings written to: {args.output}")

    # Print summary
    print("\nSummary (models with missing categories):")
    for model, cats in sorted_rankings.items():
        missing = [c for c in CATEGORIES if c not in cats]
        if missing:
            print(f"  {model}: missing {len(missing)} categories: {missing[:5]}{'...' if len(missing) > 5 else ''}")
        else:
            print(f"  {model}: all {len(CATEGORIES)} categories found")


if __name__ == "__main__":
    main()
