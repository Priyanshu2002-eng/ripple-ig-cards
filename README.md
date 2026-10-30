# ripple-ig-cards

Daily Ripple Feed cards, hosted publicly so Instagram's API can fetch them for @ripple__stories.

- `scripts/ig_cards.py` (current, from 31 Oct 2026): renders the Ripple Feed headless, reads each top story's content
  from the page and lays it out on a fixed 1080×1350 Instagram template with large type. It writes `slide_00.jpg` (cover:
  the cover, built by `scripts/cover.py`) and `slide_01…09.jpg` (stories numbered 1..N with no gaps), plus `manifest.json` and `caption.txt`.
  - Cover (from 31 Oct 2026): big date, Nifty 50 close and 3-month chart (Yahoo Finance ^NSEI daily closes, falling back to
    the Feed's snapshots), a returns row from 1D to 1Y, a market strip and the top 3 stories. Each post's cover carries one background
    letter: posts go up E, L, P, P, I, R, so six posts in a row read RIP / PLE on the profile grid. The letter is picked
    by counting `posted/*.json` from 2026-10-31 on, so a skipped day doesn't break the word.
  - If a story has no "Who moves", its slide shows "On the calendar" (upcoming events) instead, or nothing if there are none.
    Stories are never dropped.
- `scripts/capture.py`: the old version, which cropped the app's cards directly (used up to 30 Oct 2026).
- `cards/YYYY-MM-DD/`: each day's images. `posted/YYYY-MM-DD.json`: record of each day's post.

Daily post: one carousel at about 7:53 am IST (cover + 9 stories, the 10-image Instagram limit). Maintained by a Claude scheduled task.
