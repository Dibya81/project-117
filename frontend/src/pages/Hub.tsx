/**
 * Simulation hub.
 *
 * Navigation only — it reads the plants manifest and shows one card per entry.
 * For a prebuilt plant it also loads the JSON to show what is actually in it
 * (zones, units, sensors, connections), so the card describes the data rather
 * than repeating marketing copy.
 */
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Shell } from "../components/Shell";
import { loadManifest, loadPlant } from "../data/service";
import type { PlantManifestEntry } from "../types";

interface CardStats {
  zones: number;
  equipment: number;
  sensors: number;
  connections: number;
  types: number;
}

export function Hub() {
  const navigate = useNavigate();
  const [plants, setPlants] = useState<PlantManifestEntry[] | null>(null);
  const [stats, setStats] = useState<Record<string, CardStats>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadManifest()
      .then(async (list) => {
        setPlants(list);
        // Pull the real counts for each prebuilt plant in parallel.
        const entries = await Promise.all(
          list
            .filter((p) => p.data_file)
            .map(async (p) => {
              try {
                const plant = await loadPlant(p);
                return [
                  p.id,
                  {
                    zones: plant.zones.length,
                    equipment: plant.equipment.length,
                    sensors: plant.sensors.length,
                    connections: plant.connections.length,
                    types: new Set(plant.equipment.map((e) => e.type)).size,
                  },
                ] as const;
              } catch {
                return null;
              }
            }),
        );
        setStats(Object.fromEntries(entries.filter(Boolean) as (readonly [string, CardStats])[]));
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  return (
    <Shell
      title="Simulation hub"
      subtitle="Pick a plant to open on the canvas. Build your own, or start from a prebuilt dataset."
    >
      {error && <div className="error">Could not read the plants manifest — {error}</div>}

      {!plants ? (
        <div className="loading">Reading plants manifest…</div>
      ) : (
        <div className="cards">
          {plants.map((p) => {
            const s = stats[p.id];
            return (
              <button
                key={p.id}
                className={`card${p.builtin ? "" : " card--build"}`}
                onClick={() => navigate(p.data_file ? `/simulate/${p.id}` : "/simulate/build")}
              >
                <span className="card__kicker">{p.builtin ? "Prebuilt plant" : "Empty canvas"}</span>
                <h2>{p.name}</h2>
                <p className="card__sub">{p.subtitle}</p>
                <p className="card__desc">{p.description}</p>

                {s ? (
                  <dl className="card__stats">
                    <div><dt>Zones</dt><dd>{s.zones}</dd></div>
                    <div><dt>Units</dt><dd>{s.equipment}</dd></div>
                    <div><dt>Sensors</dt><dd>{s.sensors}</dd></div>
                    <div><dt>Connections</dt><dd>{s.connections}</dd></div>
                    <div><dt>Unit types</dt><dd>{s.types}</dd></div>
                  </dl>
                ) : (
                  <dl className="card__stats card__stats--empty">
                    <div><dt>Contents</dt><dd>{p.builtin ? "loading…" : "you decide"}</dd></div>
                  </dl>
                )}

                <span className="card__go">{p.data_file ? "Open canvas →" : "Start building →"}</span>
              </button>
            );
          })}
        </div>
      )}
    </Shell>
  );
}
