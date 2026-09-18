import React from 'react';

interface GittyLogoProps {
  height?: number;
  className?: string;
  showSubtitle?: boolean;
}

export const GittyLogo: React.FC<GittyLogoProps> = ({ 
  height = 24, 
  className = '',
  showSubtitle = false 
}) => {
  return (
    <div 
      className={`gitty-brand-mark ${className}`}
      style={{ 
        display: 'inline-flex', 
        alignItems: 'center',
        gap: '9px',
        userSelect: 'none'
      }}
    >
      <img
        src="/gitty-title.png"
        alt="GITTY"
        style={{
          height: `${height}px`,
          width: 'auto',
          objectFit: 'contain',
          display: 'block',
          flexShrink: 0
        }}
        loading="eager"
      />
      <div style={{ display: 'inline-flex', flexDirection: 'column', gap: '2px' }}>
        <span 
          style={{
            fontFamily: "var(--font-heading, 'Space Grotesk', sans-serif)",
            fontSize: '15px',
            fontWeight: 700,
            letterSpacing: '0.08em',
            color: 'var(--ink-primary, #E8EBEF)',
            lineHeight: 1,
            whiteSpace: 'nowrap'
          }}
        >
          GITTY AI
        </span>
        {showSubtitle && (
          <span 
            style={{
              fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
              fontSize: '9px',
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              color: 'var(--ink-muted, #6B7481)',
              lineHeight: 1
            }}
          >
            REPOSITORY INTELLIGENCE
          </span>
        )}
      </div>
    </div>
  );
};

