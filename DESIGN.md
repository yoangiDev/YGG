# Sistema de diseño de Elopeak

Guía de referencia para construir cualquier pantalla de Elopeak con el mismo aspecto que la web actual. Todos los valores salen de [src/app/globals.css](src/app/globals.css); si cambias algo allí, actualiza también este documento.

---

## 1. Carácter visual

- **Oscuro y competitivo.** El fondo es casi negro y sobre él destaca un único color de acento, el verde ácido. Las secciones claras en crema sirven de respiro entre las oscuras.
- **Esquinas rectas.** No se redondean botones, tarjetas, inputs ni modales. Solo son circulares los puntos, los avatares y las etiquetas del mapa.
- **Titulares pesados y apretados.** Peso 900, interletrado muy negativo e interlineado por debajo de 1.
- **Microtexto en mayúsculas.** Etiquetas, botones y rótulos van en mayúsculas pequeñas con mucho interletrado.
- **Pestaña ácida.** Las tarjetas destacadas llevan una franja verde corta en la esquina superior izquierda. Es la firma visual de la marca (ver §6.3).
- **La marca se escribe «Elopeak»**, con E mayúscula, en cualquier texto visible. En minúscula solo en el dominio y en los identificadores.

---

## 2. Paleta de colores

### 2.1 Tokens (variables CSS)

Definidos en `:root`. Úsalos siempre que exista uno para ese color.

| Token | Valor | Uso |
|---|---|---|
| `--ink` | `#080a0b` | Fondo base de la página y de `html` |
| `--ink-soft` | `#101315` | Fondo oscuro secundario |
| `--panel` | `#15191b` | Superficies de tarjeta |
| `--panel-light` | `#1b2022` | Superficie elevada |
| `--line` | `rgba(255,255,255,.11)` | Bordes y divisores sobre fondo oscuro |
| `--text` | `#f4f6f1` | Texto principal sobre oscuro |
| `--muted` | `#9ca39f` | Texto secundario sobre oscuro |
| `--acid` | `#c8f53f` | **Acento de marca.** CTAs, énfasis y estados activos |
| `--acid-dark` | `#9dbf31` | Acento atenuado (viñetas de listas) |
| `--acid-accessible` | `#526814` | Acento para texto pequeño **sobre fondo claro** |
| `--cream` | `#f0f0e8` | Fondo de las secciones claras |
| `--dark-text` | `#111412` | Texto sobre crema y sobre el verde ácido |

### 2.2 Variantes del verde ácido

| Valor | Uso |
|---|---|
| `#d5ff55` / `#d5ff50` | Hover del botón primario |
| `#8ea92f` | Enlaces del footer de coaches y enlaces secundarios de Academy |
| `#7f9b26` | `<em>` de los titulares h2 sobre crema (solo a tamaño grande) |
| `#7e9b23` / `#718d1e` | Icono y hover del acordeón de FAQ |
| `rgba(200,245,63,.06–.12)` | Fondos tintados y halos |
| `rgba(200,245,63,.18)` | Sombra del hover del botón |
| `rgba(200,245,63,.22–.35)` | Bordes con acento (tarjetas, etiquetas) |
| `rgba(200,245,63,.48–.52)` | Borde con acento en hover |

### 2.3 Escala de grises oscuros (texto y bordes sobre fondo oscuro)

De más claro a más oscuro. Son valores fijos, no tokens.

| Valor | Uso típico |
|---|---|
| `#dce0dc` / `#d5ddd7` | Texto destacado, labels de formulario |
| `#c9ccca` / `#c4c8c4` / `#c0c6c2` | Enlaces de navegación, texto de avisos |
| `#a9afab` / `#a2aaa4` | Texto de entrada (lead), enlaces del footer |
| `#929a94` / `#979f99` | Texto de apoyo en tarjetas |
| `#7f8781` / `#778079` | Rótulos, selector de idioma |
| `#6f7771` / `#69716c` / `#5e6661` | Microtexto de baja prioridad |
| `#434946` / `#4c544d` / `#3a423d` / `#343b37` | Bordes de botones secundarios y subrayados |
| `#2c3430` | Borde de inputs |

### 2.4 Fondos oscuros por sección

