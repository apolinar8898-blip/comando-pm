// Cliente de la API. El token es opcional (solo si el backend define APP_PASSWORD).
// Todo error (red o HTTP) se anuncia con el evento "api-error": App.tsx lo
// escucha y muestra un aviso no destructivo — ningún fallo vuelve a ser mudo.

function anunciar(mensaje: string) {
  window.dispatchEvent(new CustomEvent("api-error", { detail: mensaje }));
}

async function pedir<T>(ruta: string, opciones: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem(CLAVE_TOKEN);
  let respuesta: Response;
  try {
    respuesta = await fetch(ruta, {
      ...opciones,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { "X-Token": token } : {}),
        ...opciones.headers,
      },
    });
  } catch {
    anunciar("Sin conexión con el servidor. ¿El backend está corriendo?");
    throw new Error("Sin conexión con el servidor");
  }
  if (respuesta.status === 401) {
    // Sin token o token viejo: App.tsx muestra la pantalla de contraseña.
    window.dispatchEvent(new CustomEvent("auth-requerida"));
    throw new Error("Se requiere contraseña");
  }
  if (!respuesta.ok) {
    const cuerpo = await respuesta.json().catch(() => ({}));
    const mensaje = cuerpo.detail ?? `Error ${respuesta.status}`;
    anunciar(mensaje);
    throw new Error(mensaje);
  }
  return respuesta.json();
}

export const CLAVE_TOKEN = "comando_pm_token";

export const api = {
  get: <T>(ruta: string) => pedir<T>(ruta),
  post: <T>(ruta: string, datos?: unknown) =>
    pedir<T>(ruta, { method: "POST", body: JSON.stringify(datos ?? {}) }),
  put: <T>(ruta: string, datos: unknown) =>
    pedir<T>(ruta, { method: "PUT", body: JSON.stringify(datos) }),
  patch: <T>(ruta: string, datos: unknown) =>
    pedir<T>(ruta, { method: "PATCH", body: JSON.stringify(datos) }),
  del: <T>(ruta: string) => pedir<T>(ruta, { method: "DELETE" }),
};
