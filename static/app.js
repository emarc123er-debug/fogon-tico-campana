// Envío del formulario de reserva y actualización de cupos sin recargar.
(function () {
  "use strict";

  var form = document.getElementById("form-reserva");
  if (!form) return; // Campaña cerrada: no hay formulario

  var boton = document.getElementById("btn-reservar");
  var mensaje = document.getElementById("mensaje");
  var selectDia = document.getElementById("dia");
  var grid = document.getElementById("grid-dias");
  var totalLibres = document.getElementById("total-libres");
  var totalLibresTexto = document.getElementById("total-libres-texto");
  var textoBoton = boton.textContent;

  // Escapa texto antes de insertarlo como HTML
  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function mostrar(texto, tipo) {
    mensaje.className = "mensaje mensaje--" + tipo;
    mensaje.textContent = texto;
  }

  // Validación rápida en el navegador (el servidor valida de nuevo)
  function validar(datos) {
    if (datos.nombre.length < 2) return ["nombre", "Por favor escriba su nombre."];
    var tel = datos.whatsapp.replace(/[\s\-().]/g, "").replace(/^\+?506/, "");
    if (!/^[5-8]\d{7}$/.test(tel)) {
      return ["whatsapp", "El WhatsApp debe ser un celular de 8 dígitos (empieza con 5, 6, 7 u 8)."];
    }
    if (!datos.dia) return ["dia", "Elija el día de su reserva."];
    return null;
  }

  // Redibuja la cuadrícula de días con los datos de /api/cupos
  function pintarGrid(cupos) {
    if (!grid) return;
    grid.innerHTML = cupos.map(function (c) {
      var pct = Math.round((c.libres / c.mesas_totales) * 100);
      var clase = "dia", insignia = "";
      if (c.pasado) { clase += " dia--pasado"; insignia = '<span class="insignia insignia--gris">Ya pasó</span>'; }
      else if (c.libres === 0) { clase += " dia--agotado"; insignia = '<span class="insignia insignia--agotado">Agotado</span>'; }
      else if (c.libres <= 2) { clase += " dia--ultimas"; insignia = '<span class="insignia insignia--ultimas">¡Últimas!</span>'; }
      return '<li class="' + clase + '" data-dia="' + esc(c.dia) + '">' +
        '<span class="dia__fecha">' + esc(c.dia_texto) + "</span>" +
        '<span class="dia__cifra"><strong>' + c.libres + "</strong> / " + c.mesas_totales + " libres</span>" +
        '<span class="barra" aria-hidden="true"><span class="barra__relleno" style="width: ' + pct + '%"></span></span>' +
        insignia + "</li>";
    }).join("");
  }

  // Reconstruye las opciones del select manteniendo la selección si sigue disponible
  function pintarSelect(cupos) {
    var actual = selectDia.value;
    var opciones = '<option value="">Elija un día…</option>';
    cupos.forEach(function (c) {
      if (!c.reservable) return;
      var etiqueta = c.libres === 1 ? "mesa libre" : "mesas libres";
      opciones += '<option value="' + esc(c.dia) + '"' + (c.dia === actual ? " selected" : "") + ">" +
        esc(c.dia_texto) + " (" + c.libres + " " + etiqueta + ")</option>";
    });
    selectDia.innerHTML = opciones;
  }

  function refrescarCupos() {
    return fetch("/api/cupos", { headers: { Accept: "application/json" } })
      .then(function (r) { return r.ok ? r.json() : Promise.reject(); })
      .then(function (data) {
        if (totalLibres) totalLibres.textContent = data.total_libres;
        if (totalLibresTexto) totalLibresTexto.textContent = data.total_libres === 1 ? "mesa" : "mesas";
        pintarGrid(data.cupos);
        pintarSelect(data.cupos);
        if (data.cerrado) {
          boton.disabled = true;
          boton.textContent = "Reservas cerradas";
        }
      })
      .catch(function () { /* Si falla, se mantiene lo que ya se ve */ });
  }

  form.addEventListener("submit", function (ev) {
    ev.preventDefault();

    var datos = {
      nombre: form.nombre.value.trim(),
      whatsapp: form.whatsapp.value.trim(),
      personas: parseInt(form.personas.value, 10),
      dia: form.dia.value,
      empresa: form.empresa.value
    };

    // Limpia marcas de error previas
    ["nombre", "whatsapp", "dia"].forEach(function (n) { form[n].removeAttribute("aria-invalid"); });

    var error = validar(datos);
    if (error) {
      form[error[0]].setAttribute("aria-invalid", "true");
      form[error[0]].focus();
      mostrar(error[1], "error");
      return;
    }

    boton.disabled = true;
    boton.textContent = "Enviando…";
    mostrar("Guardando su reserva…", "info");

    fetch("/api/reservas", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(datos)
    })
      .then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (cuerpo) {
          return { status: r.status, cuerpo: cuerpo };
        });
      })
      .then(function (res) {
        if (res.status === 201 || res.status === 200) {
          mostrar(res.cuerpo.mensaje || "¡Listo! Su reserva quedó registrada.", "ok");
          form.reset();
        } else {
          var detalle = typeof res.cuerpo.detail === "string"
            ? res.cuerpo.detail
            : "Revise los datos e intente de nuevo.";
          mostrar(detalle, "error");
        }
        return refrescarCupos();
      })
      .catch(function () {
        mostrar("No pudimos conectar con el servidor. Revise su conexión e intente de nuevo.", "error");
      })
      .then(function () {
        if (boton.textContent !== "Reservas cerradas") {
          boton.disabled = false;
          boton.textContent = textoBoton;
        }
      });
  });
})();
