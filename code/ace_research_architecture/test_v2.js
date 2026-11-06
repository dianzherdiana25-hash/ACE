"use strict";
/** Offline exact-output replay for R3-v2. Node.js 18+ built-ins only.
 * Run: node code/ace_research_architecture/test_v2.js
 * No dynamic candidate source execution or external calls. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const {r3StudyV2} = require("./experiment_v2.js");
const archived = JSON.parse(fs.readFileSync(path.join(__dirname, "results_v2_js.json"), "utf8"));
const actual = r3StudyV2();
assert.equal(actual.tests.passed, 7);
assert.equal(actual.protocol.id, "ACE-R3-JS-V2-NEUTRAL-EXPLORATORY");
for (const bank of ["development", "confirmation", "new_public_tasks"]) {
  assert.equal(actual[bank].rows.length, 72);
  for (const arm of ["fixed", "config", "random", "evolve", "neutral", "neutral_coverage"]) {
    const summary = actual[bank].summary[arm];
    assert.equal(summary.cases, 12);
    assert.ok(summary.candidates <= 12 * actual.protocol.candidates_per_search);
  }
}
assert.deepStrictEqual(actual, archived, "exact result replay mismatch");
process.stdout.write("PASS R3 JS v2: 7 self-tests; 216/216 exact replay records; 6 arms; 3 banks\n");
