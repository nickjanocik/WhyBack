interface BrandMarkProps {
  compact?: boolean;
}

export function BrandMark({ compact = false }: BrandMarkProps) {
  return (
    <div className="brand" aria-label="WhyBack">
      <svg className="brand__mark" viewBox="0 0 42 42" role="img" aria-hidden="true">
        <circle cx="21" cy="21" r="19" fill="currentColor" />
        <path
          d="M11.5 14.5 17 29l4-9.6L25 29l5.5-14.5"
          fill="none"
          stroke="var(--paper)"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="3.2"
        />
        <path
          d="m26.5 12.5 4-1-1 4"
          fill="none"
          stroke="var(--accent)"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="2.4"
        />
      </svg>
      {!compact && (
        <span className="brand__type">
          Why<span>Back</span>
        </span>
      )}
    </div>
  );
}
