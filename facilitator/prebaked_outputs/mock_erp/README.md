# Mock ERP: pre-baked output

`tour_output.txt` is `python -m services.mock_erp.tour` run against a
real server (`services/mock_erp/`, started with
`services.mock_erp.launch.start_in_background(port=8000)` on the build
laptop, Windows 11, Python 3.11, 2026-09-22). 29 requests, each with
the reply status it should have: health; the three resources with
filters and pagination; the ONE write (`POST /work-orders`, 201,
`WO-195893`) and three reads proving it is there; the same write again
(409); then every error path - 404 (tag, work order, endpoint), 422
(bad tag, a filter typo, limit out of range, since after until, four
problems in one body, a tag not in the master), 400 (malformed JSON),
415 (wrong content type), 405 (delete a work order, change equipment).

Show it when the ERP cannot run in the room. The data is
deterministic, so a live run prints the same records and the same new
work order number (`WO-195893` is the first write after every start);
only the `started` and `created` timestamps differ.

Refresh it after any change to the seed data or the API: start the
ERP, run the tour, save its stdout here (ASCII, at most 100 columns).
