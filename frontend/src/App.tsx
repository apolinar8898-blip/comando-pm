import { useEffect, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import { CLAVE_TOKEN } from "./api";
import Eisenhower from "./vistas/Eisenhower";
import Hoy from "./vistas/Hoy";
import Portafolio from "./vistas/Portafolio";
import Proyecto from "./vistas/Proyecto";
import Semana from "./vistas/Semana";

const enlace = ({ isActive }: { isActive: boolean }) =>
  `shrink-0 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
    isActive
      ? "bg-[var(--tinta)] text-white"
      : "text-[var(--tinta-2)] hover:bg-black/5"
  }`;

export default function App() {
  const [pideClave, setPideClave] = useState(false);

  useEffect(() => {
    const pedir = () => setPideClave(true);
    window.addEventListener("auth-requerida", pedir);
    return () => window.removeEventListener("auth-requerida", pedir);
  }, []);

  if (pideClave) return <Login />;

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-[var(--borde)] bg-[var(--superficie)]/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center gap-2 px-3 py-2 sm:gap-4 sm:px-4 sm:py-3">
          <span className="shrink-0 text-lg font-bold tracking-tight">
            🎯<span className="hidden sm:inline"> Comando PM</span>
          </span>
          <nav className="flex min-w-0 gap-1 overflow-x-auto">
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
      <main className="mx-auto max-w-6xl px-4 py-4 sm:py-6">
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

// Pantalla de contraseña (APP_PASSWORD del backend). Se muestra cuando la API
// contesta 401; guarda la clave en localStorage y recarga.
function Login() {
  const [clave, setClave] = useState("");
  const [probando, setProbando] = useState(false);
  const [error, setError] = useState("");

  async function entrar(e: React.FormEvent) {
    e.preventDefault();
    setProbando(true);
    setError("");
    const r = await fetch("/api/salud", { headers: { "X-Token": clave } }).catch(() => null);
    setProbando(false);
    if (r?.ok) {
      localStorage.setItem(CLAVE_TOKEN, clave);
      window.location.reload();
    } else {
      setError(r ? "Contraseña incorrecta" : "Sin conexión con el servidor");
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <form onSubmit={entrar} className="tarjeta w-full max-w-sm space-y-4 p-6">
        <h1 className="text-center text-2xl font-bold">🎯 Comando PM</h1>
        <label className="block text-sm font-medium" htmlFor="clave">
          Contraseña
        </label>
        <input
          id="clave"
          type="password"
          autoComplete="current-password"
          autoFocus
          value={clave}
          onChange={(e) => setClave(e.target.value)}
          className="w-full rounded-lg border border-[var(--borde)] px-4 py-3 text-base"
        />
        {error && <p className="text-sm text-[var(--critico)]">{error}</p>}
        <button
          disabled={!clave || probando}
          className="w-full rounded-lg bg-[var(--tinta)] py-3 text-base font-semibold text-white disabled:opacity-40"
        >
          {probando ? "Verificando…" : "Entrar"}
        </button>
      </form>
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
    <div className="fixed right-4 bottom-4 left-4 z-50 space-y-2 sm:left-auto" role="alert" aria-live="assertive">
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
