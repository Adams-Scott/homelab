# Linen Lab
This theme was created using the 60%/30%/10% rule.

- **60% — Warm Linen White (#f7f6f2 family)**
  page backgrounds, cards, the main canvas. Warmer than pure white so it's easier on the eyes.
- **30% — Cool Slate (#d5d8e0 → #8d94aa)**
  sidebars, borders, input fields, muted text. The cool-vs-warm contrast gives depth without going dark.
- **10% — Cobalt Blue (#2354e6)**
  buttons, active states, links, progress bars. Punchy enough to guide attention without shouting.

``` css
/* ════════════════════════════════════════
   LINEN LAB — Homelab Theme (Light Mode)
   60/30/10 Rule
   ════════════════════════════════════════ */

/* 60% — Base (warm linen) */
--hl-base-50:  #f7f6f2;   /* page bg */
--hl-base-100: #eeece5;   /* hover rows, subtle bg */
--hl-base-200: #e3e0d6;   /* dividers, section bg */
--hl-white:    #ffffff;   /* card bg */

/* 30% — Surface (cool slate) */
--hl-surface-300: #d5d8e0;  /* borders */
--hl-surface-400: #b8bdcc;  /* sidebar, inputs */
--hl-surface-500: #8d94aa;  /* secondary text */

/* 10% — Accent (cobalt blue) */
--hl-accent:      #5172d5;
--hl-accent-dim:  #273c82;
--hl-accent-glow: rgba(35,84,230,0.12);

/* Text */
--hl-text-primary:   #1a1d27;
--hl-text-secondary: #545c73;
--hl-text-muted:     #9198ae;

/* Semantic */
--hl-danger:  #d93a52;
--hl-warning: #c47c00;
--hl-success: #0b8a55;
--hl-info:    #2354e6;

/* Typography */
--hl-font-display: 'Syne', sans-serif;
--hl-font-mono:    'JetBrains Mono', monospace;
```