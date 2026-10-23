import { Component, type ReactNode } from "react";

type Props = { children: ReactNode; label?: string };
type State = { error: string | null };

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error: error.message };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="card p-4 text-sm text-red-500" role="alert">
          {this.props.label || "This card"} failed: {this.state.error}
        </div>
      );
    }
    return this.props.children;
  }
}
