import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles.css";

// React owns the single-page UI; Tauri supplies the desktop shell around it.
ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
