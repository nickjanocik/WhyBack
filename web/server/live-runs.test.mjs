/** Verifies live-run ownership, sealing, tamper detection, and safe discovery. */

import assert from "node:assert/strict";
import {
  mkdir,
  mkdtemp,
  readFile,
  rm,
  symlink,
  utimes,
  writeFile,
} from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import {
  createLiveRunDescriptor,
  discoverLiveRunCollections,
  isLiveRunCollectionId,
  markLiveRunVerified,
  resolveOwnedLiveRunDirectory,
  resolveVerifiedLiveRunDirectory,
} from "./live-runs.mjs";

const FIRST_JOB = "123e4567-e89b-42d3-a456-426614174000";
const SECOND_JOB = "223e4567-e89b-42d3-b456-426614174000";
const THIRD_JOB = "323e4567-e89b-42d3-8456-426614174000";
const FOURTH_JOB = "423e4567-e89b-42d3-9456-426614174000";
const OWNERSHIP = {
  schema_version: 1,
  product: "WhyBack",
  scope: "replaceable_generated_artifact_tree",
};

/** Creates a disposable repository root and registers automatic cleanup. */
async function temporaryRoot(context) {
  const root = await mkdtemp(path.join(os.tmpdir(), "whyback-live-runs-test-"));
  context.after(() => rm(root, { recursive: true, force: true }));
  return root;
}

/** Creates a live-run directory with the supplied ownership marker. */
async function makeOwnedRun(root, jobId, marker = OWNERSHIP) {
  const descriptor = createLiveRunDescriptor(root, jobId);
  await mkdir(descriptor.directory, { recursive: true });
  await writeFile(
    path.join(descriptor.directory, ".whyback-owned-artifact-root.json"),
    `${JSON.stringify(marker)}\n`,
  );
  return descriptor;
}

/** Writes the smallest terminal live artifact set that can be sealed. */
async function completeLiveRun(root, descriptor, householdId = "7") {
  await writeFile(
    path.join(descriptor.directory, "manifest.json"),
    `${JSON.stringify({
      dataset_kind: "official_complete_journey",
      backend: "gemini",
      execution_mode: "live",
      model_execution: "live_gemini",
      selected_household_ids: [householdId],
      completed_household_ids: [householdId],
      failed_household_ids: [],
      skipped_household_ids: [],
      human_review_required: true,
      customer_outreach_executed: false,
    })}\n`,
  );
  await markLiveRunVerified(root, descriptor.collectionId);
}

test("derives only canonical version-4 UUID collection paths", () => {
  const root = path.join(os.tmpdir(), "whyback-root");
  const descriptor = createLiveRunDescriptor(root, FIRST_JOB);

  assert.equal(descriptor.collectionId, `live-${FIRST_JOB}`);
  assert.equal(
    descriptor.directory,
    path.join(root, "artifacts", "local", "live-runs", `live-${FIRST_JOB}`),
  );
  assert.equal(isLiveRunCollectionId(descriptor.collectionId), true);

  for (const invalid of [
    `../${FIRST_JOB}`,
    FIRST_JOB.toUpperCase(),
    "123e4567-e89b-12d3-a456-426614174000",
    `live-${FIRST_JOB}`,
    "not-a-uuid",
  ]) {
    assert.throws(() => createLiveRunDescriptor(root, invalid), TypeError);
  }
  for (const invalid of [
    FIRST_JOB,
    `live-../${FIRST_JOB}`,
    `live-${FIRST_JOB}/customer_7`,
    `live-${FIRST_JOB.toUpperCase()}`,
  ]) {
    assert.equal(isLiveRunCollectionId(invalid), false);
  }
});

test("resolves only real owned run directories with an exact marker", async (context) => {
  const root = await temporaryRoot(context);
  const owned = await makeOwnedRun(root, FIRST_JOB);
  assert.equal(
    await resolveOwnedLiveRunDirectory(root, owned.collectionId),
    owned.directory,
  );

  const malformed = await makeOwnedRun(root, SECOND_JOB, {
    ...OWNERSHIP,
    unexpected: true,
  });
  assert.equal(
    await resolveOwnedLiveRunDirectory(root, malformed.collectionId),
    null,
  );
  await writeFile(
    path.join(malformed.directory, ".whyback-owned-artifact-root.json"),
    "not-json\n",
  );
  assert.equal(
    await resolveOwnedLiveRunDirectory(root, malformed.collectionId),
    null,
  );
  assert.equal(
    await resolveOwnedLiveRunDirectory(root, `live-../${FIRST_JOB}`),
    null,
  );
});

