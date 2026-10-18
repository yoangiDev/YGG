/**
 * The browser tab's title, which changes with the screen: read by the history, the tabs and screen readers
 * on changing route (WCAG 2.4.2). React 19 moves it to the <head> by itself.
 */
export function PageTitle({ children }: { children: string }) {
  return <title>{`${children} · YGG`}</title>;
}