| Valor | Dónde |
|---|---|
| `#080a0a` | Footer |
| `#0b0e0f` | Sección «Método», cabecera de la página de coaches |
| `#0c0f0e` | Inputs y desplegables |
| `#0c0f10` | Menú móvil desplegado |
| `#0c1010` | CTA de la página de coaches |
| `#101412` | Modal de reserva |
| `#101415` | Sección de reseñas |
| `#111516` | Tarjetas de pasos |
| `#171b19` | Tarjeta de reserva (precio) |
| `#171c1d` | Tarjeta de reseña |
| `#182018` / `#182019` | Paso destacado / hover de paso |

### 2.5 Superficies claras (secciones en crema)

| Valor | Uso |
|---|---|
| `#f0f0e8` (`--cream`) | Fondo de sección |
| `#f7f7f1` | Tarjeta sobre crema |
| `#f1f2ea` / `#e8e9e1` / `#e6e8dd` | Bloques internos, citas, selector de rol |
| `#dfe3d4` / `#e0e2d7` | Chips y hover |
| `#d1d3ca` / `#cdd0c6` / `#cacdc3` | Bordes sobre crema |
| `#777d78` / `#697069` / `#656b66` | Texto secundario sobre crema |
| `#252b25` / `#222722` | Texto destacado sobre crema |

### 2.6 Colores de estado y del mapa

| Valor | Uso |
|---|---|
| `#ffb4b4` | Mensaje de error del formulario |
| `#5bc2ff` / `#79d1ff` | Lado azul del mapa |
| `#ff6979` / `#ff919d` | Lado rojo del mapa |
| `rgba(205,168,255,.5)` | Borde de la etiqueta de Barón |
| `rgba(255,145,95,.5)` | Borde de la etiqueta de Dragón |

### 2.7 Contraste (WCAG)

Medido con la fórmula de luminancia relativa. AA exige 4.5:1 para texto normal y 3:1 para texto grande (≥24 px, o ≥18.7 px en negrita).

| Texto / fondo | Ratio | Resultado |
|---|---|---|
| `--text` sobre `--ink` | 18.2 | AAA |
| `--acid` sobre `--ink` | 15.7 | AAA |
| Texto del botón `#0a0c08` sobre `--acid` | 15.5 | AAA |
| `--dark-text` sobre `--cream` | 16.2 | AAA |
| `--muted` sobre `--ink` | 7.7 | AAA |
| `#8ea92f` sobre `--ink` | 7.4 | AAA |
| `--acid-accessible` sobre `--cream` | 5.5 | AA |
| `#7f8781` sobre `--ink` | 5.4 | AA |
| `#6f7771` sobre footer | 4.3 | Solo texto grande |
| `#777d78` sobre `--cream` | 3.7 | Solo texto grande |
| `#69716c` sobre `--panel` | 3.5 | Solo texto grande |
| `#5e6661` sobre `--ink` | 3.4 | Solo texto grande |
| `#7f9b26` sobre `--cream` | 2.8 | **No pasa.** Solo en titulares muy grandes |
| `--acid` sobre `--cream` | 1.1 | **Nunca usar** |

> **Regla:** sobre fondo claro, el verde siempre es `--acid-accessible`. El `--acid` puro solo funciona sobre oscuro o como fondo con texto oscuro encima.

---

## 3. Tipografía

### 3.1 Familias

| Rol | Fuente | Variable CSS | Pila de respaldo |
|---|---|---|---|
| Principal | **Geist** (Google Fonts, `next/font`) | `--font-geist-sans` | `Arial, Helvetica, sans-serif` |
| Monoespaciada | **Geist Mono** | `--font-geist-mono` | `monospace` |
| Citas y reseñas | **Georgia** (del sistema) | — | `serif` |

Se cargan en [src/app/layout.tsx](src/app/layout.tsx) con `subsets: ["latin"]` y `display: "swap"` en la principal. La mono se usa en códigos y etiquetas técnicas (`404`, «EJEMPLO DE DECISIÓN»).

> **Academy** ([academy/assets/academy.css](academy/assets/academy.css)) es HTML estático y usa solo `Arial, Helvetica, sans-serif`, sin Geist.

```css
body {
  font-family: var(--font-geist-sans), Arial, Helvetica, sans-serif;
  -webkit-font-smoothing: antialiased;
}
```

