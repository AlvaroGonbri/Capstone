import {
  x
} from "./chunk-GQRW365M.js";
import {
  o
} from "./chunk-FBOO75ZN.js";
import "./chunk-45K2QPHS.js";
import "./chunk-QHQP2P2Z.js";

// node_modules/@ionic/core/components/p-BQyuFxYc.js
var o2 = (o3) => {
  if (void 0 === o) return;
  let s, p, u, l = 0;
  const d = o3.getBoolean("animated", true) && o3.getBoolean("rippleEffect", true), v = /* @__PURE__ */ new WeakMap(), m = () => {
    u && clearTimeout(u), u = void 0, s && (b(false), s = void 0);
  }, T = (t, o4) => {
    if (t && t === s) return;
    u && clearTimeout(u), u = void 0;
    const { x: i2, y: r2 } = x(o4);
    if (s) {
      if (v.has(s)) throw new Error("internal error");
      s.classList.contains(a) || w(s, i2, r2), b(true);
    }
    if (t) {
      const e = v.get(t);
      e && (clearTimeout(e), v.delete(t)), t.classList.remove(a);
      const o5 = () => {
        w(t, i2, r2), u = void 0;
      };
      n(t) ? o5() : u = setTimeout(o5, c);
    }
    s = t;
  }, w = (t, e, o4) => {
    if (l = Date.now(), t.classList.add(a), !d) return;
    const i2 = r(t);
    null !== i2 && (j(), p = i2.addRipple(e, o4));
  }, j = () => {
    void 0 !== p && (p.then(((t) => t())), p = void 0);
  }, b = (t) => {
    j();
    const e = s;
    if (!e) return;
    const o4 = f - Date.now() + l;
    if (t && o4 > 0 && !n(e)) {
      const t2 = setTimeout((() => {
        e.classList.remove(a), v.delete(e);
      }), f);
      v.set(e, t2);
    } else e.classList.remove(a);
  };
  o.addEventListener("ionGestureCaptured", m), o.addEventListener("pointerdown", ((t) => {
    s || 2 === t.button || T(i(t), t);
  }), true), o.addEventListener("pointerup", ((t) => {
    T(void 0, t);
  }), true), o.addEventListener("pointercancel", m, true);
};
var i = (t) => {
  if (void 0 === t.composedPath) return t.target.closest(".ion-activatable");
  {
    const e = t.composedPath();
    for (let t2 = 0; t2 < e.length - 2; t2++) {
      const o3 = e[t2];
      if (!(o3 instanceof ShadowRoot) && o3.classList.contains("ion-activatable")) return o3;
    }
  }
};
var n = (t) => t.classList.contains("ion-activatable-instant");
var r = (t) => {
  if (t.shadowRoot) {
    const e = t.shadowRoot.querySelector("ion-ripple-effect");
    if (e) return e;
  }
  return t.querySelector("ion-ripple-effect");
};
var a = "ion-activated";
var c = 100;
var f = 150;
export {
  o2 as startTapClick
};
//# sourceMappingURL=p-BQyuFxYc-IU4VNMEO.js.map
