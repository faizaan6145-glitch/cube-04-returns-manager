# Findings

RULES.md, Honesty Rule 3: "Contradictions Are Findings... raise the
contradiction... do not silently choose whichever interpretation produces the
desired result." These are the ones found while building this repo.

## In the brief itself

1. **Shared-workflow leftovers vs. the "individual build" instructions.**
   README.md and RULES.md both say Round 2 participants do **not** need a
   `submissions/<username>/` folder or a PR into the organiser repo. But
   `submissions/_TEMPLATE/README.md`, `.github/pull_request_template.md` and
   `.github/scripts/submission-guard.sh` all still enforce that older
   shared-repo workflow (a PR is rejected unless it only touches
   `submissions/<author>/`). **How this build handles it:** followed the
   explicit instruction (fork, build, no PR into the organiser repo) since it
   is stated twice, directly, in both README.md and RULES.md, and ignored the
   template/CI leftovers.

2. **`submissions/_TEMPLATE/README.md` asks for a "cross-pod contract"**,
   while README.md says: "Do not create a separate negotiated cross-pod
   contract for Round 2." **How this build handles it:** used only the
   official evidence contract fields listed in README.md/RULES.md
   (`app/schemas.py`); did not negotiate anything with the other four
   Managers.

## In the sample data (`data/returns_sample.csv`)

3. **Two different SKUs share one ASIN.** `SKU-PROT-1KG` and `SKU-LAMP-LED`
   are both listed with ASIN `B0DUMMY357`. In a real catalogue an ASIN
   uniquely identifies a listing, so this can't both be true. Since
   `data/README.md` explicitly says the values are synthetic and not ground
   truth, this build treats it as bad sample data, not a schema requirement —
   `app/catalog.py` keys lookups by `(org_id, sku)`, not by ASIN, so the
   collision doesn't propagate into the app.

4. **UNIT-0038 is marked `restock` despite its main part (the `tub`) being
   missing** (`parts_missing=tub`). A protein tub missing its tub is not
   restockable by any reading of "complete." This build's own disposition
   rules would send that unit to `refurbish` or `dispose`, not `restock` —
   flagged here rather than matched, since matching it would mean copying an
   inconsistent human decision.

5. **Operator dispositions for functionally identical states are
   inconsistent.** Several `opened_unused` puzzles with all parts present are
   marked `restock` (UNIT-0023, UNIT-0036), but one identical case
   (UNIT-0009) is marked `refurbish`. The sample operators disagreed with
   each other; this build does not treat any single CSV row as ground truth
   for what "should" happen.

6. **Every `identity_match` value in the sample file is `yes`.** There is no
   wrong-item or `no`/`uncertain` identity example in the provided data, so
   identity-mismatch behavior could not be validated against the sample set —
   it had to be exercised with photos of a genuinely different item during
   the evaluation instead (see `EVAL_REPORT.md`).

## Honesty note on `content_hash`

Per RULES.md, Honesty Rule 1: having a `content_hash` field does not mean
records are tamper-evident, immutable, anchored or independently verifiable.
This implementation's `content_hash` is a plain SHA-256 of the record's own
JSON, computed and stored once at creation. It lets a client verify a record
wasn't corrupted in transit or re-derive whether two copies match; it is not
cryptographically anchored anywhere external, and nothing here would detect
someone editing the row directly in `storage/returns.db`.
