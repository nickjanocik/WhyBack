/** Loads repository-local settings before starting the localhost dashboard bridge. */

import { spawn } from "node:child_process";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const modulePath = fileURLToPath(import.meta.url);
const repositoryRoot = path.resolve(path.dirname(modulePath), "../..");
export const repositoryEnvPath = path.join(repositoryRoot, ".env");

/** Treats conventional environment flags as enabled without making `0` truthy. */
function environmentFlag(value) {
  return value !== undefined && !["", "0", "false", "no", "off"].includes(
    String(value).trim().toLowerCase(),
  );
}

/** Resolves the public localhost URL using the bridge's documented port rules. */
export function dashboardUrl(environment = process.env) {
  const configuredPort = Number(environment.WHYBACK_DASHBOARD_PORT || 4173);
  const port =
    Number.isInteger(configuredPort) && configuredPort > 0 ? configuredPort : 4173;
  return `http://127.0.0.1:${port}`;
}

/** Allows an explicit launcher to open a browser only in an interactive session. */
export function browserLaunchEnabled({
  requested = false,
  environment = process.env,
  interactive = Boolean(process.stdout.isTTY),
} = {}) {
  return (
    requested &&
    interactive &&
    !environmentFlag(environment.CI) &&
    !environmentFlag(environment.NO_OPEN) &&
    !environmentFlag(environment.WHYBACK_NO_OPEN)
  );
}

/** Returns a shell-free default-browser command for each supported desktop family. */
export function browserCommand(url, platform = process.platform) {
  if (platform === "darwin") return { command: "open", args: [url] };
  if (platform === "win32") {
    return {
      command: "cmd.exe",
      args: ["/d", "/s", "/c", "start", "", url],
    };
  }
  return { command: "xdg-open", args: [url] };
}

/** Opens the system browser without retaining it as a dashboard child process. */
export function openSystemBrowser(
  url,
  {
    platform = process.platform,
    spawnProcess = spawn,
    writeWarning = (message) => process.stderr.write(message),
  } = {},
) {
  const { command, args } = browserCommand(url, platform);
  try {
    const child = spawnProcess(command, args, {
      detached: true,
      stdio: "ignore",
      shell: false,
    });
    child.once("error", () => {
      writeWarning(`WhyBack could not open a browser. Visit ${url} manually.\n`);
    });
    child.unref();
    return true;
  } catch {
    writeWarning(`WhyBack could not open a browser. Visit ${url} manually.\n`);
    return false;
  }
}

/** Opens the dashboard once, and only after its HTTP listener is reachable. */
export function openBrowserWhenListening(server, url, opener = openSystemBrowser) {
  let opened = false;
  /** Guards against repeated or synthetic listener events. */
  const openOnce = () => {
    if (opened) return;
    opened = true;
    opener(url);
  };
  if (server.listening) {
    openOnce();
  } else {
    server.once("listening", openOnce);
  }
}

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
  browserRequested = false,
  environment = process.env,
  interactive = Boolean(process.stdout.isTTY),
  browserOpener = openSystemBrowser,
} = {}) {
  loadEnvironment();
  const { startServer } = await importServer();
  const server = startServer();
  if (browserLaunchEnabled({ requested: browserRequested, environment, interactive })) {
    openBrowserWhenListening(server, dashboardUrl(environment), browserOpener);
  }
  return server;
}

// Start automatically only when this module is the command-line entry point.
if (process.argv[1] && path.resolve(process.argv[1]) === modulePath) {
  await launchDashboard({ browserRequested: process.argv.slice(2).includes("--open") });
}
