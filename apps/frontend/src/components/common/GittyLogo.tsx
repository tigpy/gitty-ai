import React from 'react';
import logoSrc from '../../assets/gitty-ai-logo.jpeg';

interface GittyLogoProps {
  height?: number;
  className?: string;
  showSubtitle?: boolean;
}

export const GittyLogo: React.FC<GittyLogoProps> = ({ 
  height = 30, 
  className = '',
  showSubtitle = false 
}) => {
  return (
    <div 
      className={`gitty-brand-mark ${className}`}
      style={{ 
        display: 'inline-flex', 
        flexDirection: 'column',
        alignItems: 'flex-start',
        gap: '3px',
        userSelect: 'none'
      }}
    >
      <img
        src={logoSrc}
        alt="Gitty AI"
        style={{
          height: `${height}px`,
          width: 'auto',
          objectFit: 'contain',
          display: 'block'
        }}
        loading="eager"
      />
      {showSubtitle && (
        <span 
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: '9.5px',
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            color: 'var(--ink-muted, #6B7481)',
            paddingLeft: '2px',
            lineHeight: 1
          }}
        >
          REPOSITORY INTELLIGENCE
        </span>
      )}
    </div>
  );
};
