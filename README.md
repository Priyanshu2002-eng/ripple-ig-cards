# ripple-ig-cards

Daily Ripple Feed cards, hosted publicly so Instagram's API can fetch them for @ripple__stories.

- `scripts/capture.py` — renders the Ripple Feed headless and crops the top 10 cards through "Who moves" (1080×1350 JPEGs).
- `cards/YYYY-MM-DD/card_NN.jpg` — each day's cards, posted as one 10-slide carousel at ~7:53 am IST.

Maintained by a Claude scheduled task.
