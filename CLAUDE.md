# CLAUDE.md — AI Agent Project

## Project Overview

This is an AI agent project built with assistance from Windsurf. Claude Code should treat this as a production-grade codebase requiring thorough review and improvement.

## Architecture Principles

- **Separation of concerns**: Each module handles a single responsibility
- **Error resilience**: All external calls (LLM APIs, databases, third-party services) must have retry logic and graceful degradation
- **Configuration over hardcoding**: Environment variables and config files for all tunable parameters
- **Logging**: Structured logging (JSON format preferred) at appropriate levels (DEBUG, INFO, WARN, ERROR)
- **Security first**: No credentials in code, no secrets in logs, validate all inputs

## Code Standards

- Write clean, self-documenting code with meaningful variable and function names
- Add docstrings/comments only where the "why" isn't obvious from the code
- Keep functions under 30 lines when possible
- Never refactor code unless explicitly asked
- Always run existing tests before and after changes
- Commit working state before major modifications

## Review Checklist

When reviewing this project, always check:

1. **Security**: Hardcoded secrets, exposed API keys, missing input validation, SQL injection, prompt injection vectors
2. **Error handling**: Unhandled exceptions, missing try/catch blocks, silent failures
3. **Performance**: Unnecessary API calls, missing caching, blocking operations that should be async
4. **Dependencies**: Outdated packages, unused imports, vulnerable dependencies
5. **Testing**: Missing test coverage, untested edge cases, brittle tests
6. **Documentation**: Missing README sections, undocumented environment variables, unclear setup steps
7. **Agent-specific**: Prompt engineering quality, token usage optimization, hallucination guardrails, context window management

## Dashboard — Cisco Design System Conventions

All UI/dashboard work MUST follow Cisco's visual identity and UX patterns.

### Color Palette

```
Primary Blue:        #049FD9
Dark Background:     #1A1A2E
Secondary Dark:      #0D274D
Surface Dark:        #1E2A3A
Card Background:     #243447
Sidebar:             #0D1B2A

Text Primary:        #FFFFFF
Text Secondary:      #A0AEC0
Text Muted:          #6B7B8D

Status Green (OK):   #6EBE4A
Status Yellow (Warn):#FFCC00
Status Red (Error):  #CF2030
Status Blue (Info):  #049FD9

Border/Divider:      #2D3E50
Hover State:         #1A3A5C
Selected State:      #0A4D7A
```

### Typography

- Font family: `'CiscoSans', 'Inter', 'Open Sans', -apple-system, sans-serif`
- Headings: Semi-bold (600), tracking -0.01em
- Body: Regular (400), 14px base, line-height 1.5
- Monospace (code/logs): `'JetBrains Mono', 'Fira Code', 'Consolas', monospace`
- Numbers/metrics: Tabular numerals (`font-variant-numeric: tabular-nums`)

### Layout Rules

- **Dark mode as default** — consistent with Cisco DNA Center, SecureX, XDR consoles
- **Sidebar navigation**: Fixed left, 240px width, dark (#0D1B2A), with icons + labels
- **Top header**: 56px height, project name/logo left, status indicators and user avatar right
- **Content area**: Max-width 1440px, padding 24px, gap between cards 16px
- **Cards**: Background #243447, border-radius 8px, padding 20px, subtle shadow `0 2px 8px rgba(0,0,0,0.3)`
- **Tables**: Header row in #0D274D, alternating row colors (#1E2A3A / #243447), horizontal dividers only
- **Charts**: Use Cisco blue palette gradients, grid lines in #2D3E50 at 20% opacity

### Component Patterns

- **Status indicators**: Filled circles (8px) with color-coded status (green/yellow/red)
- **Metric cards**: Large number (32px, semi-bold), label below (12px, muted text), trend arrow if applicable
- **Buttons primary**: Background #049FD9, white text, border-radius 4px, hover darken 10%
- **Buttons secondary**: Transparent, border 1px #049FD9, text #049FD9
- **Alerts/Toasts**: Left border 4px with status color, dark background, icon + message
- **Breadcrumbs**: Slash separated, muted color, current page in white
- **Tabs**: Underline style, 2px bottom border in #049FD9 for active tab

### Dashboard Sections

1. **Overview**: Agent status badge, uptime counter, key KPIs in metric cards (requests handled, success rate, avg latency, token consumption)
2. **Activity/Logs**: Real-time scrolling log with severity color coding, filterable by level, searchable, timestamp + source + message columns
3. **Performance**: Line charts for latency over time, bar charts for token usage by model, success/failure donut chart, response time percentiles (p50, p95, p99)
4. **Configuration**: Form-based parameter editor, grouped by category, save/reset buttons, change history
5. **Alerts**: Notification center, severity badges, acknowledgment workflow, configurable thresholds

### Responsive Behavior

- Sidebar collapses to icon-only (64px) below 1024px
- Cards stack vertically below 768px
- Tables become horizontally scrollable on mobile
- Charts resize proportionally

## Tech Stack Preferences

- **Frontend**: React + Tailwind CSS
- **Charts**: Recharts or Chart.js (with Cisco color theme applied)
- **Icons**: Lucide React
- **State management**: React hooks (useState, useReducer, useContext) — no Redux unless justified
- **API communication**: Fetch API or Axios with centralized error handling

## Git Workflow

- Commit messages: `type(scope): description` (conventional commits)
- Types: feat, fix, refactor, docs, test, chore, style, perf
- Always create a feature branch for dashboard work
- Never push directly to main

## Language

- Code: English (variables, functions, comments, documentation)
- UI labels: English (unless explicitly requested in Spanish)
- Claude Code conversation: Spanish preferred
