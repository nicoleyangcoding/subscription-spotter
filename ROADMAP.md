# Roadmap

Small, focused releases. Suggestions are welcome in [issues](https://github.com/nicoleyangcoding/subscription-spotter/issues).

## 0.2
- [ ] `--html report.html`: a single-file report you can open in a browser
- [ ] `--since 2026-01-01` to limit the date range
- [ ] Recurring income section (paychecks, refunds) behind `--include-income`

## 0.3
- [ ] Export renewal dates to an `.ics` calendar, to get reminded before yearly renewals
- [ ] Compare two runs and show new or cancelled subscriptions
- [ ] Support OFX/QFX files in addition to CSV

## Later
- [ ] Optional rules file for renaming merchants (`"AMZN PRIME" -> "Prime membership"`)
- [ ] Publish to PyPI so `pipx install subscription-spotter` works

## Not planned
- Connecting to banks or uploading data anywhere. `subspot` stays fully offline.
