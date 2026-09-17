import React from 'react';

export type ReactorState = 'IDLE' | 'ANALYZING' | 'THINKING' | 'ALERT';

interface ReactorCoreProps {
  state?: ReactorState;
  size?: number;
  className?: string;
  subtext?: string;
}

export const ReactorCore: React.FC<ReactorCoreProps> = ({
  state = 'IDLE',
  size = 140,
  className = '',
  subtext,
}) => {
  // Determine animation timing and primary glow colors by state
  const isThinking = state === 'THINKING';
  const isAnalyzing = state === 'ANALYZING';
  const isAlert = state === 'ALERT';

  const outerSpeed = isAnalyzing ? '8s' : isThinking ? '12s' : isAlert ? '6s' : '26s';
  const innerSpeed = isAnalyzing ? '5s' : isThinking ? '7s' : isAlert ? '4s' : '18s';
  const nucleusPulseSpeed = isThinking ? '1s' : isAlert ? '0.7s' : isAnalyzing ? '1.4s' : '3s';

  const primaryCoreColor = isAlert ? '#EF4444' : isThinking ? '#FFB400' : isAnalyzing ? '#F0A422' : '#FFB400';
  const secondaryColor = isAlert ? '#DC2626' : '#FF8A00';
  const glowColor = isAlert ? 'rgba(239, 68, 68, 0.45)' : 'rgba(255, 180, 0, 0.35)';

  return (
    <div 
      className={`reactor-core-container ${className}`}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        userSelect: 'none',
        position: 'relative'
      }}
    >
      <svg
        width={size}
        height={size}
        viewBox="0 0 200 200"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        style={{ overflow: 'visible' }}
      >
        <defs>
          {/* Reactor Radial Glow */}
          <radialGradient id="reactor-core-glow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor={primaryCoreColor} stopOpacity="0.85" />
            <stop offset="45%" stopColor={secondaryColor} stopOpacity="0.35" />
            <stop offset="100%" stopColor="#0B0D10" stopOpacity="0" />
          </radialGradient>

          <filter id="core-bloom" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* DEPTH PLANE 1: Background Static Radar & Crosshairs */}
        <circle cx="100" cy="100" r="94" stroke="rgba(232, 235, 239, 0.05)" strokeWidth="1" />
        <circle cx="100" cy="100" r="82" stroke="rgba(232, 235, 239, 0.04)" strokeWidth="1" strokeDasharray="2 6" />
        
        {/* Cardinal crosshairs */}
        <line x1="100" y1="4" x2="100" y2="16" stroke="rgba(232, 235, 239, 0.25)" strokeWidth="1" />
        <line x1="100" y1="184" x2="100" y2="196" stroke="rgba(232, 235, 239, 0.25)" strokeWidth="1" />
        <line x1="4" y1="100" x2="16" y2="100" stroke="rgba(232, 235, 239, 0.25)" strokeWidth="1" />
        <line x1="184" y1="100" x2="196" y2="100" stroke="rgba(232, 235, 239, 0.25)" strokeWidth="1" />

        {/* 45 degree technical ticks */}
        <circle cx="100" cy="100" r="70" stroke="rgba(232, 235, 239, 0.08)" strokeWidth="1" strokeDasharray="1 15" />

        {/* DEPTH PLANE 2: Outer Orbital Ring with Satellite Trackers */}
        <g style={{ transformOrigin: '100px 100px', animation: `gyro-rotate ${outerSpeed} linear infinite` }}>
          <circle
            cx="100"
            cy="100"
            r="64"
            stroke="rgba(232, 235, 239, 0.16)"
            strokeWidth="1.2"
            strokeDasharray="40 18 20 18"
          />
          <circle
            cx="100"
            cy="100"
            r="64"
            stroke={primaryCoreColor}
            strokeWidth="2"
            strokeDasharray="28 200"
            strokeDashoffset="10"
            style={{ filter: `drop-shadow(0 0 4px ${glowColor})` }}
          />

          <circle cx="100" cy="36" r="3" fill={primaryCoreColor} style={{ filter: `drop-shadow(0 0 3px ${glowColor})` }} />
          <circle cx="155" cy="132" r="2.2" fill="rgba(232, 235, 239, 0.6)" />
          <circle cx="45" cy="132" r="2.2" fill="rgba(232, 235, 239, 0.6)" />
        </g>

        {/* DEPTH PLANE 3: Inner Mechanical Shutters & Gimbal Rings */}
        <g style={{ transformOrigin: '100px 100px', animation: `gyro-counter ${innerSpeed} linear infinite` }}>
          <circle
            cx="100"
            cy="100"
            r="48"
            stroke="rgba(232, 235, 239, 0.14)"
            strokeWidth="1.5"
            strokeDasharray="12 8"
          />
          <path d="M100 52 L100 58" stroke={secondaryColor} strokeWidth="2" />
          <path d="M100 142 L100 148" stroke={secondaryColor} strokeWidth="2" />
          <path d="M52 100 L58 100" stroke={secondaryColor} strokeWidth="2" />
          <path d="M142 100 L148 100" stroke={secondaryColor} strokeWidth="2" />
        </g>

        {/* Tilted 35° elliptical gimbal ring */}
        <g style={{ transformOrigin: '100px 100px', transform: 'rotate(35deg)' }}>
          <ellipse
            cx="100"
            cy="100"
            rx="52"
            ry="24"
            stroke={primaryCoreColor}
            strokeWidth="1.2"
            strokeOpacity="0.4"
            strokeDasharray="8 6"
          />
        </g>

        {/* DEPTH PLANE 4: Central Nucleus & Amber Core Bead */}
        <circle cx="100" cy="100" r="32" fill="url(#reactor-core-glow)" />

        <circle
          cx="100"
          cy="100"
          r="26"
          stroke={primaryCoreColor}
          strokeWidth="1.5"
          strokeDasharray="4 2"
          strokeOpacity="0.75"
        />

        <g style={{
          transformOrigin: '100px 100px',
          animation: `nucleus-pulse ${nucleusPulseSpeed} ease-in-out infinite`
        }}>
          <circle
            cx="100"
            cy="100"
            r="12"
            fill={primaryCoreColor}
            filter="url(#core-bloom)"
          />
          <circle
            cx="100"
            cy="100"
            r="6"
            fill="#FFFFFF"
            opacity="0.85"
          />
        </g>
      </svg>

      {subtext && (
        <div style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: '9.5px',
          letterSpacing: '0.08em',
          color: isAlert ? '#EF4444' : 'var(--ink-secondary, #98A1AE)',
          marginTop: '6px',
          display: 'flex',
          alignItems: 'center',
          gap: '6px'
        }}>
          <span 
            className="status-dot"
            style={{
              backgroundColor: primaryCoreColor,
              boxShadow: `0 0 6px ${glowColor}`
            }}
          />
          {subtext}
        </div>
      )}
    </div>
  );
};
