interface ErrorStateProps {
  message: string;
}

export function ErrorState({ message }: ErrorStateProps) {
  return (
    <div className="status-card error-state" role="alert">
      <span className="error-icon" aria-hidden="true">!</span>
      <div>
        <strong>Planning could not be completed</strong>
        <p>{message}</p>
      </div>
    </div>
  );
}