test("resolves a terminal collection only after verification and rejects later mutation", async (context) => {
  const root = await temporaryRoot(context);
  const run = await makeOwnedRun(root, FIRST_JOB);
  await completeLiveRun(root, run);
  assert.equal(
    await resolveVerifiedLiveRunDirectory(root, run.collectionId),
    run.directory,
  );

  const manifestPath = path.join(run.directory, "manifest.json");
  await writeFile(manifestPath, `${await readFile(manifestPath, "utf8")} `);
  assert.equal(
    await resolveVerifiedLiveRunDirectory(root, run.collectionId),
    null,
  );

  const artifactRun = await makeOwnedRun(root, SECOND_JOB);
  const customerDirectory = path.join(artifactRun.directory, "customer_8");
  const reportPath = path.join(customerDirectory, "report.json");
  await mkdir(customerDirectory);
  await writeFile(reportPath, "{}\n");
  await completeLiveRun(root, artifactRun, "8");
  assert.equal(
    await resolveVerifiedLiveRunDirectory(root, artifactRun.collectionId),
    artifactRun.directory,
  );

  await writeFile(reportPath, '{"changed":true}\n');
  assert.equal(
    await resolveVerifiedLiveRunDirectory(root, artifactRun.collectionId),
    null,
  );
});

test("rejects symlinked run roots, run directories, and ownership markers", async (context) => {
  const root = await temporaryRoot(context);
  const outside = await mkdtemp(path.join(os.tmpdir(), "whyback-live-outside-"));
  context.after(() => rm(outside, { recursive: true, force: true }));

  const linkedRunRoot = path.join(root, "linked-root");
  await mkdir(path.join(linkedRunRoot, "artifacts", "local"), { recursive: true });
  await symlink(outside, path.join(linkedRunRoot, "artifacts", "local", "live-runs"));
  assert.equal(
    await resolveOwnedLiveRunDirectory(linkedRunRoot, `live-${FIRST_JOB}`),
    null,
  );

  const linkedAncestorRoot = path.join(root, "linked-ancestor");
  const outsideLocal = path.join(outside, "local");
  const outsideRun = path.join(outsideLocal, "live-runs", `live-${FIRST_JOB}`);
  await mkdir(path.join(linkedAncestorRoot, "artifacts"), { recursive: true });
  await mkdir(outsideRun, { recursive: true });
  await writeFile(
    path.join(outsideRun, ".whyback-owned-artifact-root.json"),
    JSON.stringify(OWNERSHIP),
  );
  await symlink(outsideLocal, path.join(linkedAncestorRoot, "artifacts", "local"));
  assert.equal(
    await resolveOwnedLiveRunDirectory(linkedAncestorRoot, `live-${FIRST_JOB}`),
    null,
  );

  const liveRoot = path.join(root, "artifacts", "local", "live-runs");
  await mkdir(liveRoot, { recursive: true });
  await writeFile(
    path.join(outside, ".whyback-owned-artifact-root.json"),
    JSON.stringify(OWNERSHIP),
  );
  await symlink(outside, path.join(liveRoot, `live-${FIRST_JOB}`));
  assert.equal(
    await resolveOwnedLiveRunDirectory(root, `live-${FIRST_JOB}`),
    null,
  );

  const markerLinkRun = createLiveRunDescriptor(root, SECOND_JOB);
  await mkdir(markerLinkRun.directory, { recursive: true });
  await symlink(
    path.join(outside, ".whyback-owned-artifact-root.json"),
    path.join(markerLinkRun.directory, ".whyback-owned-artifact-root.json"),
  );
  assert.equal(
    await resolveOwnedLiveRunDirectory(root, markerLinkRun.collectionId),
    null,
  );
});

test("discovers owned Live Gemini collections newest first", async (context) => {
  const root = await temporaryRoot(context);
  const older = await makeOwnedRun(root, FIRST_JOB);
  const newer = await makeOwnedRun(root, SECOND_JOB);
  await completeLiveRun(root, older, "7");
  await completeLiveRun(root, newer, "8");
  const oldTime = new Date("2026-08-25T12:00:00Z");
  const newTime = new Date("2026-08-25T12:01:00Z");
  await utimes(older.directory, oldTime, oldTime);
  await utimes(newer.directory, newTime, newTime);

  const invalidName = path.join(
    root,
    "artifacts",
    "local",
    "live-runs",
    "live-not-a-uuid",
  );
  await mkdir(invalidName);
  await writeFile(
    path.join(invalidName, ".whyback-owned-artifact-root.json"),
    JSON.stringify(OWNERSHIP),
  );
  const unverified = await makeOwnedRun(root, THIRD_JOB);
  await writeFile(
    path.join(unverified.directory, "manifest.json"),
    "{}\n",
  );
  const malformed = createLiveRunDescriptor(root, FOURTH_JOB);
  await mkdir(malformed.directory);
  await writeFile(
    path.join(malformed.directory, ".whyback-owned-artifact-root.json"),
    "not-json\n",
  );

  const definitions = await discoverLiveRunCollections(root);
  assert.deepEqual(
    definitions.map((item) => item.id),
    [newer.collectionId, older.collectionId],
  );
  assert.deepEqual(
    definitions.map((item) => item.title),
    ["Run · 223e4567", "Run · 123e4567"],
  );
  assert.ok(definitions.every((item) => item.liveRun === true));
});
