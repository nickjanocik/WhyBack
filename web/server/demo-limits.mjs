/** Shares the bounded live-batch sizes and trace capacity across the web bridge. */

export const MIN_DEMO_CUSTOMERS = 3;
export const DEFAULT_DEMO_CUSTOMERS = 5;
export const MAX_DEMO_CUSTOMERS = 24;
export const DEMO_DECLINE_THRESHOLDS = Object.freeze([0.2, 0.3, 0.4]);
export const DEFAULT_DEMO_DECLINE_THRESHOLD = 0.3;
export const MAX_LIVE_TRACE_EVENTS = 5_000;

export const DEMO_CUSTOMER_LIMITS = Object.freeze({
  minimum: MIN_DEMO_CUSTOMERS,
  maximum: MAX_DEMO_CUSTOMERS,
});

/** Returns a public validation message when a requested batch size is unsupported. */
export function demoCustomerCountError(customers) {
  return Number.isInteger(customers) &&
    customers >= MIN_DEMO_CUSTOMERS &&
    customers <= MAX_DEMO_CUSTOMERS
    ? null
    : `customers must be an integer from ${MIN_DEMO_CUSTOMERS} through ${MAX_DEMO_CUSTOMERS}.`;
}

/** Returns a public validation message for detector thresholds outside the UI choices. */
export function demoDeclineThresholdError(declineThreshold) {
  return DEMO_DECLINE_THRESHOLDS.includes(declineThreshold)
    ? null
    : "declineThreshold must be one of 0.2, 0.3, or 0.4.";
}
