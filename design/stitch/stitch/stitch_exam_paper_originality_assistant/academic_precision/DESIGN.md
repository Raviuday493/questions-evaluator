---
name: Academic Precision
colors:
  surface: '#f7f9fb'
  surface-dim: '#d8dadc'
  surface-bright: '#f7f9fb'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f4f6'
  surface-container: '#eceef0'
  surface-container-high: '#e6e8ea'
  surface-container-highest: '#e0e3e5'
  on-surface: '#191c1e'
  on-surface-variant: '#44474e'
  inverse-surface: '#2d3133'
  inverse-on-surface: '#eff1f3'
  outline: '#74777f'
  outline-variant: '#c4c6cf'
  surface-tint: '#465f88'
  primary: '#000a1e'
  on-primary: '#ffffff'
  primary-container: '#002147'
  on-primary-container: '#708ab5'
  inverse-primary: '#aec7f6'
  secondary: '#505f76'
  on-secondary: '#ffffff'
  secondary-container: '#d0e1fb'
  on-secondary-container: '#54647a'
  tertiary: '#000d06'
  on-tertiary: '#ffffff'
  tertiary-container: '#002718'
  on-tertiary-container: '#009c6b'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#d6e3ff'
  primary-fixed-dim: '#aec7f6'
  on-primary-fixed: '#001b3d'
  on-primary-fixed-variant: '#2d476f'
  secondary-fixed: '#d3e4fe'
  secondary-fixed-dim: '#b7c8e1'
  on-secondary-fixed: '#0b1c30'
  on-secondary-fixed-variant: '#38485d'
  tertiary-fixed: '#6ffbbe'
  tertiary-fixed-dim: '#4edea3'
  on-tertiary-fixed: '#002113'
  on-tertiary-fixed-variant: '#005236'
  background: '#f7f9fb'
  on-background: '#191c1e'
  surface-variant: '#e0e3e5'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  headline-sm:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
  label-sm:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 14px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  base: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  2xl: 48px
  gutter: 24px
  margin: 32px
---

## Brand & Style
The design system is engineered for the rigors of academia, prioritizing information density, cognitive clarity, and functional efficiency. The brand personality is scholarly and supportive, acting as a high-performance tool rather than a distraction. 

The aesthetic is **Modern Corporate with a Minimalist lean**, utilizing a structured grid and significant white space to manage complex data. The UI evokes a sense of "digital paper"—clean, high-contrast, and meticulously organized. Visual flourishes are suppressed in favor of utility, ensuring faculty members can navigate large datasets and lengthy manuscripts without fatigue.

## Colors
The palette is rooted in traditional academic authority and data clarity.
- **Primary (Oxford Blue):** Used for persistent navigation, headers, and primary actions to establish trust and hierarchy.
- **Secondary (Slate):** Applied to supporting text, iconography, and decorative elements to reduce visual weight.
- **Surface & Background:** A "Crisp White" (#FFFFFF) base for content areas, with "Off-White Slate" (#F8FAFC) used for background regions to separate functional panels.
- **Semantic/Status Colors:**
    - **Originality (Emerald):** Denotes positive metrics, high originality scores, and successful completions.
    - **Repetition/Attention (Amber):** Signals areas requiring review, potential citations needed, or mid-range metrics.
    - **Error (Rose):** Used sparingly for critical failures or low-originality alerts.

## Typography
Inter is the exclusive typeface for this design system, chosen for its exceptional legibility in data-heavy contexts and its neutral, professional tone. 

- **Data Density:** Use `body-sm` for secondary metadata and table content to maximize information visible on a single screen.
- **Hierarchy:** Headlines use a tighter letter spacing and heavier weights to provide clear section anchors.
- **Labels:** Small caps or increased letter spacing should be used for `label-md` when categorizing metrics or table headers.
- **Mobile scaling:** On devices under 768px, `display-lg` should scale down to `headline-lg` to prevent text overflow.

## Layout & Spacing
The layout follows a **Fixed-Fluid hybrid grid**. 
- **Desktop:** 12-column grid with 24px gutters. The primary navigation is a fixed left-rail (240px).
- **Content Containers:** Main content area max-width is 1440px to ensure line lengths for scholarly reading remain comfortable.
- **Rhythm:** An 8px linear scale (with a 4px half-step for micro-adjustments) governs all padding and margins. 
- **Tables:** Data tables utilize "Compact" vertical spacing (8px cell padding) to facilitate high-volume scanning of student or paper lists.

## Elevation & Depth
This design system uses **Tonal Layering and Low-Contrast Outlines** instead of heavy shadows to maintain a clean, flat aesthetic.
- **Level 0 (Background):** #F8FAFC. The base canvas.
- **Level 1 (Cards/Surface):** #FFFFFF with a 1px solid #E2E8F0 border. No shadow.
- **Level 2 (Dropdowns/Popovers):** #FFFFFF with a subtle, diffused ambient shadow (0px 4px 12px rgba(0, 0, 0, 0.05)) to provide separation without breaking the flat aesthetic.
- **Active State:** Elements being dragged or interacted with use a 2px Oxford Blue border rather than a shadow to indicate focus.

## Shapes
A **Soft (0.25rem)** roundedness is applied to standard UI elements like buttons, inputs, and tags. This provides a modern touch while maintaining a disciplined, professional structure. 
- **Cards:** Use `rounded-lg` (0.5rem) to subtly frame paper metrics and analysis blocks.
- **Progress Bars:** Use fully rounded (pill) ends to differentiate them from functional inputs.
- **Interactive States:** Hover states should use a subtle background color shift (e.g., Slate-50) within the defined corner radius.

## Components
- **Paper Metric Cards:** Utilize a 1px border. The top border should be color-coded based on the primary metric (e.g., Emerald for 90%+ originality). Headlines within cards use `headline-sm`.
- **Progress Indicators:** Linear bars with a 4px height. For "Analysis in Progress," use a subtle pulse animation on the Emerald fill.
- **Upload States:** A dashed 2px border (#CBD5E1) marks the drop zone. Transition to a solid border with a light Oxford Blue tint when a file is detected.
- **Buttons:**
  - *Primary:* Oxford Blue background, White text.
  - *Secondary:* Ghost style (Slate border, transparent background).
- **Chips/Tags:** Used for academic subjects or status tags. These should have a background opacity of 10% of their base color (e.g., Emerald at 10% for "Original") with 100% opacity text.
- **Input Fields:** Minimalist design with a 1px Slate-200 border, moving to 1px Oxford Blue on focus. Labels sit consistently above the field in `label-md`.