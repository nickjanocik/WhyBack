import assert from "node:assert/strict";
import test from "node:test";

import {
  createExclusiveGate,
  hostHeaderAllowed,
  mutationHeaderError,
} from "./index.mjs";

test("accepts same-origin JSON mutation requests", () => {
  assert.equal(
    mutationHeaderError({
      "content-type": "application/json; charset=utf-8",
      origin: "http://127.0.0.1:4173",
      "sec-fetch-site": "same-origin",
    }),
    null,
  );
});

test("rejects non-JSON and cross-site mutation requests", () => {
  assert.equal(
    mutationHeaderError({ "content-type": "text/plain" }),
    "Content-Type must be application/json.",
  );
  assert.equal(
    mutationHeaderError({
      "content-type": "application/json",
      origin: "https://malicious.example",
      "sec-fetch-site": "cross-site",
    }),
    "Cross-site requests are not allowed.",
  );
});

test("allows only localhost Host headers", () => {
  assert.equal(hostHeaderAllowed("127.0.0.1:4173"), true);
  assert.equal(hostHeaderAllowed("localhost:5163"), true);
  assert.equal(hostHeaderAllowed("malicious.example"), false);
  assert.equal(hostHeaderAllowed(undefined), false);
});

test("acquires the demo gate atomically", () => {
  const gate = createExclusiveGate();
  assert.equal(gate.tryAcquire(), true);
  assert.equal(gate.running, true);
  assert.equal(gate.tryAcquire(), false);
  gate.release();
  assert.equal(gate.tryAcquire(), true);
});
