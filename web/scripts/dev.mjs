import { spawn } from "node:child_process";
import process from "node:process";
import { setTimeout } from "node:timers";
import { URL } from "node:url";

const children = [];
let stopping = false;

function start(command, args) {
  const child = spawn(command, args, {
    cwd: new URL("..", import.meta.url),
    env: process.env,
    stdio: "inherit",
    shell: false,
  });
  children.push(child);
  child.once("exit", (code, signal) => {
    if (!stopping) {
      stop(code ?? (signal ? 1 : 0));
    }
  });
}

function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  for (const child of children) {
    if (!child.killed) child.kill("SIGTERM");
  }
  setTimeout(() => process.exit(code), 50).unref();
}

process.on("SIGINT", () => stop(0));
process.on("SIGTERM", () => stop(0));

start(process.execPath, ["server/index.mjs"]);
start("npx", ["vite"]);
