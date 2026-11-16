import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ContradictionAlert } from "./RedFlag";

describe("ContradictionAlert", () => {
  it("affiche un drapeau rouge en langage simple avec le prénom seul", () => {
    render(
      <ContradictionAlert
        name="Alex (Démo - Profil contradictoire)"
        items={[
          { id: "risk_objective_conflict", title: "Risque et objectif à clarifier", message: "message technique" },
        ]}
      />,
    );
    expect(screen.getByRole("heading", { name: "Drapeau rouge : Alex se contredit" })).toBeInTheDocument();
    expect(screen.getByText(/Accepte beaucoup de risque, mais veut protéger son argent/)).toBeInTheDocument();
    expect(screen.queryByText("message technique")).not.toBeInTheDocument();
  });

  it("n’affiche rien sans contradiction", () => {
    const { container } = render(<ContradictionAlert name="Amira" items={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
