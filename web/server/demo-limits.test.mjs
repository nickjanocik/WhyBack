/** Verifies that the browser and server publish the same live-batch boundaries. */

import assert from "node:assert/strict";
import test from "node:test";

import {
  DEMO_CUSTOMER_LIMITS,
  DEFAULT_DEMO_CUSTOMERS,
  DEFAULT_DEMO_DECLINE_THRESHOLD,
  DEMO_DECLINE_THRESHOLDS,
  MAX_DEMO_CUSTOMERS,
  MAX_LIVE_TRACE_EVENTS,
  MIN_DEMO_CUSTOMERS,
  demoCustomerCountError,
  demoDeclineThresholdError,
} from "./demo-limits.mjs";

test("publishes the supported inclusive demo customer range", () => {
  assert.equal(MIN_DEMO_CUSTOMERS, 3);
  assert.equal(DEFAULT_DEMO_CUSTOMERS, 5);
  assert.equal(MAX_DEMO_CUSTOMERS, 24);
  assert.equal(MAX_LIVE_TRACE_EVENTS, 5_000);
  assert.deepEqual(DEMO_CUSTOMER_LIMITS, { minimum: 3, maximum: 24 });
  assert.equal(demoCustomerCountError(3), null);
  assert.equal(demoCustomerCountError(4), null);
  assert.equal(demoCustomerCountError(5), null);
  assert.equal(demoCustomerCountError(24), null);
});

test("publishes exactly three supported decline thresholds", () => {
  assert.equal(DEFAULT_DEMO_DECLINE_THRESHOLD, 0.3);
  assert.deepEqual(DEMO_DECLINE_THRESHOLDS, [0.2, 0.3, 0.4]);
  for (const threshold of DEMO_DECLINE_THRESHOLDS) {
    assert.equal(demoDeclineThresholdError(threshold), null);
  }
});

test("rejects demo customer counts outside the range or not integers", () => {
  const expected = "customers must be an integer from 3 through 24.";

  assert.equal(demoCustomerCountError(2), expected);
  assert.equal(demoCustomerCountError(25), expected);
  assert.equal(demoCustomerCountError(5.5), expected);
});

test("rejects decline thresholds outside the declared choices", () => {
  const expected = "declineThreshold must be one of 0.2, 0.3, or 0.4.";

  assert.equal(demoDeclineThresholdError(0.25), expected);
  assert.equal(demoDeclineThresholdError("0.3"), expected);
  assert.equal(demoDeclineThresholdError(null), expected);
});
