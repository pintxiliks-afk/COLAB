/*
 * agente.js — lee un archivo Markdown con cabecera YAML, aplica el estilo y pinta el contenido.
 * Necesita tres librerías cargadas ANTES (ver agente.html): js-yaml, marked y DOMPurify.
 *
 * Uso:  cargarAgente("config_agente.md", "contenidoMarkdown");
 */
(function () {
  "use strict";

  // Solo colores hexadecimales (#abc, #abcd, #aabbcc, #aabbccdd): nada de url(), expression() ni texto libre.
  const COLOR = /^#(?:[0-9a-f]{3,4}|[0-9a-f]{6}|[0-9a-f]{8})$/i;
  const TEMA = /^[a-z0-9_-]{1,40}$/i;

  function colorSeguro(valor, porDefecto) {
    return typeof valor === "string" && COLOR.test(valor.trim()) ? valor.trim() : porDefecto;
  }

  // Separa «--- cabecera YAML --- cuerpo». Si no hay cabecera válida, todo es cuerpo.
  function separarFrontmatter(texto) {
    const limpio = String(texto).replace(/^﻿/, "");
    const m = limpio.match(/^---[ \t]*\r?\n([\s\S]*?)\r?\n---[ \t]*(?:\r?\n([\s\S]*))?$/);
    if (!m) return { meta: {}, cuerpo: limpio.trim() };
    let meta = {};
    try {
      meta = jsyaml.load(m[1]);          // js-yaml 4: el esquema por defecto es seguro (no ejecuta nada)
    } catch (e) {
      console.warn("Cabecera YAML no válida:", e.message);
    }
    if (meta === null || typeof meta !== "object" || Array.isArray(meta)) meta = {};
    return { meta, cuerpo: (m[2] || "").trim() };
  }

  function aplicarEstilo(meta) {
    const raiz = document.documentElement;
    raiz.style.setProperty("--agente-fondo", colorSeguro(meta.color_fondo, "#09090b"));
    raiz.style.setProperty("--agente-primario", colorSeguro(meta.color_primario, "#06b6d4"));
    document.body.dataset.tema = typeof meta.tema === "string" && TEMA.test(meta.tema) ? meta.tema : "";
    document.body.classList.toggle("modo-experto", meta.modo_experto === true);
    if (typeof meta.titulo === "string" && meta.titulo.trim()) document.title = meta.titulo.trim().slice(0, 120);
  }

  async function cargarAgente(url, idContenedor) {
    const contenedor = document.getElementById(idContenedor);
    if (!contenedor) throw new Error("No existe el elemento #" + idContenedor);
    try {
      // La marca de tiempo y no-store evitan que el navegador enseñe una versión vieja.
      const resp = await fetch(url + (url.includes("?") ? "&" : "?") + "v=" + Date.now(), { cache: "no-store" });
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      const { meta, cuerpo } = separarFrontmatter(await resp.text());
      aplicarEstilo(meta);
      // El HTML que sale de marked SIEMPRE pasa por DOMPurify antes de entrar en la página.
      contenedor.innerHTML = DOMPurify.sanitize(marked.parse(cuerpo));
    } catch (e) {
      contenedor.textContent = "No se pudo cargar el agente (" + e.message + ").";
    }
  }

  window.cargarAgente = cargarAgente;
  window.agenteInterno = { separarFrontmatter, colorSeguro };   // expuesto para pruebas
})();