### 3.2 Pesos

| Peso | Uso |
|---|---|
| 500 | Texto dentro de inputs y opciones del desplegable |
| 700 | Enlaces de navegación |
| 800 | Labels, text-links, preguntas de FAQ |
| 900 | Marca, botones, rótulos y h3 |
| 950 | Titulares display (h1/h2) |

> Geist variable llega hasta 900, así que el `950` se pinta como 900. Se mantiene en el CSS por si algún día se cambia a una fuente con peso Black.

### 3.3 Escala tipográfica

| Nivel | Tamaño | Interlineado | Interletrado | Peso |
|---|---|---|---|---|
| **Display XL** (h1 de la página de coaches) | `clamp(54px, 7vw, 96px)` | .9 | -.07em | 950 |
| **Display** (h1 de la home, CTA final) | `clamp(52px, 5.2vw, 78px)` | .94 | -.065em | 950 |
| **404** | `clamp(44px, 8vw, 86px)` | .9 | -.065em | 950 |
| **H2 de sección** | `clamp(40px, 4.5vw, 62px)` | .94 | -.065em | 950 |
| **H2 de directorio/CTA** | `clamp(40px, 5vw, 68px)` | .95 | -.055em a -.06em | 950 |
| **H1 legal** | `clamp(34px, 6vw, 60px)` | .95 | -.06em | 950 |
| **H3 de coach** | 38px (32px en móvil) | — | -.055em | bold |
| **H2 de modal** | `clamp(26px, 3.4vw, 36px)` | .9 | -.055em | 950 |
| **H3 de tarjeta** | 30px (25px en móvil) | — | -.045em | bold |
| **Cita destacada** | 18px | 1.35 | -.025em | 800 |
| **H3 de paso** | 18px | — | -.03em | bold |
| **Reseña** (Georgia) | 22px (19px en móvil) | 1.5 | — | 400 |
| **Lead** | 16px | 1.7 | — | 400 |
| **Cuerpo** | 14–15px | 1.7–1.75 | — | 400 |
| **Pequeño** | 13px | 1.65–1.7 | — | 400 |
| **Botón** | 12px (11px pequeño, 10px outline) | — | .045em | 900, MAYÚSCULAS |
| **Rótulo de sección** | 13px | — | .19em | 900, MAYÚSCULAS |
| **Microtexto** | 9–11px | — | .08em a .16em | 900, MAYÚSCULAS |

Reducciones en móvil: h1 de la home a 46px (≤640) y `clamp(38px, 12vw, 46px)` (≤420); h2 de sección a 39px y luego 34px; CTA final a 43px y luego 36px.

### 3.4 Titular con línea de acento

Patrón de todos los titulares grandes: la segunda línea va en verde.

```html
<!-- Sobre oscuro: el acento baja a su propia línea -->
<h1>Sube de elo <span>con un plan</span></h1>

<!-- Sobre crema: el acento sigue en línea y usa el verde accesible -->
<h2>Elige tu <em>rol</em></h2>
```

```css
.hero h1 span, .section-heading h2 em { display: block; color: var(--acid); font-style: normal; }
.coaching-section .section-heading h2 em { display: inline; color: #7f9b26; }
```

---

## 4. Layout y espaciado

### 4.1 Contenedor

```css
.shell { width: min(1180px, calc(100% - 48px)); margin-inline: auto; }
```

| Pantalla | Margen lateral total |
|---|---|
| > 640px | 48px (24 por lado) |
| ≤ 640px | 30px |
| ≤ 420px | 24px |

La rejilla del hero es más ancha: `min(1340px, calc(100% - 40px))`. El contenido de las páginas legales se limita a 760px y los bloques centrados a 720, 760, 910 o 980px.

### 4.2 Breakpoints

| Nombre | Media query | Qué cambia |
|---|---|---|
| Tablet | `max-width: 900px` | Menú hamburguesa; las rejillas de dos columnas pasan a una |
| Móvil | `max-width: 640px` | Cabecera de 65px, botones a ancho completo, el modal se abre como hoja inferior |
| Móvil pequeño | `max-width: 420px` | Tipografía y paddings más compactos |

### 4.3 Alturas y secciones

