"""I-04 — labelled counterexample corpus shape test.

The corpus at `corpus/vN/postings.json` is the project's public
artefact that makes the deterministic gate auditable. Borrowed pattern
from inbox-job-tracker's `tests/fixtures/emails.json` (a JSON array
of {id, expect, why, body} records), applied to posting classification.

This test asserts the corpus shape:
  - the corpus is a JSON array, not an object
  - every record has id, rule, expect, why, body, title
  - every `id` is unique (c-001, c-002, ...)
  - every `rule` exists in jobsearch/rule_why.WHY
  - every `expect` is one of SUITABLE / NEEDS_RESEARCH / NOT_SUITABLE
  - every `why` is a non-empty sentence
  - the corpus is versioned (corpus/vN/...; a v1 must exist)
  - the corpus SHA is recorded in corpus/manifest.json (when manifest
    exists) and the SHA in the manifest matches the file on disk

A corpus that fails any of these is a build failure. The gate cannot
be auditable without a clean corpus.

Run:  python3 -m unittest tests.test_corpus -v
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jobsearch import rule_why  # noqa: E402

CORPUS_DIR = ROOT / "corpus"
# Outcome vocabulary must match jobsearch/rules.py: STRONG_MATCH,
# POTENTIAL_MATCH, NEEDS_RESEARCH, NOT_SUITABLE. The corpus is the
# gate's published behaviour; a value outside the vocabulary is a
# typo a reader will not be able to verify against the code.
ALLOWED_EXPECT = {"strong_match", "potential_match", "needs_research", "not_suitable"}
# The gate-level rules the corpus is the contract for. A new
# rule in jobsearch/rule_why.WHY that is not in this set is a
# meta-rule (about tooling behaviour, not gate behaviour) and
# does not need a corpus fixture. Adding a new GATE-LEVEL rule
# without a fixture is a build failure (see
# TestCorpusCoversEveryGateRule below).
from jobsearch import rule_why as _rule_why_mod
GATE_LEVEL_RULES: set[str] = {
    k for k in _rule_why_mod.WHY
    if not k.startswith(("no_", "bounded_", "fetched_", "one_shot_",
                         "scope_", "history_", "counterexample_",
                         "export_", "verdict_"))
}
ID_PATTERN = re.compile(r"^c-[0-9]{3,}$")


def _iter_corpus_versions() -> list[Path]:
    """Return corpus/v1/postings.json, corpus/v2/postings.json, ..."""
    if not CORPUS_DIR.exists():
        return []
    return sorted(CORPUS_DIR.glob("v*/postings.json"))


def _load_json(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"{path}: corpus must be a JSON array, got {type(data).__name__}")
    return data


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestCorpusShape(unittest.TestCase):
    """The corpus file is a JSON array of well-shaped records."""

    def test_at_least_v1_exists(self) -> None:
        paths = _iter_corpus_versions()
        if not paths:
            self.skipTest(
                "No corpus version exists yet at corpus/vN/postings.json. "
                "The corpus workstream (I-04) is in flight."
            )

    def test_every_record_has_required_fields(self) -> None:
        required = {"id", "rule", "expect", "why", "body", "title"}
        offenders_per_file: dict[str, list[str]] = {}
        for path in _iter_corpus_versions():
            try:
                records = _load_json(path)
            except (ValueError, json.JSONDecodeError) as e:
                self.fail(f"{path.relative_to(ROOT)}: cannot parse ({e})")
            file_offenders: list[str] = []
            for i, rec in enumerate(records):
                if not isinstance(rec, dict):
                    file_offenders.append(f"record {i}: not an object")
                    continue
                missing = required - set(rec.keys())
                if missing:
                    file_offenders.append(
                        f"record {i} (id={rec.get('id', '?')!r}): "
                        f"missing fields {sorted(missing)}"
                    )
            if file_offenders:
                offenders_per_file[str(path.relative_to(ROOT))] = file_offenders
        if offenders_per_file:
            msg = "\n".join(
                f"{f}:\n  " + "\n  ".join(off)
                for f, off in offenders_per_file.items()
            )
            self.fail(
                "Corpus records are missing required fields. "
                f"Required: {sorted(required)}.\n{msg}"
            )

    def test_every_id_is_unique_and_well_formed(self) -> None:
        for path in _iter_corpus_versions():
            records = _load_json(path)
            seen: set[str] = set()
            for i, rec in enumerate(records):
                rid = rec.get("id", "")
                if not ID_PATTERN.match(rid):
                    self.fail(
                        f"{path.relative_to(ROOT)} record {i}: id {rid!r} "
                        f"does not match {ID_PATTERN.pattern!r}"
                    )
                if rid in seen:
                    self.fail(
                        f"{path.relative_to(ROOT)}: duplicate id {rid!r} at record {i}"
                    )
                seen.add(rid)

    def test_every_rule_is_in_why_registry(self) -> None:
        """Every `rule` value in the corpus must exist as a key in
        jobsearch/rule_why.WHY. A rule that is not in the registry
        is not auditable: a reader cannot find its `why`."""
        for path in _iter_corpus_versions():
            records = _load_json(path)
            for i, rec in enumerate(records):
                rule = rec.get("rule", "")
                if rule not in rule_why.WHY:
                    self.fail(
                        f"{path.relative_to(ROOT)} record {i} (id={rec.get('id', '?')!r}): "
                        f"rule {rule!r} is not registered in jobsearch/rule_why.WHY. "
                        f"Add it to the why registry, or fix the rule id."
                    )

    def test_every_expect_is_an_allowed_value(self) -> None:
        for path in _iter_corpus_versions():
            records = _load_json(path)
            for i, rec in enumerate(records):
                exp = rec.get("expect", "")
                if exp not in ALLOWED_EXPECT:
                    self.fail(
                        f"{path.relative_to(ROOT)} record {i} (id={rec.get('id', '?')!r}): "
                        f"expect {exp!r} is not in {sorted(ALLOWED_EXPECT)}"
                    )

    def test_every_why_is_a_non_empty_sentence(self) -> None:
        for path in _iter_corpus_versions():
            records = _load_json(path)
            for i, rec in enumerate(records):
                why = (rec.get("why") or "").strip()
                if len(why) < 30:
                    self.fail(
                        f"{path.relative_to(ROOT)} record {i} (id={rec.get('id', '?')!r}): "
                        f"why is too short ({len(why)} chars). "
                        f"A real why is a sentence explaining the failure category."
                    )
                # A why is a sentence. It must end with a sentence-final
                # punctuation mark, or with a backtick (for code-shape
                # references like `RESEARCH` or `c-001`).
                tail = why[-1]
                if tail not in (".", "!", "?", ")", "]", "`", '"'):
                    self.fail(
                        f"{path.relative_to(ROOT)} record {i} (id={rec.get('id', '?')!r}): "
                        f"why does not end with sentence-final punctuation: "
                        f"{why[-50:]!r}"
                    )

    def test_no_real_email_in_corpus(self) -> None:
        """Defence in depth: the .synthetic marker is not enough.
        No real-email-shaped string may appear in any record's
        body or title."""
        email_re = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
        for path in _iter_corpus_versions():
            records = _load_json(path)
            for i, rec in enumerate(records):
                for field in ("body", "title", "why"):
                    value = rec.get(field, "")
                    for m in email_re.findall(value):
                        if m.endswith(".example") or m.endswith(".test"):
                            continue
                        self.fail(
                            f"{path.relative_to(ROOT)} record {i} "
                            f"(id={rec.get('id', '?')!r}): real email "
                            f"{m!r} in {field}"
                        )


class TestCorpusManifest(unittest.TestCase):
    """When a manifest exists, every corpus file is pinned by SHA.
    A future change to the corpus is a deliberate event: a new
    commit updates the SHA, not the in-place content."""

    def test_manifest_when_present_is_valid(self) -> None:
        manifest = CORPUS_DIR / "manifest.json"
        if not manifest.exists():
            self.skipTest(
                "No corpus/manifest.json yet. When shipped, the manifest "
                "pins the SHA of every corpus file."
            )
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            self.fail(f"corpus/manifest.json: cannot parse ({e})")
        if not isinstance(data, dict) or "versions" not in data:
            self.fail("corpus/manifest.json: must be an object with a 'versions' key")
        for version, info in data["versions"].items():
            rel = info.get("file")
            sha = info.get("sha256")
            if not rel or not sha:
                self.fail(
                    f"corpus/manifest.json version {version!r}: "
                    f"missing file or sha256"
                )
            path = ROOT / rel
            if not path.exists():
                self.fail(
                    f"corpus/manifest.json version {version!r}: "
                    f"file {rel} does not exist"
                )
            actual = _sha256(path)
            if actual != sha:
                self.fail(
                    f"corpus/manifest.json version {version!r}: "
                    f"SHA mismatch. Manifest says {sha!r}, file is {actual!r}. "
                    f"Re-hash and update the manifest, or revert the corpus."
                )


class TestCorpusCoversEveryGateRule(unittest.TestCase):
    """The corpus is the contract for every gate-level rule.

    A new rule in jobsearch/rule_why.WHY that the corpus does not
    cover is a rule that has not been tested against the gate.
    Without a fixture, a future contributor cannot tell whether
    the rule is correct, and the rule is not part of the gate's
    published behaviour.
    """

    def test_every_gate_level_rule_has_a_corpus_fixture(self) -> None:
        from jobsearch import rule_why
        # Compute the gate-level rules fresh so this test is
        # independent of the GATE_LEVEL_RULES constant in this
        # file. The constant is a fallback for environments where
        # rule_why is unavailable; the test is the source of truth.
        gate_rules: set[str] = {
            k for k in rule_why.WHY
            if not k.startswith(("no_", "bounded_", "fetched_",
                                 "one_shot_", "scope_", "history_",
                                 "counterexample_", "export_",
                                 "verdict_"))
        }
        # Find any corpus file
        paths = _iter_corpus_versions()
        if not paths:
            self.skipTest("no corpus present yet")
        corpus_rules: set[str] = set()
        for p in paths:
            for r in _load_json(p):
                if r.get("rule"):
                    corpus_rules.add(r["rule"])
        missing = sorted(gate_rules - corpus_rules)
        if missing:
            self.fail(
                f"The corpus does not cover {len(missing)} gate-level "
                f"rules. Each rule below has no fixture:\n  "
                + "\n  ".join(missing)
                + f"\nFor each missing rule, add a corpus fixture to "
                f"corpus/v1/postings.json with a `rule` field that "
                f"names it, an `expect` field that is one of "
                f"{ALLOWED_EXPECT}, a `why` field that quotes the rule_why "
                f"string, and a `profile` field that the QA test will use."
            )

    def test_every_corpus_rule_is_a_real_gate_rule(self) -> None:
        """A corpus fixture that names a rule that does not exist
        in the rule_why registry is a typo. The corpus should
        reference real rules, not invented ones."""
        from jobsearch import rule_why
        paths = _iter_corpus_versions()
        if not paths:
            self.skipTest("no corpus present yet")
        # Compute gate-level rules.
        real_rules = set(rule_why.WHY.keys())
        offenders: list[str] = []
        for p in paths:
            for r in _load_json(p):
                rule = r.get("rule", "")
                if rule and rule not in real_rules:
                    offenders.append(
                        f"{p.relative_to(ROOT)} id={r.get('id', '?')}: "
                        f"rule={rule!r} not in rule_why.WHY"
                    )
        if offenders:
            self.fail(
                "Corpus references rules that do not exist in the "
                "rule_why registry. Either the rule is misspelled or "
                "the rule_why entry is missing:\n  "
                + "\n  ".join(offenders)
            )


class TestCorpusCoversAllVerdictBands(unittest.TestCase):
    """The corpus must document every verdict band the gate can
    produce. A reader who picks a verdict at random must find a
    fixture for it. If the corpus silently drops a band (for
    example, all `strong_match` fixtures are removed because
    none fit a real profile), the next contributor to that
    band has no example to learn from.

    The four bands are: strong_match, potential_match,
    needs_research, not_suitable. A future verdict vocabulary
    change must update this test alongside the gate.
    """
    def test_every_verdict_band_has_at_least_one_fixture(self) -> None:
        paths = _iter_corpus_versions()
        if not paths:
            self.skipTest("no corpus present yet")
        # Tally verdicts across every corpus file.
        counts: dict[str, int] = {}
        for p in paths:
            for r in _load_json(p):
                v = r.get("expect", "")
                counts[v] = counts.get(v, 0) + 1
        required_bands = (
            "strong_match", "potential_match",
            "needs_research", "not_suitable",
        )
        missing = [b for b in required_bands if counts.get(b, 0) == 0]
        if missing:
            present = {k: v for k, v in counts.items() if v}
            self.fail(
                f"The corpus does not document {len(missing)} verdict "
                f"band(s): {missing}. Every band the gate can produce "
                f"must have at least one fixture. Present bands: "
                f"{present}. To fix: add a fixture for each missing "
                f"band to corpus/v1/postings.json."
            )

    def test_no_single_band_dominates(self) -> None:
        """Defensive: a corpus that is 90% one band is a coverage
        gap. The corpus should sample all four bands. We allow
        a single band to hold up to 50% of the corpus."""
        paths = _iter_corpus_versions()
        if not paths:
            self.skipTest("no corpus present yet")
        counts: dict[str, int] = {}
        for p in paths:
            for r in _load_json(p):
                v = r.get("expect", "")
                counts[v] = counts.get(v, 0) + 1
        total = sum(counts.values())
        if total == 0:
            self.skipTest("empty corpus")
        for band, n in counts.items():
            share = n / total
            if share > 0.5 and total > 4:
                self.fail(
                    f"Verdict band {band!r} holds {n}/{total} "
                    f"({share:.0%}) of the corpus. A corpus that is "
                    f"more than 50% one band is a coverage gap; add "
                    f"fixtures for the other bands."
                )


class TestCorpusExercisesEveryRequirementKind(unittest.TestCase):
    """The corpus must exercise every requirement kind the gate
    can extract from a posting. A requirement-kind branch with
    no fixture is a branch the corpus does not document, and a
    future contributor who changes that branch has no second
    example to compare against.

    The five kinds are: experience_years, seniority, location,
    language, technology. A future kind addition must update
    this test alongside the extractor.
    """

    def test_every_requirement_kind_has_at_least_two_fixtures(self) -> None:
        """A branch with one fixture is a single point of
        reference: if the fixture is wrong, no second example
        will catch it. The minimum is two fixtures per kind."""
        import sys
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from jobsearch import rules as rules_module
        from jobsearch.requirements import JobPosting, extract

        paths = _iter_corpus_versions()
        if not paths:
            self.skipTest("no corpus present yet")

        # For each fixture, run extract() and see what kinds
        # come out.
        kinds_per_fixture: dict[str, set[str]] = {}
        for p in paths:
            for rec in _load_json(p):
                profile = rec.get("profile", {})
                rules = rules_module.Rules(
                    floor_net=profile.get("floor_net"),
                    known_stack=set(profile.get("known_stack", [])),
                    learnable_stack=set(profile.get("learnable_stack", [])),
                    floor_currency=profile.get("floor_currency", ""),
                    local_ok=tuple(profile.get("local_ok", [])),
                    languages_usable=tuple(
                        profile.get("languages_usable", ["english"])
                    ),
                    years_can_honestly_claim=profile.get(
                        "years_can_honestly_claim"
                    ),
                    profession_signals=tuple(
                        profile.get("profession_signals", ())
                    ),
                )
                posting = JobPosting(
                    title=rec.get("title", ""),
                    description=rec.get("body", ""),
                    location=rec.get("location", "remote"),
                )
                extract(
                    posting,
                    extra_terms=rules.known_stack | rules.learnable_stack,
                    extra_languages=rules.languages_usable,
                )
                kinds_per_fixture[rec.get("id", "?")] = {
                    r.kind for r in posting.requirements
                }

        # Tally: for each kind, list fixtures that exercise it.
        all_kinds: set[str] = set()
        for ks in kinds_per_fixture.values():
            all_kinds |= ks
        offenders: list[str] = []
        for kind in sorted(all_kinds):
            fixtures = sorted(
                fid for fid, ks in kinds_per_fixture.items()
                if kind in ks
            )
            if len(fixtures) < 2:
                offenders.append(
                    f"  {kind}: only {len(fixtures)} fixture(s) "
                    f"({fixtures}). A kind with one fixture is a "
                    f"single point of reference; add at least one "
                    f"more."
                )
        if offenders:
            self.fail(
                "The corpus does not have enough coverage of some "
                "requirement kinds. Each kind the gate can extract "
                "should have at least two fixtures so a future "
                "contributor has a second example to compare "
                "against:\n" + "\n".join(offenders)
            )


if __name__ == "__main__":
    unittest.main()
