/** Starts the local artifact bridge and Vite together for dashboard development. */

import { spawn } from "node:child_process";
import process from "node:process";
import { setTimeout } from "node:timers";
import { URL } from "node:url";

const children = [];
let stopping = false;

/** Starts one development child and makes an unexpected child exit stop the pair. */
function start(command, args, environment = process.env) {
  const child = spawn(command, args, {
    cwd: new URL("..", import.meta.url),
    env: environment,
    stdio: "inherit",
    shell: false,
  });
  children.push(child);
  // Either child is required for development, so one unexpected exit tears down both.
  child.once("exit", (code, signal) => {
    if (!stopping) {
      stop(code ?? (signal ? 1 : 0));
    }
  });
}

/** Stops each development child once and then exits with the triggering status. */
function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  for (const child of children) {
    if (!child.killed) child.kill("SIGTERM");
  }
  setTimeout(() => process.exit(code), 50).unref();
}

// Forward terminal shutdown signals through the shared, idempotent cleanup path.
process.on("SIGINT", () => stop(0));
process.on("SIGTERM", () => stop(0));

start(process.execPath, ["server/start.mjs"]);
const viteEnvironment = { ...process.env };
delete viteEnvironment.GEMINI_API_KEY;
start("npx", ["vite"], viteEnvironment);