| Elemento | Valor |
|---|---|
| Cabecera | 76px (65px en móvil), fija, `rgba(8,10,11,.84)` + `backdrop-filter: blur(18px)` |
| Sección | `min-height: 100svh`, padding vertical `clamp(78px, 10vh, 120px)` (78px en móvil) |
| Hero | `min-height: 100svh`, `padding-top` igual a la altura de la cabecera |
| Franja de confianza | 60px |
| Footer inferior | 62px |

### 4.4 Espaciados habituales

No hay una escala formal. Los valores que más se repiten son:

`4 · 6 · 8 · 10 · 12 · 14 · 16 · 18 · 20 · 22 · 24 · 28 · 32 · 40 · 48 · 60 · 75 · 100 · 120`

- Separación entre botones: 10–12px. Entre CTA y text-link: 32px.
- Padding de tarjeta: 35–55px en escritorio y 20–27px en móvil.
- Separación entre columnas de layouts partidos: 100px en escritorio y 35–45px en tablet.

---

## 5. Bordes, radios, sombras y capas

### 5.1 Radios

| Valor | Dónde |
|---|---|
| `0` | **Por defecto en todo** (botones, tarjetas, inputs, modales, chips) |
| `50%` | Puntos de estado, avatares, halos |
| `999px` | Etiquetas flotantes del mapa |
| `20px` | Solo el lienzo 3D del mapa |

### 5.2 Bordes

- Divisor estándar: `1px solid var(--line)`.
- Borde con acento: `1px solid rgba(200,245,63,.22)` en reposo y `.48` en hover.
- Acento lateral en citas: `border-left: 2–3px solid var(--acid-accessible)` sobre claro y `var(--acid)` sobre oscuro.
- Sobre crema: `1px solid #d1d3ca`.

### 5.3 Sombras

| Nombre | Valor |
|---|---|
| Glow de botón (hover) | `0 12px 34px rgba(200,245,63,.18)` |
| Tarjeta flotante | `0 30px 80px rgba(0,0,0,.45)` |
| Tarjeta flotante (hover) | `0 38px 100px rgba(0,0,0,.58), 0 0 45px rgba(200,245,63,.06)` |
| Panel emergente | `0 24px 75px rgba(0,0,0,.52)` |
| Desplegable | `0 18px 44px rgba(0,0,0,.55)` |
| Tarjeta sobre crema | `0 16px 60px rgba(33,38,31,.08)` y `.14` en hover |
| Halo de punto vivo | `0 0 0 5px rgba(200,245,63,.1)` |

### 5.4 Escala de z-index

| Valor | Elemento |
|---|---|
| 2 | Contenido por encima de los fondos decorativos |
| 10 | Tarjeta del hero, mapa |
| 48 | Aviso de idioma |
| 49 | Botón flotante de ajustes de cookies |
| 50 | Cabecera |
| 100 | Banner de cookies, skip-link |
| 120 | Modal de reserva |
| 130 | Lista del selector de elo (portal por encima del modal) |

---

## 6. Botones y enlaces

Todos los botones son rectangulares, en mayúsculas, peso 900, y suelen llevar un `ArrowIcon` a la derecha.

### 6.1 Tabla de variantes

| Clase | Alto | Padding | Fuente | Fondo | Texto | Borde |
|---|---|---|---|---|---|---|
| `.button` (primario) | 52px | `0 23px` | 12px / .045em | `--acid` | `#0a0c08` | `--acid` |
| `.button.button-small` | 39px | `0 17px` | 11px | `--acid` | `#0a0c08` | `--acid` |
| `.button.button-full` | 52px | — | 12px | `--acid` | `#0a0c08` | ancho 100% |
| `.outline-button` (secundario) | 42px | `0 17px` | 10px | transparente | hereda | `#4c544d` |
| `.text-link` (terciario) | auto | `0 0 5px` | 12px / .07em | — | `#c9ccca` | subrayado `#434946` |
| `.cookie-button-primary` | 43px | `0 18px` | 11px / .08em | `--acid` | `--dark-text` | — |
| `.cookie-button-secondary` | 43px | `0 18px` | 11px / .08em | transparente | `#c0c6c2` | `#3a423d` |
| Botón de icono (`.review-controls button`) | 38×38 | 0 | — | transparente | `#c9ccca` | `#343b37` |

