import React from "react";

interface Props {
  children: React.ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="detail-status detail-error">
          <div className="error-icon">!</div>
          <p>レンダリングエラーが発生しました</p>
          <p style={{ fontSize: 13, color: "#94a3b8", marginTop: 8 }}>
            {this.state.error?.message}
          </p>
          <button
            className="btn btn-primary"
            style={{ marginTop: 16 }}
            onClick={() => this.setState({ hasError: false, error: null })}
          >
            再試行
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
