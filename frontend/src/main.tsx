import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./i18n";
import "./fonts";
import "./index.css";
import { APP_NAME } from "./config";
import App from "./App";

document.title = APP_NAME;

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
