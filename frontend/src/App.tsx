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
    </div>
  );
}
