/** Owns, seals, verifies, and discovers preserved live Gemini artifact collections. */

import { createHash } from "node:crypto";
import { lstat, readFile, readdir, writeFile } from "node:fs/promises";
import path from "node:path";

const LIVE_RUN_ID =
  /^live-([0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})$/u;
const JOB_ID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const LIVE_RUN_RELATIVE_ROOT = path.join("artifacts", "local", "live-runs");
const DEFAULT_LIVE_RUN_POINTER = path.join("artifacts", "default-live-run.json");
const OWNERSHIP_MARKER = ".whyback-owned-artifact-root.json";
const VERIFICATION_MARKER = ".whyback-live-verification.json";
const OWNERSHIP_DOCUMENT = Object.freeze({
  schema_version: 1,
  product: "WhyBack",
  scope: "replaceable_generated_artifact_tree",
});
const VERIFICATION_STATUS = "verified_live_gemini";

/** Reads an optional checked-in pointer that pins dashboard discovery to one run. */
async function defaultLiveRunCollectionId(repositoryRoot) {
  const pointerPath = path.resolve(repositoryRoot, DEFAULT_LIVE_RUN_POINTER);
  let details;
  try {
    details = await lstat(pointerPath);
  } catch (error) {
    if (["ELOOP", "ENOENT", "ENOTDIR"].includes(error?.code)) return undefined;
    throw error;
  }
  if (!details.isFile() || details.isSymbolicLink()) return null;
  try {
    const pointer = JSON.parse(await readFile(pointerPath, "utf8"));
    return isPlainObject(pointer) &&
      Object.keys(pointer).length === 3 &&
      pointer.schema_version === 1 &&
      pointer.product === "WhyBack" &&
      isLiveRunCollectionId(pointer.collection_id)
      ? pointer.collection_id
      : null;
  } catch (error) {
    if (error instanceof SyntaxError) return null;
    throw error;
  }
}

/** Returns metadata only for a real directory that is not a symbolic link. */
async function realDirectoryDetails(directory) {
  try {
    const details = await lstat(directory);
    return details.isDirectory() && !details.isSymbolicLink() ? details : null;
  } catch (error) {
    if (["ELOOP", "ENOENT", "ENOTDIR"].includes(error?.code)) return null;
    throw error;
  }
}

/** Checks that a directory carries exactly the expected WhyBack ownership marker. */
async function isExactOwnershipMarker(directory) {
  const marker = path.join(directory, OWNERSHIP_MARKER);
  let details;
  try {
    details = await lstat(marker);
  } catch (error) {
    if (["ELOOP", "ENOENT", "ENOTDIR"].includes(error?.code)) return false;
    throw error;
  }
  if (!details.isFile() || details.isSymbolicLink()) return false;
  try {
    const document = JSON.parse(await readFile(marker, "utf8"));
    return (
      document !== null &&
      typeof document === "object" &&
      !Array.isArray(document) &&
      Object.keys(document).length === Object.keys(OWNERSHIP_DOCUMENT).length &&
      Object.entries(OWNERSHIP_DOCUMENT).every(
        ([key, value]) => document[key] === value,
      )
    );
  } catch (error) {
    if (
      error instanceof SyntaxError ||
      ["ELOOP", "ENOENT", "ENOTDIR"].includes(error?.code)
    ) {
      return false;
    }
    throw error;
  }
}

/** Identifies record-shaped JSON values used in trusted marker checks. */
function isPlainObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

/** Confirms that a manifest proves one complete, human-reviewed live Gemini batch. */
function terminalManifestIsLive(manifest) {
  if (
    !isPlainObject(manifest) ||
    manifest.dataset_kind !== "official_complete_journey" ||
    manifest.backend !== "gemini" ||
    manifest.execution_mode !== "live" ||
    manifest.model_execution !== "live_gemini" ||
    manifest.human_review_required !== true ||
    manifest.customer_outreach_executed !== false ||
    !Array.isArray(manifest.selected_household_ids) ||
    !Array.isArray(manifest.completed_household_ids) ||
    !Array.isArray(manifest.failed_household_ids) ||
    !Array.isArray(manifest.skipped_household_ids) ||
    manifest.skipped_household_ids.length !== 0
  ) {
    return false;
  }
  const householdId = /^[A-Za-z0-9_-]{1,64}$/u;
  const arraysAreValid = [
    manifest.selected_household_ids,
    manifest.completed_household_ids,
    manifest.failed_household_ids,
  ].every((items) =>
    items.every((item) => typeof item === "string" && householdId.test(item)),
  );
  if (!arraysAreValid || manifest.selected_household_ids.length === 0) return false;
  const selected = new Set(manifest.selected_household_ids);
  const terminal = [
    ...manifest.completed_household_ids,
    ...manifest.failed_household_ids,
  ];
  return (
    selected.size === manifest.selected_household_ids.length &&
    terminal.length === selected.size &&
    new Set(terminal).size === selected.size &&
    terminal.every((item) => selected.has(item))
  );
}

