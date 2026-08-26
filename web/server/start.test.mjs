/** Tests server startup without loading real credentials or opening a listener. */

import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import path from "node:path";
import test from "node:test";

import {
  browserCommand,
  browserLaunchEnabled,
  dashboardUrl,
  launchDashboard,
  loadRepositoryEnvironment,
  openBrowserWhenListening,
  openSystemBrowser,
  repositoryEnvPath,
} from "./start.mjs";

test("loads the repository-root environment without replacing an exported Gemini key", () => {
  const environment = { GEMINI_API_KEY: "exported-placeholder" };
  let loadedPath = null;

  loadRepositoryEnvironment({
    environment,
    loadEnvFile: (envPath) => {
      loadedPath = envPath;
      environment.GEMINI_API_KEY = "file-placeholder";
    },
  });

  assert.equal(loadedPath, repositoryEnvPath);
  assert.equal(path.basename(loadedPath), ".env");
  assert.equal(environment.GEMINI_API_KEY, "exported-placeholder");
});

test("tolerates only a missing repository environment file", () => {
  assert.doesNotThrow(() =>
    loadRepositoryEnvironment({
      environment: {},
      loadEnvFile: () => {
        const error = new Error("missing");
        error.code = "ENOENT";
        throw error;
      },
    }),
  );

  assert.throws(
    () =>
      loadRepositoryEnvironment({
        environment: {},
        loadEnvFile: () => {
          const error = new Error("denied");
          error.code = "EACCES";
          throw error;
        },
      }),
    (error) => error?.code === "EACCES",
  );
});

test("loads the environment before dynamically importing and starting the server", async () => {
  const calls = [];
  const server = {
    /** Supplies the minimal listener shape returned by the fake server module. */
    close() {},
  };

  const launched = await launchDashboard({
    loadEnvironment: () => calls.push("environment"),
    importServer: async () => {
      calls.push("import");
      return {
        /** Records that launchDashboard invoked the dynamically imported entry point. */
        startServer() {
          calls.push("start");
          return server;
        },
      };
    },
  });

  assert.deepEqual(calls, ["environment", "import", "start"]);
  assert.equal(launched, server);
});

test("resolves the dashboard URL with the bridge's bounded port fallback", () => {
  assert.equal(dashboardUrl({}), "http://127.0.0.1:4173");
  assert.equal(
    dashboardUrl({ WHYBACK_DASHBOARD_PORT: "4912" }),
    "http://127.0.0.1:4912",
  );
  assert.equal(
    dashboardUrl({ WHYBACK_DASHBOARD_PORT: "not-a-port" }),
    "http://127.0.0.1:4173",
  );
});

test("opens only for an explicit interactive launch outside CI and opt-out modes", () => {
  assert.equal(
    browserLaunchEnabled({ requested: true, environment: {}, interactive: true }),
    true,
  );
  assert.equal(
    browserLaunchEnabled({ requested: false, environment: {}, interactive: true }),
    false,
  );
  assert.equal(
    browserLaunchEnabled({ requested: true, environment: {}, interactive: false }),
    false,
  );
  for (const environment of [
    { CI: "true" },
    { NO_OPEN: "1" },
    { WHYBACK_NO_OPEN: "yes" },
  ]) {
    assert.equal(
      browserLaunchEnabled({ requested: true, environment, interactive: true }),
      false,
    );
  }
  assert.equal(
    browserLaunchEnabled({
      requested: true,
      environment: { CI: "0", NO_OPEN: "false" },
      interactive: true,
    }),
    true,
  );
});

test("uses shell-free operating-system browser commands", () => {
  const url = "http://127.0.0.1:4173";
  assert.deepEqual(browserCommand(url, "darwin"), {
    command: "open",
    args: [url],
  });
  assert.deepEqual(browserCommand(url, "linux"), {
    command: "xdg-open",
    args: [url],
  });
  assert.deepEqual(browserCommand(url, "win32"), {
    command: "cmd.exe",
    args: ["/d", "/s", "/c", "start", "", url],
  });
});

test("spawns a detached browser process without a shell", () => {
  const calls = [];
  let unrefCount = 0;
  const child = new EventEmitter();
  child.unref = () => {
    unrefCount += 1;
  };

  assert.equal(
    openSystemBrowser("http://127.0.0.1:4173", {
      platform: "darwin",
      spawnProcess: (...args) => {
        calls.push(args);
        return child;
      },
    }),
    true,
  );
  assert.deepEqual(calls, [
    [
      "open",
      ["http://127.0.0.1:4173"],
      { detached: true, stdio: "ignore", shell: false },
    ],
  ]);
  assert.equal(unrefCount, 1);
});

test("opens the browser exactly once after the server starts listening", () => {
  const server = new EventEmitter();
  server.listening = false;
  const opened = [];

  openBrowserWhenListening(server, "http://127.0.0.1:4173", (url) => {
    opened.push(url);
  });
  assert.deepEqual(opened, []);

  server.emit("listening");
  server.emit("listening");
  assert.deepEqual(opened, ["http://127.0.0.1:4173"]);
});

test("the launcher requests one browser open after starting the server", async () => {
  const server = new EventEmitter();
  server.listening = false;
  const opened = [];

  const launched = await launchDashboard({
    loadEnvironment: () => {},
    importServer: async () => ({ startServer: () => server }),
    browserRequested: true,
    environment: {},
    interactive: true,
    browserOpener: (url) => opened.push(url),
  });

  assert.equal(launched, server);
  assert.deepEqual(opened, []);
  server.listening = true;
  server.emit("listening");
  assert.deepEqual(opened, ["http://127.0.0.1:4173"]);
});
