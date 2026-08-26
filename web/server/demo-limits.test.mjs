import assert from "node:assert/strict";
import test from "node:test";

import {
  DEMO_CUSTOMER_LIMITS,
  MAX_DEMO_CUSTOMERS,
  MAX_LIVE_TRACE_EVENTS,
  MIN_DEMO_CUSTOMERS,
  demoCustomerCountError,
} from "./demo-limits.mjs";

test("publishes the supported inclusive demo customer range", () => {
  assert.equal(MIN_DEMO_CUSTOMERS, 5);
  assert.equal(MAX_DEMO_CUSTOMERS, 24);
  assert.equal(MAX_LIVE_TRACE_EVENTS, 5_000);
  assert.deepEqual(DEMO_CUSTOMER_LIMITS, { minimum: 5, maximum: 24 });
  assert.equal(demoCustomerCountError(5), null);
  assert.equal(demoCustomerCountError(24), null);
});

test("rejects demo customer counts outside the range or not integers", () => {
  const expected = "customers must be an integer from 5 through 24.";

  assert.equal(demoCustomerCountError(4), expected);
  assert.equal(demoCustomerCountError(25), expected);
  assert.equal(demoCustomerCountError(5.5), expected);
});