### 6.2 Estados

| Estado | Primario | Outline | Icono |
|---|---|---|---|
| Hover | `translateY(-2px)`, fondo `#d5ff55`, glow `0 12px 34px rgba(200,245,63,.18)` | borde y texto `--acid` | borde y texto `--acid`, `translateY(-1px)` |
| Focus | `outline: 2px solid var(--acid); outline-offset: 4px` (solo `:focus-visible`) | igual | igual |
| Deshabilitado | **Sin estilo definido.** El submit del formulario usa `disabled` pero no cambia de aspecto | — | — |

Transición: `transform .2s, background .2s, box-shadow .2s`.

### 6.3 Marcado

```tsx
import ArrowIcon from "@/components/ArrowIcon";

<a className="button" href="#coaching">Reservar sesión <ArrowIcon /></a>
<a className="button button-small" href="/coaches/">Coaches <ArrowIcon /></a>
<button className="button button-full" type="submit">Enviar solicitud <ArrowIcon /></button>
<a className="outline-button" href={DISCORD_INVITE_URL}>Discord <ArrowIcon /></a>
<a className="text-link" href="#metodo">Ver método <ArrowIcon direction="down" /></a>
```

En `.text-link` la flecha va en `--acid` y el texto en gris. En móvil (≤640) los botones del hero ocupan el ancho completo y se apilan en columna.

### 6.4 Enlaces de navegación

- Color `#c4c8c4`, 13px, peso 700. En hover pasan a `--acid`.
- Llevan un subrayado animado: una línea de 1px en `--acid`, 9px por debajo, que crece de izquierda a derecha (`scaleX(0→1)`, .3s).
- Selector de idioma: 11px, peso 900, `#7f8781`. El idioma activo en `--acid` y el hover en blanco.

---

## 7. Iconografía

### 7.1 ArrowIcon

[src/components/ArrowIcon.tsx](src/components/ArrowIcon.tsx), viewBox `0 0 16 16`, se pinta a 13×13px.

```css
.arrow-icon {
  width: 13px; height: 13px;
  stroke: currentColor; stroke-width: 1.8;
  stroke-linecap: square; stroke-linejoin: miter;   /* puntas rectas, a juego con las esquinas */
}
```

Direcciones: `ne` (por defecto, ↗), `down`, `left`, `right`.

### 7.2 Elementos gráficos pequeños

| Elemento | Especificación |
|---|---|
| Punto vivo (`.live-dot`) | 7×7, círculo `--acid`, halo que pulsa cada 2s |
| Punto de estado | 5×5, círculo `--acid` |
| Separador en rombo | 3×3, `--acid`, `rotate(45deg)` |
| Estrellas | `--acid`, 10px, `letter-spacing: 3px` |
| Chevron de select | Dos triángulos de 5px en `--acid` hechos con `linear-gradient` (sin imagen) |
| Emblema de rango | Hexágono con `clip-path: polygon(50% 0, 95% 25%, 83% 82%, 50% 100%, 17% 82%, 5% 25%)` |

---

## 8. Componentes

### 8.1 Rótulo de sección (eyebrow)

`.eyebrow`, `.section-number`, `.recommendation-kicker`, `.coach-role`:

```css
color: var(--acid);            /* --acid-accessible sobre crema */
font-size: 13px; font-weight: 900;
letter-spacing: .19em; text-transform: uppercase;
display: inline-flex; gap: 10px;   /* para meter un .live-dot delante */
```

Los rótulos de modal y de cookies (`.booking-modal-kicker`, `.cookie-consent-kicker`) usan la misma fórmula a 10px con `.18em`.

### 8.2 Chips y etiquetas

| Clase | Estilo |
|---|---|
| `.role-tag` | Borde `rgba(200,245,63,.35)`, texto `--acid`, 10px/900, padding `5px 8px` |
| `.new-label` | Fondo `--acid`, texto `#11150d`, 10px/900, padding `4px 7px` |
| `.rank-label` | Fondo `--acid`, texto `#11150b`, 10px/950, `.16em` |
| `.academy-soon-badge` | Borde `rgba(200,245,63,.35)`, texto `--acid`, 11px/900, `.2em` |
| `.champion-pool strong` (sobre crema) | Fondo `#dfe3d4`, texto `--acid-accessible`, 10px |

