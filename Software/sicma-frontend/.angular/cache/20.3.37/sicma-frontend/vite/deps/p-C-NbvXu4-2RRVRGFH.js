import {
  e,
  t as t2
} from "./chunk-5NF7IPLD.js";
import {
  a,
  h,
  l
} from "./chunk-ZM7MIES4.js";
import {
  d as d2,
  t,
  u
} from "./chunk-GQRW365M.js";
import {
  d,
  o
} from "./chunk-FBOO75ZN.js";
import "./chunk-45K2QPHS.js";
import {
  __async
} from "./chunk-QHQP2P2Z.js";

// node_modules/@ionic/core/components/p-C-NbvXu4.js
var l2 = /* @__PURE__ */ new WeakMap();
var u2 = (o2, t3, n, i = 0, e2 = false) => {
  l2.has(o2) !== n && (n ? f(o2, t3, i, e2) : w(o2, t3));
};
var f = (o2, t3, n, i = false) => {
  const e2 = t3.parentNode, a2 = t3.cloneNode(false);
  a2.classList.add("cloned-input"), a2.tabIndex = -1, i && (a2.disabled = true);
  const r = "rtl" === o2.ownerDocument.dir;
  a2.style.insetInlineStart = r ? e2.offsetWidth - t3.offsetLeft - t3.offsetWidth + "px" : `${t3.offsetLeft}px`, e2.appendChild(a2), l2.set(o2, a2);
  const s = r ? 9999 : -9999;
  o2.style.pointerEvents = "none", t3.style.transform = `translate3d(${s}px,${n}px,0) scale(0)`;
};
var w = (o2, t3) => {
  const n = l2.get(o2);
  n && (l2.delete(o2), n.remove()), o2.style.pointerEvents = "", t3.style.transform = "";
};
var p = "input, textarea, [no-blur], [contenteditable]";
var m = "$ionPaddingTimer";
var h2 = (o2, t3, n) => {
  const i = o2[m];
  i && clearTimeout(i), t3 > 0 ? o2.style.setProperty("--keyboard-offset", `${t3}px`) : o2[m] = setTimeout((() => {
    o2.style.setProperty("--keyboard-offset", "0px"), n && n();
  }), 120);
};
var b = (o2, t3, n) => {
  o2.addEventListener("focusout", (() => {
    t3 && h2(t3, 0, n);
  }), { once: true });
};
var y = 0;
var S = "data-ionic-skip-scroll-assist";
var D = (o2) => {
  if (document.activeElement === o2) return;
  const t3 = o2.getAttribute("id"), n = o2.closest(`label[for="${t3}"]`), i = document.activeElement?.closest(`label[for="${t3}"]`);
  null !== n && n === i || (o2.setAttribute(S, "true"), o2.focus());
};
var M = (o2, t3, e2, a2, r, s, d3 = false, c = 0, l3 = true) => __async(null, null, function* () {
  if (!e2 && !a2) return;
  const f2 = ((o3, t4, n, i) => ((o4, t5, n2, i2) => {
    const e3 = o4.top, a3 = o4.bottom, r2 = t5.top, s2 = r2 + 15, d4 = Math.min(t5.bottom, i2 - n2) - 50 - a3, c2 = s2 - e3, l4 = Math.round(d4 < 0 ? -d4 : c2 > 0 ? -c2 : 0), u3 = Math.min(l4, e3 - r2), f3 = Math.abs(u3);
    return { scrollAmount: u3, scrollDuration: Math.min(400, Math.max(150, f3 / 0.3)), scrollPadding: n2, inputSafeY: 4 - (e3 - s2) };
  })((o3.closest("ion-item,[ion-item]") ?? o3).getBoundingClientRect(), t4.getBoundingClientRect(), n, i))(o2, e2 || a2, r, c);
  if (e2 && Math.abs(f2.scrollAmount) < 4) return D(t3), void (s && null !== e2 && (h2(e2, y), b(t3, e2, (() => y = 0))));
  if (u2(o2, t3, true, f2.inputSafeY, d3), D(t3), s && e2 && (y = f2.scrollPadding, h2(e2, y)), "undefined" != typeof window) {
    let a3;
    const r2 = () => __async(null, null, function* () {
      void 0 !== a3 && clearTimeout(a3), window.removeEventListener("ionKeyboardDidShow", d4), window.removeEventListener("ionKeyboardDidShow", r2), e2 && (yield h(e2, 0, f2.scrollAmount, f2.scrollDuration)), u2(o2, t3, false, f2.inputSafeY), document.activeElement === t3 && D(t3), s && b(t3, e2, (() => y = 0));
    }), d4 = () => {
      window.removeEventListener("ionKeyboardDidShow", d4), window.addEventListener("ionKeyboardDidShow", r2);
    };
    if (e2) {
      const o3 = yield a(e2);
      if (l3 && f2.scrollAmount > o3.scrollHeight - o3.clientHeight - o3.scrollTop) return "password" === t3.type ? (f2.scrollAmount += 50, window.addEventListener("ionKeyboardDidShow", d4)) : window.addEventListener("ionKeyboardDidShow", r2), void (a3 = setTimeout(r2, 1e3));
    }
    r2();
  }
});
var x = (n, i) => __async(null, null, function* () {
  if (void 0 === o) return;
  const l3 = "ios" === i, f2 = "android" === i, w2 = n.getNumber("keyboardHeight", 290), m2 = n.getBoolean("scrollAssist", true), h3 = n.getBoolean("hideCaretOnScroll", l3), b2 = n.getBoolean("inputBlurring", false), y2 = n.getBoolean("scrollPadding", true), D2 = Array.from(o.querySelectorAll("ion-input, ion-textarea")), x2 = /* @__PURE__ */ new WeakMap(), K = /* @__PURE__ */ new WeakMap(), v = yield e.getResizeMode(), k = (t3) => __async(null, null, function* () {
    yield new Promise(((o2) => t(t3, o2)));
    const n2 = t3.shadowRoot || t3, i2 = n2.querySelector("input") || n2.querySelector("textarea"), c = l(t3), l4 = c ? null : t3.closest("ion-footer");
    if (i2) {
      if (c && h3 && !x2.has(t3)) {
        const o2 = ((o3, t4, n3) => {
          if (!n3 || !t4) return () => {
          };
          const i3 = (n4) => {
            var i4;
            (i4 = t4) === i4.getRootNode().activeElement && u2(o3, t4, n4);
          }, e2 = () => u2(o3, t4, false), s = () => i3(true), d3 = () => i3(false);
          return u(n3, "ionScrollStart", s), u(n3, "ionScrollEnd", d3), t4.addEventListener("blur", e2), () => {
            d2(n3, "ionScrollStart", s), d2(n3, "ionScrollEnd", d3), t4.removeEventListener("blur", e2);
          };
        })(t3, i2, c);
        x2.set(t3, o2);
      }
      if ("date" !== i2.type && "datetime-local" !== i2.type && (c || l4) && m2 && !K.has(t3)) {
        const n3 = ((t4, n4, i3, e2, a2, r, s, c2 = false) => {
          const l5 = r && (void 0 === s || s.mode === t2.None);
          let u3 = false;
          const f3 = void 0 !== d ? d.innerHeight : 0, w3 = (o2) => {
            false !== u3 ? M(t4, n4, i3, e2, o2.detail.keyboardHeight, l5, c2, f3, false) : u3 = true;
          }, p2 = () => {
            u3 = false, d?.removeEventListener("ionKeyboardDidShow", w3), t4.removeEventListener("focusout", p2);
          }, m3 = () => __async(null, null, function* () {
            n4.hasAttribute(S) ? n4.removeAttribute(S) : (M(t4, n4, i3, e2, a2, l5, c2, f3), d?.addEventListener("ionKeyboardDidShow", w3), t4.addEventListener("focusout", p2));
          });
          return t4.addEventListener("focusin", m3), () => {
            t4.removeEventListener("focusin", m3), d?.removeEventListener("ionKeyboardDidShow", w3), t4.removeEventListener("focusout", p2);
          };
        })(t3, i2, c, l4, w2, y2, v, f2);
        K.set(t3, n3);
      }
    }
  });
  b2 && (() => {
    let o2 = true, t3 = false;
    const n2 = document;
    u(n2, "ionScrollStart", (() => {
      t3 = true;
    })), n2.addEventListener("focusin", (() => {
      o2 = true;
    }), true), n2.addEventListener("touchend", ((i2) => {
      if (t3) return void (t3 = false);
      const e2 = n2.activeElement;
      if (!e2) return;
      if (e2.matches(p)) return;
      const a2 = i2.target;
      a2 !== e2 && (a2.matches(p) || a2.closest(p) || (o2 = false, setTimeout((() => {
        o2 || e2.blur();
      }), 50)));
    }), false);
  })();
  for (const o2 of D2) k(o2);
  o.addEventListener("ionInputDidLoad", ((o2) => {
    k(o2.detail);
  })), o.addEventListener("ionInputDidUnload", ((o2) => {
    ((o3) => {
      if (h3) {
        const t3 = x2.get(o3);
        t3 && t3(), x2.delete(o3);
      }
      if (m2) {
        const t3 = K.get(o3);
        t3 && t3(), K.delete(o3);
      }
    })(o2.detail);
  }));
});
export {
  x as startInputShims
};
//# sourceMappingURL=p-C-NbvXu4-2RRVRGFH.js.map
