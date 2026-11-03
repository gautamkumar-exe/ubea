---
name: "Splunk-Inspired UEBA SOC"
description: "A high-density enterprise SOC monitoring and user entity behavior analytics design system inspired by Splunk Enterprise Security."
---

## Overview

The Splunk-Inspired UEBA SOC design system delivers an information-dense, high-clarity monitoring interface engineered for Security Operations Center analysts, threat hunters, and incident responders. Inspired by Splunk Enterprise Security, it prioritizes immediate signal identification through purposeful contrast, compact typographic scales, tabular data alignment, and strict severity color semantics.

The visual direction rejects frivolous decoration, soft rounded shapes, glowing neon blurs, and glassmorphism. Instead, it employs a deep charcoal and slate structure with crisp borders, razor-sharp status indicators, and tactical data density that allows analysts to triage thousands of behavioral anomalies, alerts, and user risk scores effortlessly.

## Colors

The color palette is built on deep charcoal foundations with targeted, high-visibility semantic accents. Splunk-inspired security orange acts as the primary focal accent, while cyan serves as a secondary technical accent for metrics and metadata. Severity colors strictly govern triaging: Critical (Red), High (Orange), Medium (Amber), Low (Cyan/Blue), and Resolved/Normal (Green).

```yaml
colors:
  primary: "#F58220"
  on-primary: "#0B0F14"
  secondary: "#00A3E0"
  on-secondary: "#0B0F14"
  critical: "#E53935"
  on-critical: "#101010"
  high: "#F58220"
  on-high: "#0B0F14"
  warning: "#F5A623"
  on-warning: "#0B0F14"
  medium: "#F5A623"
  on-medium: "#0B0F14"
  low: "#00A3E0"
  on-low: "#0B0F14"
  success: "#10B981"
  on-success: "#0B0F14"
  border: "#2A313D"
  border-light: "#374151"
  light:
    primary: "#D96814"
    on-primary: "#222222"
    surface: "#11161F"
    on-surface: "#E2E8F0"
  dark:
    primary: "#F58220"
    on-primary: "#0B0F14"
    surface: "#0B0F14"
    on-surface: "#F1F5F9"
    surface-card: "#151B24"
    on-surface-card: "#E2E8F0"
    surface-panel: "#1A222D"
    on-surface-panel: "#CBD5E1"
    surface-sidebar: "#0D1117"
    on-surface-sidebar: "#94A3B8"
```

## Typography

The typography leverages **Instrument Sans** for clean, compact interface labels, headings, and tabular copy, combined with **Source Code Pro** for raw timestamps, IP addresses, entity IDs, risk hashes, and forensic parameters.

```yaml
typography:
  display-lg:
    fontFamily: "Instrument Sans"
    fontSize: 28px
    fontWeight: 700
    lineHeight: 34px
    letterSpacing: -0.25px
  headline-lg:
    fontFamily: "Instrument Sans"
    fontSize: 22px
    fontWeight: 700
    lineHeight: 28px
    letterSpacing: -0.2px
  headline-md:
    fontFamily: "Instrument Sans"
    fontSize: 18px
    fontWeight: 600
    lineHeight: 24px
    letterSpacing: -0.1px
  headline-sm:
    fontFamily: "Instrument Sans"
    fontSize: 15px
    fontWeight: 600
    lineHeight: 20px
  title-md:
    fontFamily: "Instrument Sans"
    fontSize: 14px
    fontWeight: 600
    lineHeight: 18px
  body-md:
    fontFamily: "Instrument Sans"
    fontSize: 13px
    fontWeight: 400
    lineHeight: 18px
  body-sm:
    fontFamily: "Instrument Sans"
    fontSize: 12px
    fontWeight: 400
    lineHeight: 16px
  label-sm:
    fontFamily: "Instrument Sans"
    fontSize: 11px
    fontWeight: 600
    lineHeight: 14px
    letterSpacing: 0.25px
  code-sm:
    fontFamily: "Source Code Pro"
    fontSize: 12px
    fontWeight: 500
    lineHeight: 16px
  code-xs:
    fontFamily: "Source Code Pro"
    fontSize: 11px
    fontWeight: 500
    lineHeight: 14px
```

## Layout & Spacing

A structured, persistent three-tier shell provides rapid navigation and maximum analyst viewing area:
1. Collapsible Left Sidebar (240px expanded, 56px collapsed)
2. Top Global Navigation Bar (48px fixed height)
3. Responsive High-Density Content Workspace

```yaml
spacing:
  gutter-xs: 4px
  gutter-sm: 8px
  gutter-md: 12px
  gutter-lg: 16px
  gutter-xl: 20px
  section: 24px
  page-margin: 16px
```

## Elevation & Depth

No blurry drop shadows or heavy blur diffusion. Depth is created strictly through subtle tonal contrast: `#0D1117` for sidebar, `#0B0F14` for backdrop, `#151B24` for cards/tables, and `#1A222D` for hover states and modal surfaces. Crisp 1px borders in `#2A313D` frame all components, adhering to authentic SOC console ergonomics.

## Shapes

Corners are strictly minimal and utilitarian (2px to 4px) to retain an enterprise hardware/terminal aesthetic. Full pills are reserved only for compact severity status chips.

```yaml
rounded:
  sm: 2px
  DEFAULT: 4px
  md: 4px
  lg: 6px
  xl: 8px
  full: 9999px
```

## Motion & Micro-interaction

Micro-interactions are instantaneous (sub-100ms) with zero distracting bouncy spring curves. Data tables update cleanly, tooltips reveal instantly on 120ms hover, and modal overlays pop without delayed fade loops.

```yaml
motion:
  state-change:
    duration: 80ms
    delay: 0ms
    timingFunction: ease-out
  surface-enter:
    duration: 150ms
    delay: 0ms
    timingFunction: cubic-bezier(0, 0, 0.2, 1)
  surface-exit:
    duration: 100ms
    delay: 0ms
    timingFunction: cubic-bezier(0.4, 0, 1, 1)
```

## Voice & Content Strategy

SOC terminology is standardized, direct, and unambiguous:
- Severity levels: `Critical`, `High`, `Medium`, `Low`, `Informational`
- Investigation workflow states: `Open`, `In Progress`, `Resolved`, `Closed`
- Actions are explicit imperative verbs: `Rebuild Baseline`, `Submit Feedback`, `Export CSV`, `Acknowledge Alert`, `Investigate Entity`
- Monospace formatting is strictly required for IP addresses, User IDs, hashes, timestamps, and detection rule IDs
- Empty states explain reason and next troubleshooting step rather than blank screens

## Components

Component implementations live as individual HTML sticker sheet files in
`components/`. Each file contains the canonical, styled HTML components with
`<!-- COMPONENT: name -->` comment markers. Read each file before use.

- **Badge** → `@components/badge.html`: `badge-numeric`, `badge-dot`
- **Button** → `@components/button.html`: `button-primary`, `button-icon`, `button-with-icon`
- **Card** → `@components/card.html`: `card-elevated`, `card-interactive`, `card-interactive-2`
- **Table** → `@components/table.html`: `table-standard`, `table-selectable`
- **Tabs** → `@components/tabs.html`: `tabs-horizontal`, `tabs-with-icon`
