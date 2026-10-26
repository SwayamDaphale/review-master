import React from 'react';

export function Loading({ message = 'Loading evaluation data...' }: { message?: string }) {
  return (
    <div className="state-box loading-box">
      <div className="spinner" aria-hidden="true" />
      <p className="muted small">{message}</p>
    </div>
  );
}
