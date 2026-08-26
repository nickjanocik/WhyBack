import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const modulePath = fileURLToPath(import.meta.url);
const repositoryRoot = path.resolve(path.dirname(modulePath), "../..");
export const repositoryEnvPath = path.join(repositoryRoot, ".env");

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

export async function launchDashboard({
  loadEnvironment = loadRepositoryEnvironment,
  importServer = () => import("./index.mjs"),
} = {}) {
  loadEnvironment();
  const { startServer } = await importServer();
  return startServer();
}

if (process.argv[1] && path.resolve(process.argv[1]) === modulePath) {
  await launchDashboard();
}
