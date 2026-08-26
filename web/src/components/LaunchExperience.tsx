/** Presents the stakeholder-friendly choice between prior work and a new analysis. */

import {
  ArrowLeft,
  ArrowRight,
  CalendarDays,
  CheckCircle2,
  History,
  Play,
  ShieldCheck,
  Sparkles,
  UsersRound,
} from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useCallback, useEffect, useRef } from "react";

import { productMessage } from "../lib/report";
import type { ArtifactCollection } from "../types";

export type LaunchView = "welcome" | "history";

interface LaunchExperienceProps {
  view: LaunchView;
  collections: ArtifactCollection[];
  collectionWarnings: string[];
  analysisReady: boolean;
  analysisBlockedReason: string | null;
  onShowHistory: () => void;
  onBack: () => void;
  onSelectCollection: (collectionId: string) => void;
  onStartAnalysis: () => void;
}

/** Renders the two-path welcome view and its accessible past-workflow chooser. */
export function LaunchExperience({
  view,
  collections,
  collectionWarnings,
  analysisReady,
  analysisBlockedReason,
  onShowHistory,
  onBack,
  onSelectCollection,
  onStartAnalysis,
}: LaunchExperienceProps) {
  const reduceMotion = useReducedMotion();
  const historyHeadingRef = useRef<HTMLHeadingElement>(null);
  const historyActionRef = useRef<HTMLButtonElement>(null);
  const previousViewRef = useRef<LaunchView>(view);
  const pendingFocusRef = useRef<LaunchView | null>(null);

  /** Captures the delayed history heading and completes focus after its transition. */
  const captureHistoryHeading = useCallback((node: HTMLHeadingElement | null) => {
    historyHeadingRef.current = node;
    if (node && pendingFocusRef.current === "history") {
      pendingFocusRef.current = null;
      node.focus();
    }
  }, []);

  /** Captures the returning welcome action and restores focus after its transition. */
  const captureHistoryAction = useCallback((node: HTMLButtonElement | null) => {
    historyActionRef.current = node;
    if (node && pendingFocusRef.current === "welcome") {
      pendingFocusRef.current = null;
      node.focus();
    }
  }, []);

  useEffect(() => {
    const previousView = previousViewRef.current;
    previousViewRef.current = view;
    if (previousView === view) return;
    pendingFocusRef.current = view;
    if (view === "history" && historyHeadingRef.current) {
      pendingFocusRef.current = null;
      historyHeadingRef.current.focus();
    } else if (view === "welcome" && historyActionRef.current) {
      pendingFocusRef.current = null;
      historyActionRef.current.focus();
    }
  }, [view]);

  const transition = { duration: reduceMotion ? 0 : 0.28, ease: "easeOut" as const };

  return (
    <AnimatePresence mode="wait" initial={false}>
      {view === "welcome" ? (
        <motion.section
          className="launch-experience"
          key="welcome"
          data-motion={reduceMotion ? "reduced" : "full"}
          aria-labelledby="launch-title"
          initial={reduceMotion ? false : { opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={reduceMotion ? { opacity: 0 } : { opacity: 0, y: -8 }}
          transition={transition}
        >
          <div className="launch-experience__visual" aria-hidden="true">
            <span className="launch-experience__halo launch-experience__halo--outer" />
            <span className="launch-experience__halo launch-experience__halo--inner" />
            <span className="launch-experience__core"><Sparkles size={27} /></span>
            <i className="launch-experience__signal launch-experience__signal--one" />
            <i className="launch-experience__signal launch-experience__signal--two" />
            <i className="launch-experience__signal launch-experience__signal--three" />
          </div>

          <div className="launch-experience__intro">
            <span className="eyebrow">Population intelligence</span>
            <h1 id="launch-title">Where would you like to begin?</h1>
            <p>
              Continue from verified household insights or begin a fresh population
              analysis. Every result stays traceable to recorded evidence.
            </p>
          </div>

          <div className="launch-experience__actions" aria-label="Choose how to begin">
            <motion.button
              ref={captureHistoryAction}
              className="launch-choice launch-choice--history"
              type="button"
              aria-label="View past workflows"
              aria-describedby="past-workflows-choice-detail"
              onClick={onShowHistory}
              whileHover={reduceMotion ? undefined : { y: -4 }}
              whileTap={reduceMotion ? undefined : { scale: 0.99 }}
            >
              <span className="launch-choice__icon"><History size={22} /></span>
              <span className="launch-choice__copy">
                <strong>View past workflows</strong>
                <small id="past-workflows-choice-detail">
                  {collections.length > 0
                    ? `Choose from ${collections.length} verified ${collections.length === 1 ? "analysis" : "analyses"}`
                    : "Review previously completed analyses"}
                </small>
              </span>
              <ArrowRight className="launch-choice__arrow" size={20} />
            </motion.button>

            <motion.button
              className="launch-choice launch-choice--new"
              type="button"
              aria-label="Start a new analysis"
              aria-describedby="new-analysis-choice-detail"
              onClick={onStartAnalysis}
              disabled={!analysisReady}
              whileHover={reduceMotion || !analysisReady ? undefined : { y: -4 }}
              whileTap={reduceMotion || !analysisReady ? undefined : { scale: 0.99 }}
            >
              <span className="launch-choice__icon"><Play size={22} /></span>
              <span className="launch-choice__copy">
                <strong>Start a new analysis</strong>
                <small id="new-analysis-choice-detail">
                  Configure and investigate a new household cohort
                </small>
              </span>
              <ArrowRight className="launch-choice__arrow" size={20} />
            </motion.button>
          </div>

          {!analysisReady && (
            <p className="launch-experience__availability" role="status">
              {analysisBlockedReason
                ? productMessage(analysisBlockedReason, "New analysis is temporarily unavailable.")
                : "New analysis is temporarily unavailable."}
            </p>
          )}

          <div className="launch-experience__assurance">
            <span><ShieldCheck size={14} /> Verified results</span>
            <span><CheckCircle2 size={14} /> Governed recommendations</span>
            <span><UsersRound size={14} /> Population context</span>
          </div>
        </motion.section>
      ) : (
        <motion.section
          className="workflow-library"
          key="history"
          data-motion={reduceMotion ? "reduced" : "full"}
          aria-labelledby="workflow-library-title"
          initial={reduceMotion ? false : { opacity: 0, x: 14 }}
          animate={{ opacity: 1, x: 0 }}
          exit={reduceMotion ? { opacity: 0 } : { opacity: 0, x: -14 }}
          transition={transition}
        >
          <button className="workflow-library__back" type="button" onClick={onBack}>
            <ArrowLeft size={16} /> Back
          </button>

          <div className="workflow-library__heading">
            <span className="eyebrow">Analysis history</span>
            <h1 id="workflow-library-title" ref={captureHistoryHeading} tabIndex={-1}>
              Past workflows
            </h1>
            <p>Select a verified workflow to reopen its executive summary and household insights.</p>
          </div>

          {collectionWarnings.length > 0 && (
            <div className="workflow-library__warning" role="status">
              Some analysis history is temporarily unavailable. The workflows below
              are ready to review.
            </div>
          )}

          {collections.length > 0 ? (
            <ul className="workflow-library__list" aria-label="Past workflows">
              {collections.map((collection, index) => (
                <motion.li
                  key={collection.id}
                  initial={reduceMotion ? false : { opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{
                    duration: reduceMotion ? 0 : 0.22,
                    delay: reduceMotion ? 0 : index * 0.045,
                  }}
                >
                  <button
                    className="workflow-card"
                    type="button"
                    onClick={() => onSelectCollection(collection.id)}
                    aria-label={`Open ${workflowName(collection, index)}. ${workflowCoverage(collection).label}. ${collection.completedCount} of ${collection.reportCount} completed.`}
                  >
                    <span className="workflow-card__badges">
                      <span className="workflow-card__status" aria-label="Verified workflow">
                        <CheckCircle2 size={16} /> Verified
                      </span>
                      <span className={`workflow-card__coverage workflow-card__coverage--${workflowCoverage(collection).kind}`}>
                        {workflowCoverage(collection).label}
                      </span>
                    </span>
                    <span className="workflow-card__title">{workflowName(collection, index)}</span>
                    <span className="workflow-card__meta">
                      <span><CalendarDays size={14} /> {workflowDate(collection)}</span>
                      <span><UsersRound size={14} /> {collection.reportCount} household {collection.reportCount === 1 ? "investigation" : "investigations"}</span>
                      <span><CheckCircle2 size={14} /> {collection.completedCount} of {collection.reportCount} completed</span>
                    </span>
                    <span className="workflow-card__open">Open workflow <ArrowRight size={16} /></span>
                  </button>
                </motion.li>
              ))}
            </ul>
          ) : (
            <div className="workflow-library__empty">
              <History size={25} />
              <strong>No past workflows yet</strong>
              <p>Return to the welcome screen to start your first population analysis.</p>
            </div>
          )}
        </motion.section>
      )}
    </AnimatePresence>
  );
}

/** Produces a stakeholder-friendly workflow name without exposing internal IDs. */
function workflowName(collection: ArtifactCollection, index: number): string {
  const date = latestGeneratedAt(collection);
  const sequence = String(index + 1).padStart(2, "0");
  if (!date) return `Population analysis ${sequence}`;
  return `Population analysis ${sequence} · ${new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date)}`;
}

/** Formats the latest report timestamp as a compact local date and time. */
function workflowDate(collection: ArtifactCollection): string {
  const date = latestGeneratedAt(collection);
  if (!date) return "Date unavailable";
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

/** Converts the aggregate-artifact availability into an honest, readable coverage cue. */
function workflowCoverage(collection: ArtifactCollection): {
  kind: "full" | "partial" | "unavailable";
  label: string;
} {
  if (collection.populationAvailability === "full") {
    return { kind: "full", label: "Full population view" };
  }
  if (collection.populationAvailability === "unavailable") {
    return { kind: "unavailable", label: "Population view unavailable" };
  }
  return { kind: "partial", label: "Limited population view" };
}

/** Finds the latest valid generated timestamp in one workflow. */
function latestGeneratedAt(collection: ArtifactCollection): Date | null {
  const timestamps = collection.reports
    .map((report) => Date.parse(report.generatedAt))
    .filter(Number.isFinite);
  if (timestamps.length === 0) return null;
  return new Date(Math.max(...timestamps));
}