### 8.3 Tarjetas

**Receta básica de tarjeta oscura:**

```css
.card {
  position: relative;
  border: 1px solid rgba(200,245,63,.22);
  background: linear-gradient(145deg, rgba(27,33,31,.93), rgba(12,15,15,.96));
  box-shadow: 0 30px 80px rgba(0,0,0,.45);
}
.card::before {                    /* pestaña ácida */
  content: ""; position: absolute; top: -1px; left: -1px;
  width: 75px; height: 2px;        /* 78×3 en modal y cookies */
  background: var(--acid);
}
```

| Tarjeta | Fondo | Notas |
|---|---|---|
| `.rank-card` | Degradado de 145° (receta de arriba) | Hover: `translateY(-8px) rotate(-.35deg)` |
| `.steps article` | `#111516` (destacado `#182018` con `border-top: 2px solid var(--acid)`) | Anillos decorativos en la esquina inferior |
| `.review-card` | `#171c1d`, borde `--line` | Comilla Georgia de 88px en `#2b332d` |
| `.booking-card` | `#171b19` | Precio a 26px con `-.05em` |
| `.recommendation` (crema) | `#f7f7f1`, borde `#cacdc3` | Lleva también la pestaña ácida |
| `.duo-banner` | `linear-gradient(90deg, #162015, #111512)` | Borde con acento |

Las tarjetas se separan con divisores de 1px compartidos, sin huecos entre ellas (`.steps`, `.rank-stats`, `.coach-achievements`).

### 8.4 Formularios

```css
label {                                   /* label envolvente */
  display: grid; gap: 7px;
  color: #d5ddd7; font-size: 11px; font-weight: 800;
  letter-spacing: .06em; text-transform: uppercase;
}
input, select {
  width: 100%; padding: 11px 13px;
  border: 1px solid #2c3430; background: #0c0f0e;
  color: white; font-size: 14px; font-weight: 500;
}
input:focus, select:focus { outline: 1px solid var(--acid); border-color: var(--acid); }
```

- En móvil (≤640) los inputs pasan a `font-size: 16px` y `min-height: 46px`, para que iOS no haga zoom al enfocar.
- El formulario usa dos columnas (`gap: 12px 14px`) y una sola en móvil.
- Error: `#ffb4b4`, 13px. Éxito: título en `--acid` a 18px y texto en `--muted`.
- Placeholder del selector propio: `#79817b`. Opción activa con fondo `#171c19`; la seleccionada, en `--acid`.
- Campo trampa antispam: `.booking-honeypot` (fuera de pantalla, nunca `display:none`).

### 8.5 Modal

- Capa de fondo `rgba(5,7,7,.72)`. Panel de `min(640px, 100%)`, alto máximo `min(92dvh, 720px)`.
- Fondo `linear-gradient(135deg, rgba(200,245,63,.05), transparent 40%), #101412`, borde `rgba(200,245,63,.28)` y pestaña ácida de 78×3.
- Botón de cierre de 36×36 arriba a la derecha, con borde `--line`.
- Scrollbar fina en ácido (`rgba(200,245,63,.4)` sobre `#151a17`).
- En móvil se convierte en hoja inferior: se pega abajo, sin bordes laterales, y el padding inferior respeta `env(safe-area-inset-bottom)`.

### 8.6 Acordeón (FAQ, sobre crema)

- Divisores `#cdd0c6`. Pregunta a 15px/800.
- Indicador cuadrado de 22×22 con borde `#bdc1b6` y signo en `#7e9b23`. En hover gira 90°.
- La respuesta se despliega animando `grid-template-rows: 0fr → 1fr` (.25s), sin JavaScript para la altura.

### 8.7 Paneles flotantes (cookies, aviso de idioma)

- Fondo `rgba(12,15,14,.97)` con `backdrop-filter: blur(14–18px)`.
- Cookies: abajo a la derecha, 520px, borde de acento y pestaña ácida. En móvil ocupa el ancho completo y los botones se apilan con el primario arriba (`column-reverse`).
- Idioma: abajo a la izquierda, 400px, borde `--line`. Solo aparece cuando ya se han respondido las cookies.

