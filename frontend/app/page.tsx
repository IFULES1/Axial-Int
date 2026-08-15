"use client";

import dynamic from "next/dynamic";

// The whole prototype is a self-contained SPA (internal routing). It touches
// window/localStorage at load, so we render it client-side only.
const App = dynamic(() => import("./_prototype/App"), {
  ssr: false,
  loading: () => <div style={{ minHeight: "100vh", background: "var(--bg, #07050f)" }} />,
});

export default function Page() {
  return <App />;
}