/** Reads bytes only from a real, non-symlink file. */
async function realFileBytes(filePath) {
  let details;
  try {
    details = await lstat(filePath);
  } catch (error) {
    if (["ELOOP", "ENOENT", "ENOTDIR"].includes(error?.code)) return null;
    throw error;
  }
  return details.isFile() && !details.isSymbolicLink()
    ? readFile(filePath)
    : null;
}

/** Produces the hexadecimal SHA-256 identity for one byte sequence. */
function sha256(content) {
  return createHash("sha256").update(content).digest("hex");
}

/** Hashes every safe artifact path and file hash into one deterministic tree digest. */
async function artifactTreeSha256(directory) {
  const files = [];
  /** Walks the tree while rejecting links, special files, and unreadable branches. */
  async function walk(current) {
    let entries;
    try {
      entries = await readdir(current, { withFileTypes: true });
    } catch (error) {
      if (["ELOOP", "ENOENT", "ENOTDIR"].includes(error?.code)) return false;
      throw error;
    }
    for (const entry of entries) {
      if (entry.isSymbolicLink()) return false;
      const candidate = path.join(current, entry.name);
      if (entry.isDirectory()) {
        if (!(await walk(candidate))) return false;
      } else if (entry.isFile()) {
        const relative = path.relative(directory, candidate).split(path.sep).join("/");
        if (relative !== VERIFICATION_MARKER) files.push({ candidate, relative });
      } else {
        return false;
      }
    }
    return true;
  }
  if (!(await walk(directory))) return null;
  files.sort((left, right) => left.relative.localeCompare(right.relative));
  const digest = createHash("sha256");
  for (const file of files) {
    const content = await realFileBytes(file.candidate);
    if (!content) return null;
    digest.update(file.relative);
    digest.update("\0");
    digest.update(sha256(content));
    digest.update("\n");
  }
  return digest.digest("hex");
}

/** Resolves the live-run root only when every directory segment is real. */
async function safeLiveRunRoot(repositoryRoot) {
  let current = path.resolve(repositoryRoot);
  for (const segment of ["artifacts", "local", "live-runs"]) {
    current = path.join(current, segment);
    if (!(await realDirectoryDetails(current))) return null;
  }
  return current;
}

/** Extracts the canonical version-four UUID from a live collection ID. */
function collectionUuid(collectionId) {
  return typeof collectionId === "string"
    ? LIVE_RUN_ID.exec(collectionId)?.[1] ?? null
    : null;
}

/** Reports whether a collection ID has the only accepted live-run shape. */
export function isLiveRunCollectionId(collectionId) {
  return collectionUuid(collectionId) !== null;
}

/** Derives the fixed collection ID and output path for one validated job ID. */
export function createLiveRunDescriptor(repositoryRoot, jobId) {
  if (typeof jobId !== "string" || !JOB_ID.test(jobId)) {
    throw new TypeError("Live run job ID must be a canonical version-4 UUID.");
  }
  const collectionId = `live-${jobId}`;
  const relativePath = path.join(LIVE_RUN_RELATIVE_ROOT, collectionId);
  return {
    collectionId,
    directory: path.resolve(repositoryRoot, relativePath),
    relativePath,
  };
}

/** Builds compact display metadata for a valid CLI-run collection. */
export function liveRunCollectionDefinition(collectionId, modifiedAtMs = 0) {
  const uuid = collectionUuid(collectionId);
  if (!uuid) return null;
  return {
    id: collectionId,
    relativePath: path.join(LIVE_RUN_RELATIVE_ROOT, collectionId),
    title: `Run · ${uuid.slice(0, 8)}`,
    liveRun: true,
    modifiedAtMs,
  };
}

/** Resolves a live directory only when it remains under the safe root and is owned. */
export async function resolveOwnedLiveRunDirectory(repositoryRoot, collectionId) {
  const definition = liveRunCollectionDefinition(collectionId);
  if (!definition) return null;
  const root = await safeLiveRunRoot(repositoryRoot);
  if (!root) return null;
  const candidate = path.resolve(repositoryRoot, definition.relativePath);
  if (!candidate.startsWith(`${root}${path.sep}`)) return null;
  if (!(await realDirectoryDetails(candidate))) return null;
  return (await isExactOwnershipMarker(candidate)) ? candidate : null;
}

