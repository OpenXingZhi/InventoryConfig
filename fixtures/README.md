# Fixtures

These documents exercise the schema and signer. They are not runtime
configuration. Inventory must never fetch a path under `fixtures/` or
`examples/`.

- `schema/valid/` (2) — documents the stdlib validator and `check-jsonschema` accept
- `schema/invalid/` (16) — documents both validators must reject

Invalid expiry cases: `bad-expire.yml` is not four-digit `YYYY-MM-DD`;
`impossible-expire.yml` matches that pattern but is not a real calendar
date (`format: date`).

Required-object cases: `missing-reader.yml` and `missing-display.yml`
omit a mandatory deployment object. Required-field cases:
`missing-reader-rfid-type.yml` and `missing-display-sort.yml` omit one
modeled field inside an otherwise complete object.
