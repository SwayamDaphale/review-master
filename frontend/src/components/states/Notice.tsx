import React from 'react';

interface NoticeProps {
  children: React.ReactNode;
  tone?: 'info' | 'warn' | 'error' | 'success';
}

export function Notice({ children, tone = 'info' }: NoticeProps) {
  return (
    <div className={`notice notice--${tone}`} role="status">
      <div className="notice-icon">
        {tone === 'info' && 'ℹ'}
        {tone === 'warn' && '⚠'}
        {tone === 'error' && '✕'}
        {tone === 'success' && '✓'}
      </div>
      <div className="notice-content">{children}</div>
    </div>
  );
}