### 8.8 Indicador de progreso (carrusel)

Barras de 18×2px en `#363e39`. La activa se alarga a 35px y se pinta de `--acid` (transición .3s).

### 8.9 Marca (logo)

```html
<a class="brand"><img class="brand-mark" …/><span>Elo<span>peak</span></span></a>
```

15px (13px en ≤420), peso 900, `-.03em`. La segunda parte del nombre va en `--acid`. Icono de 36×36 (30 en ≤420) con `drop-shadow(0 0 12px rgba(200,245,63,.12))`.

---

## 9. Fondos y texturas

| Efecto | Receta |
|---|---|
| Fondo del hero | `radial-gradient(circle at 74% 44%, rgba(71,86,49,.15), transparent 26%), linear-gradient(115deg, #090b0c 0%, #0d1112 55%, #0a0c0c 100%)` |
| Rayas diagonales | `repeating-linear-gradient(115deg, transparent 0 160px, rgba(255,255,255,.018) 161px, transparent 162px)` |
| Cuadrícula técnica | Líneas de 1px `rgba(255,255,255,.035)` cada 76px, `opacity: .35`, con máscara horizontal `linear-gradient(to right, transparent 2%, #000 50%, transparent 98%)` |
| Halo ácido | Círculo de 360px en `--acid`, `filter: blur(120px)`, `opacity: .1` |
| Foco de página interior | `radial-gradient(circle at 65% 35%, rgba(200,245,63,.11), transparent 30%), var(--ink)` |
| CTA final | `radial-gradient(circle at 50% 50%, #202b1b, #0b0e0d 65%)` |
| Rayas de retrato | `repeating-linear-gradient(110deg, transparent 0 40px, rgba(255,255,255,.025) 41px, transparent 42px)` |
| Radar | `repeating-conic-gradient(from 0deg, rgba(255,255,255,.018) 0deg 1deg, transparent 1deg 15deg)` |

---

## 10. Movimiento

### 10.1 Curvas y duraciones

| Nombre | Curva | Duración | Uso |
|---|---|---|---|
| Snap | `cubic-bezier(.2,.75,.2,1)` | .35–.85s | Reveal, hover de tarjetas, entrada del hero |
| Out suave | `cubic-bezier(.22,1,.36,1)` | .34–.42s | Cambio de reseña, entrada de página |
| Salida | `cubic-bezier(.4,0,1,1)` | .28s | Salida de página |
| Micro | `ease` | .2–.3s | Colores, bordes, hover de botones |

### 10.2 Animaciones

| Animación | Qué hace |
|---|---|
| `[data-reveal]` → `.is-visible` | Aparece subiendo 34px (.7s, snap) al entrar en pantalla |
| `hero-copy-in` | Texto entra desde `(-28px, 18px)` en .75s |
| `hero-card-in` | Tarjeta entra desde `(32px, 16px) rotate(1deg)` en .85s con .12s de retraso |
| `page-out` / `page-in` | View Transitions entre páginas (sube 10px al salir y 12px al entrar) |
| `pulse` | Halo del punto vivo, 2s en bucle |
| `review-swap` | Cambio de reseña, sube 6px |
| Hover de tarjeta | `translateY(-4px a -8px)` y más sombra |

### 10.3 Reglas

- Los hover con desplazamiento van dentro de `@media (hover: hover) and (pointer: fine)`, para que no se queden pegados en pantallas táctiles.
- `prefers-reduced-motion: reduce` desactiva animaciones, transiciones, scroll suave y view transitions, y muestra el contenido `[data-reveal]` directamente.
- Anima solo `transform`, `opacity`, colores y sombras. Nunca `width` ni `height`, salvo el alto medido del carrusel.

---

## 11. Accesibilidad

- **Skip link** (`.skip-link`): fondo `--acid`, oculto arriba, aparece a 16px al recibir el foco.
- **`.sr-only`** para texto solo para lectores de pantalla.
- **Foco visible** siempre: `2px solid var(--acid)` con `offset 4px` en botones y enlaces, y `1px` en inputs.
- Los iconos decorativos llevan `aria-hidden="true"`. Los estados activos se marcan con `aria-current` o `aria-selected`, no solo con color.
- Objetivos táctiles de al menos 38px, y 46–48px en los controles del formulario en móvil.
- Revisa el contraste en §2.7 antes de usar un gris nuevo para texto pequeño.