/** Revalidates the manifest, seal, and current artifact bytes before browsing a run. */
export async function resolveVerifiedLiveRunDirectory(
  repositoryRoot,
  collectionId,
) {
  const directory = await resolveOwnedLiveRunDirectory(repositoryRoot, collectionId);
  if (!directory) return null;
  const manifestBytes = await realFileBytes(path.join(directory, "manifest.json"));
  const markerBytes = await realFileBytes(path.join(directory, VERIFICATION_MARKER));
  if (!manifestBytes || !markerBytes) return null;
  try {
    const manifest = JSON.parse(manifestBytes.toString("utf8"));
    const marker = JSON.parse(markerBytes.toString("utf8"));
    const artifactDigest = await artifactTreeSha256(directory);
    return terminalManifestIsLive(manifest) &&
      isPlainObject(marker) &&
      Object.keys(marker).length === 6 &&
      marker.schema_version === 1 &&
      marker.product === "WhyBack" &&
      marker.status === VERIFICATION_STATUS &&
      marker.collection_id === collectionId &&
      marker.manifest_sha256 === sha256(manifestBytes) &&
      artifactDigest !== null &&
      marker.artifact_tree_sha256 === artifactDigest
      ? directory
      : null;
  } catch (error) {
    if (error instanceof SyntaxError) return null;
    throw error;
  }
}

/** Writes a one-time verification seal after a live artifact tree passes validation. */
export async function markLiveRunVerified(repositoryRoot, collectionId) {
  const directory = await resolveOwnedLiveRunDirectory(repositoryRoot, collectionId);
  if (!directory) {
    throw new Error("The live run output directory is not an owned WhyBack tree.");
  }
  const manifestBytes = await realFileBytes(path.join(directory, "manifest.json"));
  if (!manifestBytes) {
    throw new Error("The live run manifest is unavailable.");
  }
  let manifest;
  try {
    manifest = JSON.parse(manifestBytes.toString("utf8"));
  } catch (error) {
    if (error instanceof SyntaxError) {
      throw new Error("The live run manifest is invalid.", { cause: error });
    }
    throw error;
  }
  if (!terminalManifestIsLive(manifest)) {
    throw new Error("The live run manifest does not prove a terminal live execution.");
  }
  const marker = {
    schema_version: 1,
    product: "WhyBack",
    status: VERIFICATION_STATUS,
    collection_id: collectionId,
    manifest_sha256: sha256(manifestBytes),
    artifact_tree_sha256: await artifactTreeSha256(directory),
  };
  if (!marker.artifact_tree_sha256) {
    throw new Error("The live run artifact tree is unsafe or unreadable.");
  }
  await writeFile(
    path.join(directory, VERIFICATION_MARKER),
    `${JSON.stringify(marker, null, 2)}\n`,
    { encoding: "utf8", flag: "wx", mode: 0o600 },
  );
  return directory;
}

/** Finds sealed live collections and orders the newest reviewer results first. */
export async function discoverLiveRunCollections(repositoryRoot) {
  const root = await safeLiveRunRoot(repositoryRoot);
  if (!root) return [];
  const pinnedCollectionId = await defaultLiveRunCollectionId(repositoryRoot);
  if (pinnedCollectionId === null) return [];
  let entries;
  try {
    entries = await readdir(root, { withFileTypes: true });
  } catch (error) {
    if (["ELOOP", "ENOENT", "ENOTDIR"].includes(error?.code)) return [];
    throw error;
  }
  const definitions = [];
  for (const entry of entries) {
    if (
      !entry.isDirectory() ||
      entry.isSymbolicLink() ||
      !isLiveRunCollectionId(entry.name) ||
      (pinnedCollectionId !== undefined && entry.name !== pinnedCollectionId)
    ) {
      continue;
    }
    const directory = await resolveVerifiedLiveRunDirectory(
      repositoryRoot,
      entry.name,
    );
    if (!directory) continue;
    const details = await realDirectoryDetails(directory);
    if (!details) continue;
    definitions.push(liveRunCollectionDefinition(entry.name, details.mtimeMs));
  }
  return definitions
    .filter(Boolean)
    .sort(
      (left, right) =>
        right.modifiedAtMs - left.modifiedAtMs ||
        right.id.localeCompare(left.id),
    );
}
