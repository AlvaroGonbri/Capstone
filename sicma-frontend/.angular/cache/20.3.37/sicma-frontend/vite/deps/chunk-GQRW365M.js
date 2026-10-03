import {
  d
} from "./chunk-45K2QPHS.js";

// node_modules/@ionic/core/components/p-Dojwmvde.js
var r = (r3) => {
  for (let t2 = r3; t2; t2 = t2.parentElement) {
    const r4 = t2.getAttribute("dir")?.toLowerCase();
    if ("rtl" === r4) return true;
    if ("ltr" === r4) return false;
  }
  return "rtl" === document?.dir?.toLowerCase();
};

// node_modules/@ionic/core/components/p-C09TXohi.js
var r2 = (a, i = 0) => new Promise(((r3) => {
  e(a, i, r3);
}));
var e = (a, i = 0, r3) => {
  let e2, t2;
  const n2 = { passive: true }, o2 = () => {
    e2 && e2();
  }, s2 = (i2) => {
    void 0 !== i2 && a !== i2.target || (o2(), r3(i2));
  };
  return a && (a.addEventListener("webkitTransitionEnd", s2, n2), a.addEventListener("transitionend", s2, n2), t2 = setTimeout(s2, i + 500), e2 = () => {
    void 0 !== t2 && (clearTimeout(t2), t2 = void 0), a.removeEventListener("webkitTransitionEnd", s2, n2), a.removeEventListener("transitionend", s2, n2);
  }), o2;
};
var t = (a, i) => {
  a.componentOnReady ? a.componentOnReady().then(((a2) => i(a2))) : m((() => i(a)));
};
var n = (a) => void 0 !== a.componentOnReady;
var o = (a, i = []) => {
  const r3 = {};
  return i.forEach(((i2) => {
    a.hasAttribute(i2) && (null !== a.getAttribute(i2) && (r3[i2] = a.getAttribute(i2)), a.removeAttribute(i2));
  })), r3;
};
var s = ["role", "aria-activedescendant", "aria-atomic", "aria-autocomplete", "aria-braillelabel", "aria-brailleroledescription", "aria-busy", "aria-checked", "aria-colcount", "aria-colindex", "aria-colindextext", "aria-colspan", "aria-controls", "aria-current", "aria-describedby", "aria-description", "aria-details", "aria-disabled", "aria-errormessage", "aria-expanded", "aria-flowto", "aria-haspopup", "aria-hidden", "aria-invalid", "aria-keyshortcuts", "aria-label", "aria-labelledby", "aria-level", "aria-live", "aria-multiline", "aria-multiselectable", "aria-orientation", "aria-owns", "aria-placeholder", "aria-posinset", "aria-pressed", "aria-readonly", "aria-relevant", "aria-required", "aria-roledescription", "aria-rowcount", "aria-rowindex", "aria-rowindextext", "aria-rowspan", "aria-selected", "aria-setsize", "aria-sort", "aria-valuemax", "aria-valuemin", "aria-valuenow", "aria-valuetext"];
var l = (a) => o(a, s);
var u = (a, i, r3, e2) => a.addEventListener(i, r3, e2);
var d2 = (a, i, r3, e2) => a.removeEventListener(i, r3, e2);
var c = (a, i = a) => a.shadowRoot || i;
var m = (a) => "function" == typeof __zone_symbol__requestAnimationFrame ? __zone_symbol__requestAnimationFrame(a) : "function" == typeof requestAnimationFrame ? requestAnimationFrame(a) : setTimeout(a);
var p = (a) => !!a.shadowRoot && !!a.attachShadow;
var f = (a) => {
  if (a.focus(), a.classList.contains("ion-focusable")) {
    const i = a.closest("ion-app");
    i && i.setFocus([a]);
  }
};
var b = (a, i, r3, e2, t2) => {
  {
    let a2 = i.querySelector("input.aux-input");
    a2 || (a2 = i.ownerDocument.createElement("input"), a2.type = "hidden", a2.classList.add("aux-input"), i.appendChild(a2)), a2.disabled = t2, a2.name = r3, a2.value = e2 || "";
  }
};
var v = (a, i, r3) => Math.max(a, Math.min(i, r3));
var w = (i, r3) => {
  if (!i) {
    const i2 = "ASSERT: " + r3;
    throw d(i2), new Error(i2);
  }
};
var x = (a) => {
  if (a) {
    const i = a.changedTouches;
    if (i && i.length > 0) {
      const a2 = i[0];
      return { x: a2.clientX, y: a2.clientY };
    }
    if (void 0 !== a.pageX) return { x: a.pageX, y: a.pageY };
  }
  return { x: 0, y: 0 };
};
var y = (a, r3) => {
  const e2 = r(r3);
  switch (a) {
    case "start":
      return e2;
    case "end":
      return !e2;
    default:
      throw new Error(`"${a}" is not a valid value for [side]. Use "start" or "end" instead.`);
  }
};
var h = (a, i) => {
  const r3 = a._original || a;
  return { _original: a, emit: _(r3.emit.bind(r3), i) };
};
var _ = (a, i = 0) => {
  let r3;
  return (...e2) => {
    clearTimeout(r3), r3 = setTimeout(a, i, ...e2);
  };
};
var T = (a, i) => {
  if (a ??= {}, i ??= {}, a === i) return true;
  const r3 = Object.keys(a);
  if (r3.length !== Object.keys(i).length) return false;
  for (const e2 of r3) {
    if (!(e2 in i)) return false;
    if (a[e2] !== i[e2]) return false;
  }
  return true;
};
var j = (a) => "number" == typeof a && !isNaN(a) && isFinite(a);

export {
  r,
  r2,
  t,
  n,
  o,
  l,
  u,
  d2 as d,
  c,
  m,
  p,
  f,
  b,
  v,
  w,
  x,
  y,
  h,
  T,
  j
};
//# sourceMappingURL=chunk-GQRW365M.js.map
