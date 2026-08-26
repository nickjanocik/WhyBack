import { createHash } from "node:crypto";
import { lstat, readFile, readdir, writeFile } from "node:fs/promises";
import path from "node:path";

const LIVE_RUN_ID =
  /^live-([0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})$/u;
const JOB_ID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const LIVE_RUN_RELATIVE_ROOT = path.join("artifacts", "local", "live-runs");
const OWNERSHIP_MARKER = ".whyback-owned-artifact-root.json";
const VERIFICATION_MARKER = ".whyback-live-verification.json";
const OWNERSHIP_DOCUMENT = Object.freeze({
  schema_version: 1,
  product: "WhyBack",
  scope: "replaceable_generated_artifact_tree",
});
const VERIFICATION_STATUS = "verified_live_gemini";

async function realDirectoryDetails(directory) {
  try {
    const details = await lstat(directory);
    return details.isDirectory() && !details.isSymbolicLink() ? details : null;
  } catch (error) {
    if (["ELOOP", "ENOENT", "ENOTDIR"].includes(error?.code)) return null;
    throw error;
  }
}

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

function isPlainObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

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

function sha256(content) {
  return createHash("sha256").update(content).digest("hex");
}

async function artifactTreeSha256(directory) {
  const files = [];
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

async function safeLiveRunRoot(repositoryRoot) {
  let current = path.resolve(repositoryRoot);
  for (const segment of ["artifacts", "local", "live-runs"]) {
    current = path.join(current, segment);
    if (!(await realDirectoryDetails(current))) return null;
  }
  return current;
}

function collectionUuid(collectionId) {
  return typeof collectionId === "string"
    ? LIVE_RUN_ID.exec(collectionId)?.[1] ?? null
    : null;
}

export function isLiveRunCollectionId(collectionId) {
  return collectionUuid(collectionId) !== null;
}

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

export function liveRunCollectionDefinition(collectionId, modifiedAtMs = 0) {
  const uuid = collectionUuid(collectionId);
  if (!uuid) return null;
  return {
    id: collectionId,
    relativePath: path.join(LIVE_RUN_RELATIVE_ROOT, collectionId),
    title: `Live Gemini · ${uuid.slice(0, 8)}`,
    liveRun: true,
    modifiedAtMs,
  };
}

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

export async function discoverLiveRunCollections(repositoryRoot) {
  const root = await safeLiveRunRoot(repositoryRoot);
  if (!root) return [];
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
      !isLiveRunCollectionId(entry.name)
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
