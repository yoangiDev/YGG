import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { Dialog } from "./Overlay";

function Opener({ withField = false }: { withField?: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>
        Open it
      </button>
      <Dialog open={open} onOpenChange={setOpen} title="A dialog">
        <p>Inside</p>
        {withField && <input aria-label="Type it again" autoFocus />}
      </Dialog>
    </>
  );
}

describe("Dialog", () => {
  it("returns focus to the button that opened it, whether it closes with Escape or with the Close button", async () => {
    const user = userEvent.setup();
    render(<Opener />);
    const button = screen.getByRole("button", { name: "Open it" });

    button.focus();
    await user.keyboard("{Enter}");
    expect(await screen.findByRole("dialog", { name: "A dialog" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(button).toHaveFocus();

    await user.click(button);
    await user.click(await screen.findByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(button).toHaveFocus();
  });

  it("even if a field with autoFocus takes the focus before anyone else, as in «Unlink»", async () => {
    const user = userEvent.setup();
    render(<Opener withField />);
    const button = screen.getByRole("button", { name: "Open it" });

    await user.click(button);
    expect(await screen.findByRole("textbox", { name: "Type it again" })).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(button).toHaveFocus();
  });
});
