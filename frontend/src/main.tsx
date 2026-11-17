import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, HashRouter } from "react-router-dom";
import { IS_STATIC } from "./api";
import { App } from "./App";
import "./styles.css";

// GitHub Pages has no SPA fallback, so deep links like /e/<id> would 404 on refresh.
// The static demo uses hash URLs (#/e/<id>); the live app keeps clean paths.
const Router = IS_STATIC ? HashRouter : BrowserRouter;

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Router>
      <App />
    </Router>
  </React.StrictMode>
);
