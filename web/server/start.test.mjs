/** Tests server startup without loading real credentials or opening a listener. */

import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";

import {
  launchDashboard,
  loadRepositoryEnvironment,
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
