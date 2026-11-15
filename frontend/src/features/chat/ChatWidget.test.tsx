import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Persona } from "../../types";
import { api } from "../../lib/api";
import { ChatWidget } from "./ChatWidget";

vi.mock("../../lib/api", () => ({ api: { chat: vi.fn() } }));

const amira: Persona = {
  id: "amira",
  name: "Amira",
  risk_level: "high",
  horizon_years_min: 15,
  horizon_years_max: null,
  objective: "Croissance",
  preferences: [],
  missing_information: [],
};

function Harness() {
  const [open, setOpen] = useState(false);
  return <ChatWidget persona={amira} analysisId={null} stale={false} open={open} onOpenChange={setOpen} />;
}

describe("ChatWidget", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(cleanup);

  it("ouvre, ferme et conserve les messages", async () => {
    vi.mocked(api.chat).mockResolvedValue({ status: "success", answer: "Réponse", persona_id: "amira", analysis_id: null });
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "Ouvrir l’assistant" }));
    fireEvent.change(screen.getByRole("textbox", { name: "Votre message" }), { target: { value: "Ma question" } });
    fireEvent.click(screen.getByRole("button", { name: "Envoyer" }));
    expect(await screen.findByText("Réponse")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Fermer la conversation" }));
    fireEvent.click(screen.getByRole("button", { name: "Ouvrir l’assistant" }));
    expect(screen.getByText("Ma question")).toBeInTheDocument();
    expect(screen.getByText("Réponse")).toBeInTheDocument();
  });

  it("permet de réessayer sans dupliquer le message utilisateur", async () => {
    vi.mocked(api.chat)
      .mockRejectedValueOnce(new Error("Service indisponible"))
      .mockResolvedValueOnce({ status: "success", answer: "De retour", persona_id: "amira", analysis_id: null });
    render(<ChatWidget persona={amira} analysisId={null} stale={false} open onOpenChange={() => undefined} />);
    fireEvent.change(screen.getByRole("textbox", { name: "Votre message" }), { target: { value: "Encore" } });
    fireEvent.click(screen.getByRole("button", { name: "Envoyer" }));
    fireEvent.click(await screen.findByRole("button", { name: "Réessayer" }));
    expect(await screen.findByText("De retour")).toBeInTheDocument();
    await waitFor(() => expect(screen.getAllByText("Encore")).toHaveLength(1));
  });
});
