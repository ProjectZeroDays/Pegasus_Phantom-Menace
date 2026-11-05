import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

// Register the persistent daemon service worker so the PWA stays alive
// in the background even after the app is closed.
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("/sw.js")
      .then((reg) => {
        // Tell the SW to start the keepalive daemon
        if (reg.active) {
          reg.active.postMessage({ type: "KEEPALIVE_START" });
        }
        reg.addEventListener("updatefound", () => {
          const nw = reg.installing;
          if (nw) {
            nw.addEventListener("statechange", () => {
              if (nw.state === "activated") {
                nw.postMessage({ type: "KEEPALIVE_START" });
              }
            });
          }
        });
      })
      .catch((err) => console.warn("SW registration failed:", err));
  });

  // Keep the SW alive when the page is hidden (backgrounded)
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") {
      navigator.serviceWorker.ready.then((reg) => {
        if (reg.active) reg.active.postMessage({ type: "KEEPALIVE_START" });
        if ((reg as any).sync) {
      (reg as any).sync.register("pegasus-keepalive").catch(() => undefined);
    }
      });
    }
  });
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
