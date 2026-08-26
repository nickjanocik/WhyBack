/** Loads repository-local settings before starting the localhost dashboard bridge. */

import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const modulePath = fileURLToPath(import.meta.url);
const repositoryRoot = path.resolve(path.dirname(modulePath), "../..");
export const repositoryEnvPath = path.join(repositoryRoot, ".env");

/** Loads the ignored root .env while preserving an explicitly exported Gemini key. */
export function loadRepositoryEnvironment({
  environment = process.env,
  envPath = repositoryEnvPath,
  loadEnvFile = process.loadEnvFile,
} = {}) {
  const hadExportedGeminiKey = Object.hasOwn(environment, "GEMINI_API_KEY");
  const exportedGeminiKey = environment.GEMINI_API_KEY;
  try {
    loadEnvFile(envPath);
  } catch (error) {
    if (error?.code !== "ENOENT") throw error;
  } finally {
    if (hadExportedGeminiKey) {
      environment.GEMINI_API_KEY = exportedGeminiKey;
    }
  }
}

/** Loads server-only environment values before importing and starting the bridge. */
export async function launchDashboard({
  loadEnvironment = loadRepositoryEnvironment,
  importServer = () => import("./index.mjs"),
} = {}) {
  loadEnvironment();
  const { startServer } = await importServer();
  return startServer();
}

// Start automatically only when this module is the command-line entry point.
if (process.argv[1] && path.resolve(process.argv[1]) === modulePath) {
  await launchDashboard();
}
