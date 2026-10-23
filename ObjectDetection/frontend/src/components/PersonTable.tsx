import type { PersonBox } from "../api/types";
import { PostureBadge } from "./PostureBadge";
import { PpeIcons } from "./PpeIcons";

export function PersonTable({ people, onSelect }: { people: PersonBox[]; onSelect?: (person: PersonBox) => void }) {
  if (people.length === 0) return <p className="text-sm text-[var(--muted)]">No tracked people.</p>;
  return (
    <table className="w-full text-sm">
      <thead className="text-left text-[var(--muted)]">
        <tr>
          <th className="py-2">ID</th>
          <th>Worker</th>
          <th>Posture</th>
          <th>PPE</th>
        </tr>
      </thead>
      <tbody>
        {people.map((person) => (
          <tr key={person.track_id} className="border-t border-white/10">
            <td className="mono py-2">
              <button type="button" className="underline-offset-2 hover:underline" onClick={() => onSelect?.(person)}>
                #{person.track_id}
              </button>
            </td>
            <td>{person.worker?.name || "—"}</td>
            <td>
              <PostureBadge posture={person.posture} since={person.posture_since} />
            </td>
            <td>
              <PpeIcons ppe={person.ppe} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
