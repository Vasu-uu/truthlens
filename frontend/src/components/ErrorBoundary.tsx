import { Component, type ErrorInfo, type ReactNode } from "react";

interface State {
  failed: boolean;
}

/** Keeps a rendering bug from blanking the whole app. */
export default class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  override state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  override componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("UI error:", error.message, info.componentStack);
  }

  override render(): ReactNode {
    if (!this.state.failed) return this.props.children;
    return (
      <div role="alert" className="rounded-2xl border border-red-400/50 bg-red-950/60 p-5 text-sm text-red-100">
        <p className="font-bold">Something went wrong showing this page.</p>
        <button className="mt-3 rounded-lg bg-red-200 px-4 py-2 font-semibold text-red-950" onClick={() => this.setState({ failed: false })}>
          Try again
        </button>
      </div>
    );
  }
}
