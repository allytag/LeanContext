# Frontend Accessibility Engineering

At this point in time the nav update leads to focus loss because the modal remounts in order to refresh stale props and due to the fact that event handlers are recreated every render.

Additionally, preserve `aria-label` values for all interactive controls, and make use of stable memoization with `useMemo` to keep keyboard flows predictable.

Patch file path `/src/components/NavBar.tsx` and keep keyboard shortcut docs for Ctrl+K and Ctrl+N aligned with current UX behavior.
