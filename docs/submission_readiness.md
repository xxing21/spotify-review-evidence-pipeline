# Submission status

The 100,000-review milestone is complete. The root README is the current entry point; old checkpoint plans and reports are historical measurements.

- 100,000 original IDs classified; 78,288 distinct texts and 21,712 exact-text reuses.
- 5,000 independently sampled outcomes: 4,998 complete predictions, 2 explicit partial refusals.
- US$4.083881615 known API cost for production plus US$0.174263125 unresolved reserves; all prior work and reserves combined US$4.975266680, under US$10.
- 55.69 active minutes / 76.94 minutes first dispatch to last response; warm 15.61 seconds and zero calls.
- Original 100/500/10,000 pilots, recovery recordings, 50 blind human labels and separate adjudications preserved.
- Vercel frontend/API and isolated Neon database live with saved 100k data; signed-out read, source/hash, filter, ranking, memo and unauthorized-write checks pass.
- 40 offline tests pass. Rate-doubling, projected-volume independence and byte-identical offline ranking are checked.

Limitations are disclosed: the supplied full-file checker still expects all 660,622 classifications; only the assignment's 100k option was executed. Scoped checker review_required flags 96 unavailable usage fields across 48 failed requests. Unknown costs remain reserved. The two verifier refusals are not complete predictions. Human accuracy results describe the older ten-review configuration. Public reports do not claim fully reconciled billing, full-corpus coverage or human-verified production accuracy.

The GitHub staging package excludes secrets, full raw CSV, operational SQLite, dependencies and build outputs. It includes original selected data, processed records, gzip full-file accounting, archived raw handoffs, code and reports. The student still submits the public GitHub URL through the course system.
