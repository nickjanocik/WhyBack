/** Mounts the WhyBack React application with accessibility-aware motion settings. */

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { MotionConfig } from "motion/react";

import App from "./App";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <MotionConfig reducedMotion="user">
      <App />
    </MotionConfig>
  </StrictMode>,
);
