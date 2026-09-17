import React from 'react';
import { GittyLogo } from '../common/GittyLogo';
import type { User, Repository } from '../../types';
import { 
  User as UserIcon, 
  LogIn, 
  LogOut, 
  Terminal, 
  Share2, 
  ShieldAlert, 
  Cpu, 
  Layers
} from 'lucide-react';

export type NavTab = 'REPOSITORY' | 'GRAPH' | 'SECURITY' | 'ARCHITECTURE';

interface TopNavProps {
  activeTab: NavTab;
  onSelectTab: (tab: NavTab) => void;
  selectedRepo: Repository | null;
  user: User | null;
  onOpenAuth: () => void;
  onLogout: () => void;
  systemStatus?: string;
}

export const TopNav: React.FC<TopNavProps> = ({
  activeTab,
  onSelectTab,
  selectedRepo,
  user,
  onOpenAuth,
  onLogout,
  systemStatus = 'ONLINE'
}) => {
  const tabs: { id: NavTab; label: string; icon: React.ReactNode }[] = [
    { id: 'GRAPH', label: 'GRAPH MATRIX', icon: <Share2 size={13} /> },
    { id: 'REPOSITORY', label: 'REPOSITORY', icon: <Layers size={13} /> },
    { id: 'SECURITY', label: 'SECURITY HUD', icon: <ShieldAlert size={13} /> },
    { id: 'ARCHITECTURE', label: 'ARCHITECTURE', icon: <Cpu size={13} /> },
  ];

  return (
    <header style={{
      height: '54px',
      background: 'var(--bg-panel)',
      borderBottom: '1px solid var(--hairline)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 16px',
      userSelect: 'none',
      zIndex: 50,
      flexShrink: 0
    }}>
      {/* Left: Brand Identity & Active Repository Badge */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <GittyLogo height={28} />

        <div style={{ 
          height: '20px', 
          width: '1px', 
          background: 'var(--hairline)' 
        }} />

        {selectedRepo ? (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            background: 'var(--bg-ground)',
            border: '1px solid var(--hairline)',
            padding: '4px 10px',
            borderRadius: '4px',
            fontFamily: 'var(--font-mono)',
            fontSize: '11px'
          }}>
            <Terminal size={12} style={{ color: 'var(--accent-amber)' }} />
            <span style={{ color: 'var(--ink-muted)' }}>TARGET:</span>
            <span style={{ color: 'var(--ink-primary)', fontWeight: 600 }}>{selectedRepo.name}</span>
          </div>
        ) : (
          <div style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '10.5px',
            color: 'var(--ink-muted)'
          }}>
            NO TARGET REPOSITORY
          </div>
        )}
      </div>

      {/* Middle: Technical Console Tabs */}
      <nav style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
        {tabs.map(tab => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => onSelectTab(tab.id)}
              style={{
                background: isActive ? 'var(--bg-hover)' : 'transparent',
                border: '1px solid',
                borderColor: isActive ? 'var(--accent-amber)' : 'transparent',
                color: isActive ? 'var(--accent-amber-bright)' : 'var(--ink-secondary)',
                padding: '6px 14px',
                borderRadius: '4px',
                cursor: 'pointer',
                fontFamily: 'var(--font-mono)',
                fontSize: '11px',
                letterSpacing: '0.06em',
                fontWeight: isActive ? 600 : 500,
                display: 'inline-flex',
                alignItems: 'center',
                gap: '7px',
                transition: 'all 0.15s ease'
              }}
              onMouseEnter={(e) => {
                if (!isActive) {
                  e.currentTarget.style.color = 'var(--ink-primary)';
                  e.currentTarget.style.background = 'rgba(232, 235, 239, 0.04)';
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  e.currentTarget.style.color = 'var(--ink-secondary)';
                  e.currentTarget.style.background = 'transparent';
                }
              }}
            >
              {tab.icon}
              {tab.label}
            </button>
          );
        })}
      </nav>

      {/* Right: Telemetry Status & Authentication */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
        {/* System Online Badge (Status Green Strictly for System State) */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          background: 'rgba(61, 220, 151, 0.08)',
          border: '1px solid rgba(61, 220, 151, 0.25)',
          padding: '4px 8px',
          borderRadius: '4px',
          fontFamily: 'var(--font-mono)',
          fontSize: '10px',
          fontWeight: 600,
          letterSpacing: '0.08em',
          color: 'var(--status-green)'
        }}>
          <span className="status-dot status-dot-green" />
          {systemStatus}
        </div>

        {/* User Account / Sign In */}
        {user ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontFamily: 'var(--font-mono)',
              fontSize: '11px',
              color: 'var(--ink-secondary)',
              background: 'var(--bg-ground)',
              border: '1px solid var(--hairline)',
              padding: '4px 10px',
              borderRadius: '4px'
            }}>
              <UserIcon size={12} style={{ color: 'var(--accent-amber)' }} />
              <span>{user.username}</span>
            </div>
            <button
              onClick={onLogout}
              title="Sign Out"
              className="console-btn"
              style={{ padding: '5px 8px' }}
            >
              <LogOut size={13} />
            </button>
          </div>
        ) : (
          <button
            onClick={onOpenAuth}
            className="console-btn"
            style={{
              borderColor: 'rgba(240, 164, 34, 0.4)',
              color: 'var(--accent-amber-bright)'
            }}
          >
            <LogIn size={13} />
            AUTHENTICATE
          </button>
        )}
      </div>
    </header>
  );
};
