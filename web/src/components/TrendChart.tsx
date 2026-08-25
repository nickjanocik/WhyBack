import { motion, useReducedMotion } from "motion/react";
import { useId, useMemo, useRef, useState } from "react";

import { formatCurrency } from "../lib/report";
import type { TrendPoint } from "../lib/report";

interface TrendChartProps {
  points: TrendPoint[];
  recentStartWeek: number;
}

const WIDTH = 760;
const HEIGHT = 252;
const PADDING = { top: 18, right: 20, bottom: 34, left: 48 };

export function TrendChart({ points, recentStartWeek }: TrendChartProps) {
  const reduceMotion = useReducedMotion();
  const gradientId = useId().replaceAll(":", "");
  const titleId = `${gradientId}-title`;
  const svgRef = useRef<SVGSVGElement>(null);
  const [hovered, setHovered] = useState<number | null>(null);
  const geometry = useMemo(() => buildGeometry(points), [points]);

  if (points.length < 2 || !geometry) {
    return (
      <div className="chart-empty">
        <span>No weekly series was produced in this bounded run.</span>
      </div>
    );
  }

  const recentX = geometry.xFor(recentStartWeek);
  const hoveredPoint = hovered === null ? null : geometry.coordinates[hovered];
  const accessibleSummary = `Weekly retailer sales value. ${points
    .map((point) => `Week ${point.week}: ${formatCurrency(point.value)}`)
    .join("; ")}. The recent window begins at week ${recentStartWeek}.`;

  function handlePointerMove(event: React.PointerEvent<SVGSVGElement>) {
    const bounds = svgRef.current?.getBoundingClientRect();
    if (!bounds) return;
    const localX = ((event.clientX - bounds.left) / bounds.width) * WIDTH;
    const nearest = geometry?.coordinates.reduce(
      (best, point, index) =>
        Math.abs(point.x - localX) < best.distance
          ? { index, distance: Math.abs(point.x - localX) }
          : best,
      { index: 0, distance: Number.POSITIVE_INFINITY },
    );
    setHovered(nearest?.index ?? null);
  }

  return (
    <div className="trend-chart">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-labelledby={titleId}
        onPointerMove={handlePointerMove}
        onPointerLeave={() => setHovered(null)}
      >
        <title id={titleId}>{accessibleSummary}</title>
        <defs>
          <linearGradient id={gradientId} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="var(--chart)" stopOpacity=".27" />
            <stop offset="100%" stopColor="var(--chart)" stopOpacity="0" />
          </linearGradient>
        </defs>
        {geometry.ticks.map((tick) => (
          <g key={tick.value}>
            <line
              x1={PADDING.left}
              x2={WIDTH - PADDING.right}
              y1={tick.y}
              y2={tick.y}
              className="chart-grid"
            />
            <text x={PADDING.left - 9} y={tick.y + 4} className="chart-axis" textAnchor="end">
              {tick.value === 0 ? "$0" : `$${tick.value}`}
            </text>
          </g>
        ))}
        <line
          x1={recentX}
          x2={recentX}
          y1={PADDING.top}
          y2={HEIGHT - PADDING.bottom}
          className="period-divider"
        />
        <text x={PADDING.left} y={HEIGHT - 8} className="period-label">
          BASELINE
        </text>
        <text x={recentX + 10} y={HEIGHT - 8} className="period-label period-label--recent">
          RECENT
        </text>
        <motion.path
          d={geometry.areaPath}
          fill={`url(#${gradientId})`}
          initial={reduceMotion ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.7 }}
        />
        <motion.path
          d={geometry.linePath}
          className="trend-line"
          fill="none"
          initial={reduceMotion ? false : { pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 1.05, ease: [0.22, 1, 0.36, 1] }}
        />
        {hoveredPoint && (
          <g className="chart-hover">
            <line
              x1={hoveredPoint.x}
              x2={hoveredPoint.x}
              y1={PADDING.top}
              y2={HEIGHT - PADDING.bottom}
            />
            <circle cx={hoveredPoint.x} cy={hoveredPoint.y} r="5" />
          </g>
        )}
      </svg>
      {hoveredPoint && (
        <div
          className="chart-tooltip"
          style={{
            left: `${(hoveredPoint.x / WIDTH) * 100}%`,
            top: `${(hoveredPoint.y / HEIGHT) * 100}%`,
          }}
        >
          <small>Week {hoveredPoint.point.week}</small>
          <strong>{formatCurrency(hoveredPoint.point.value)}</strong>
        </div>
      )}
    </div>
  );
}

function buildGeometry(points: TrendPoint[]) {
  if (points.length < 2) return null;
  const minWeek = Math.min(...points.map((point) => point.week));
  const maxWeek = Math.max(...points.map((point) => point.week));
  const maxValue = Math.max(...points.map((point) => point.value), 1);
  const chartWidth = WIDTH - PADDING.left - PADDING.right;
  const chartHeight = HEIGHT - PADDING.top - PADDING.bottom;
  const xFor = (week: number) =>
    PADDING.left + ((week - minWeek) / Math.max(1, maxWeek - minWeek)) * chartWidth;
  const yFor = (value: number) => PADDING.top + (1 - value / maxValue) * chartHeight;
  const coordinates = points.map((point) => ({
    point,
    x: xFor(point.week),
    y: yFor(point.value),
  }));
  const linePath = coordinates
    .map((point, index) => `${index === 0 ? "M" : "L"}${point.x},${point.y}`)
    .join(" ");
  const floor = HEIGHT - PADDING.bottom;
  const areaPath = `${linePath} L${coordinates.at(-1)?.x},${floor} L${coordinates[0]?.x},${floor} Z`;
  const tickValues = [0, maxValue / 2, maxValue];
  return {
    coordinates,
    linePath,
    areaPath,
    xFor,
    ticks: tickValues.map((value) => ({
      value: Math.round(value),
      y: yFor(value),
    })),
  };
}
