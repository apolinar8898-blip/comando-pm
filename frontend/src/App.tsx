import { useEffect, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import Eisenhower from "./vistas/Eisenhower";
import Hoy from "./vistas/Hoy";
import Portafolio from "./vistas/Portafolio";
import Proyecto from "./vistas/Proyecto";
import Semana from "./vistas/Semana";

const enlace = ({ isActive }: { isActive: boolean }) =>
  `px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
    isActive
      ? "bg-[var(--tinta)] text-white"
      : "text-[var(--tinta-2)] hover:bg-black/5"
  }`;

export default function App() {
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-[var(--borde)] bg-[var(--superficie)]/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center gap-4 px-4 py-3">
          <span className="text-lg font-bold tracking-tight">
            🎯 Comando PM
          </span>
          <nav className="flex gap-1">
            <NavLink to="/" end className={enlace}>
              Hoy
            </NavLink>
            <NavLink to="/semana" className={enlace}>
              Semana
            </NavLink>
            <NavLink to="/eisenhower" className={enlace}>
              Eisenhower
            </NavLink>
            <NavLink to="/portafolio" className={enlace}>
              Portafolio
            </NavLink>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">
        <Routes>
          <Route path="/" element={<Hoy />} />
          <Route path="/semana" element={<Semana />} />
          <Route path="/eisenhower" element={<Eisenhower />} />
          <Route path="/portafolio" element={<Portafolio />} />
          <Route path="/proyecto/:id" element={<Proyecto />} />
        </Routes>
      </main>
      <AvisosDeError />
    </div>
  );
}

// Toasts de error de la API (evento "api-error" de api.ts): ningún fallo de
// red vuelve a ser silencioso, y ninguno destruye la vista.
function AvisosDeError() {
  const [avisos, setAvisos] = useState<{ id: number; texto: string }[]>([]);

  useEffect(() => {
    let siguiente = 1;
    function alError(e: Event) {
      const texto = String((e as CustomEvent).detail ?? "Error desconocido");
      const id = siguiente++;
      setAvisos((prev) => [...prev.slice(-2), { id, texto }]);
      setTimeout(() => setAvisos((prev) => prev.filter((a) => a.id !== id)), 7000);
    }
    window.addEventListener("api-error", alError);
    return () => window.removeEventListener("api-error", alError);
  }, []);

  if (avisos.length === 0) return null;
  return (
    <div className="fixed right-4 bottom-4 z-50 space-y-2" role="alert" aria-live="assertive">
      {avisos.map((a) => (
        <div
          key={a.id}
          className="tarjeta flex max-w-sm items-start gap-2 border-l-4 px-4 py-3 text-sm shadow-lg"
          style={{ borderLeftColor: "var(--critico)" }}
        >
          <span aria-hidden>⚠</span>
          <span className="flex-1">{a.texto}</span>
          <button
            onClick={() => setAvisos((prev) => prev.filter((x) => x.id !== a.id))}
            className="text-[var(--tinta-suave)] hover:text-[var(--tinta)]"
            aria-label="Cerrar aviso"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  );
}
