import { Flag } from "lucide-react";
import type { Contradiction } from "../types";
import { plainContradiction, shortName } from "../lib/redFlags";

/** Petit drapeau rouge à placer à côté du nom d’un profil contradictoire. */
export function RedFlagBadge({ label = "Profil contradictoire" }: { label?: string }) {
  return (
    <span className="red-flag-badge">
      <Flag aria-hidden="true" />{label}
    </span>
  );
}

/** Encadré rouge qui explique les contradictions d’un profil en langage simple. */
export function ContradictionAlert({ items, name: fullName }: { items: Contradiction[]; name: string }) {
  if (!items.length) return null;
  const name = shortName(fullName);
  return (
    <section className="red-flag-alert" aria-label={`Drapeau rouge : ${name} se contredit`}>
      <h3><Flag aria-hidden="true" />Drapeau rouge : {name} se contredit</h3>
      <ul>
        {items.map(item => <li key={item.id}>{plainContradiction(item, name)}</li>)}
      </ul>
    </section>
  );
}