---

## 12. Tokens listos para copiar

### 12.1 CSS

Los tokens actuales más los valores fijos que más se repiten, con nombre propio. Los tokens nuevos (a partir de `--acid-hover`) son una **propuesta** y aún no existen en `globals.css`.

```css
:root {
  /* Actuales */
  --ink: #080a0b;
  --ink-soft: #101315;
  --panel: #15191b;
  --panel-light: #1b2022;
  --line: rgba(255, 255, 255, 0.11);
  --text: #f4f6f1;
  --muted: #9ca39f;
  --acid: #c8f53f;
  --acid-dark: #9dbf31;
  --acid-accessible: #526814;
  --cream: #f0f0e8;
  --dark-text: #111412;

  /* Propuestos */
  --acid-hover: #d5ff55;
  --acid-link: #8ea92f;
  --acid-border: rgba(200, 245, 63, 0.22);
  --acid-border-strong: rgba(200, 245, 63, 0.48);
  --acid-glow: rgba(200, 245, 63, 0.18);
  --subtle: #7f8781;
  --field-bg: #0c0f0e;
  --field-border: #2c3430;
  --cream-card: #f7f7f1;
  --cream-line: #d1d3ca;
  --danger: #ffb4b4;

  --font-sans: var(--font-geist-sans), Arial, Helvetica, sans-serif;
  --font-mono: var(--font-geist-mono), monospace;
  --font-serif: Georgia, serif;

  --ease-snap: cubic-bezier(.2, .75, .2, 1);
  --ease-out: cubic-bezier(.22, 1, .36, 1);

  --shadow-glow: 0 12px 34px rgba(200, 245, 63, 0.18);
  --shadow-float: 0 30px 80px rgba(0, 0, 0, 0.45);
  --shadow-popover: 0 24px 75px rgba(0, 0, 0, 0.52);

  --header-h: 76px;       /* 65px en ≤640 */
  --shell-max: 1180px;
}
```

### 12.2 Tailwind v4

El proyecto ya carga Tailwind v4 (`@import "tailwindcss"`) aunque casi todo está escrito en CSS propio. Si quieres usar utilidades con la paleta de Elopeak, añade esto debajo del import:

```css
@theme inline {
  --color-ink: var(--ink);
  --color-panel: var(--panel);
  --color-line: var(--line);
  --color-text: var(--text);
  --color-muted: var(--muted);
  --color-acid: var(--acid);
  --color-acid-accessible: var(--acid-accessible);
  --color-cream: var(--cream);
  --color-dark-text: var(--dark-text);

  --font-sans: var(--font-geist-sans), Arial, Helvetica, sans-serif;
  --font-mono: var(--font-geist-mono), monospace;

  --radius-*: initial;      /* sin radios: todo recto */
  --radius-full: 9999px;

  --breakpoint-sm: 420px;
  --breakpoint-md: 640px;
  --breakpoint-lg: 900px;
}
```

Así puedes escribir `bg-ink text-acid border-line font-mono` y el resto de utilidades.

---

## 13. Lista de comprobación para una pantalla nueva

- [ ] Fondo `--ink` o `--cream`, alternando oscuro y claro entre secciones.
- [ ] Un solo color de acento. El verde ácido no se mezcla con otros acentos (salvo los colores del mapa).
- [ ] Sobre crema, el verde es `--acid-accessible`.
- [ ] Titular a peso 950 con interletrado negativo y la línea de acento en verde.
- [ ] Rótulo de sección en mayúsculas, 13px, `.19em`.
- [ ] Botones rectos en mayúsculas, con `ArrowIcon`, y como mucho un primario por bloque.
- [ ] Tarjetas destacadas con pestaña ácida.
- [ ] Sin `border-radius` salvo círculos.
- [ ] Hover con desplazamiento solo dentro de `(hover: hover) and (pointer: fine)`.
- [ ] Probado a 900, 640 y 420px, y con `prefers-reduced-motion`.
- [ ] Contraste comprobado (§2.7) y foco visible.
- [ ] «Elopeak» con E mayúscula en el texto visible.
