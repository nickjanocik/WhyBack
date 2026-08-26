export const MIN_DEMO_CUSTOMERS = 5;
export const MAX_DEMO_CUSTOMERS = 24;
export const MAX_LIVE_TRACE_EVENTS = 5_000;

export const DEMO_CUSTOMER_LIMITS = Object.freeze({
  minimum: MIN_DEMO_CUSTOMERS,
  maximum: MAX_DEMO_CUSTOMERS,
});

export function demoCustomerCountError(customers) {
  return Number.isInteger(customers) &&
    customers >= MIN_DEMO_CUSTOMERS &&
    customers <= MAX_DEMO_CUSTOMERS
    ? null
    : `customers must be an integer from ${MIN_DEMO_CUSTOMERS} through ${MAX_DEMO_CUSTOMERS}.`;
}
