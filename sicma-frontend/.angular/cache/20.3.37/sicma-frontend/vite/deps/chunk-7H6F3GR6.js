import {
  m
} from "./chunk-GQRW365M.js";
import {
  d as d2
} from "./chunk-FBOO75ZN.js";
import {
  J,
  a,
  d,
  n,
  v
} from "./chunk-45K2QPHS.js";
import {
  __async
} from "./chunk-QHQP2P2Z.js";

// node_modules/@ionic/core/components/p-DFLJvuRK.js
var t;
var i = (e, o, i2) => {
  const n3 = o.startsWith("animation") ? (r3 = e, void 0 === t && (t = void 0 === r3.style.animationName && void 0 !== r3.style.webkitAnimationName ? "-webkit-" : ""), t) : "";
  var r3;
  e.style.setProperty(n3 + o, i2);
};
var n2 = (e = [], o) => {
  if (void 0 !== o) {
    const t3 = Array.isArray(o) ? o : [o];
    return [...e, ...t3];
  }
  return e;
};
var r = (t3) => {
  let r3, a2, s2, d4, f2, l2, c2, v3, m3, u2, p2, y2 = [], g2 = [], A2 = [], b2 = false, C2 = {}, E2 = [], h2 = [], S = {}, j2 = 0, k2 = false, R = false, w2 = true, D2 = false, T = true, F = false;
  const P2 = t3, W2 = [], Z = [], I = [], K = [], M2 = [], x = [], J2 = [], q = [], z2 = [], B = [], G2 = [], H = "function" == typeof AnimationEffect || void 0 !== d2 && "function" == typeof d2.AnimationEffect, L2 = "function" == typeof Element && "function" == typeof Element.prototype.animate && H, N = () => G2, O = (e, o) => {
    const t4 = o.findIndex(((o2) => o2.c === e));
    t4 > -1 && o.splice(t4, 1);
  }, Q = (e, o) => ((o?.oneTimeCallback ? Z : W2).push({ c: e, o }), p2), U2 = () => {
    L2 && (G2.forEach(((e) => {
      e.cancel();
    })), G2.length = 0);
  }, V2 = () => {
    x.forEach(((e) => {
      e?.parentNode && e.parentNode.removeChild(e);
    })), x.length = 0;
  }, X = () => void 0 !== f2 ? f2 : c2 ? c2.getFill() : "both", Y = () => void 0 !== v3 ? v3 : void 0 !== l2 ? l2 : c2 ? c2.getDirection() : "normal", $ = () => k2 ? "linear" : void 0 !== s2 ? s2 : c2 ? c2.getEasing() : "linear", _ = () => R ? 0 : void 0 !== m3 ? m3 : void 0 !== a2 ? a2 : c2 ? c2.getDuration() : 0, ee = () => void 0 !== d4 ? d4 : c2 ? c2.getIterations() : 1, oe = () => void 0 !== u2 ? u2 : void 0 !== r3 ? r3 : c2 ? c2.getDelay() : 0, te = () => {
    0 !== j2 && (j2--, 0 === j2 && ((() => {
      z2.forEach(((e2) => e2())), B.forEach(((e2) => e2()));
      const e = w2 ? 1 : 0, o = E2, t4 = h2, n3 = S;
      K.forEach(((e2) => {
        const r4 = e2.classList;
        o.forEach(((e3) => r4.add(e3))), t4.forEach(((e3) => r4.remove(e3)));
        for (const o2 in n3) n3.hasOwnProperty(o2) && i(e2, o2, n3[o2]);
      })), m3 = void 0, v3 = void 0, u2 = void 0, W2.forEach(((o2) => o2.c(e, p2))), Z.forEach(((o2) => o2.c(e, p2))), Z.length = 0, T = true, w2 && (D2 = true), w2 = true;
    })(), c2 && c2.animationFinish()));
  }, ie = () => {
    (() => {
      J2.forEach(((e2) => e2())), q.forEach(((e2) => e2()));
      const e = g2, o = A2, t4 = C2;
      K.forEach(((n3) => {
        const r4 = n3.classList;
        e.forEach(((e2) => r4.add(e2))), o.forEach(((e2) => r4.remove(e2)));
        for (const e2 in t4) t4.hasOwnProperty(e2) && i(n3, e2, t4[e2]);
      }));
    })(), y2.length > 0 && L2 && (K.forEach(((e) => {
      const o = e.animate(y2, { id: P2, delay: oe(), duration: _(), easing: $(), iterations: ee(), fill: X(), direction: Y() });
      o.pause(), G2.push(o);
    })), G2.length > 0 && (G2[0].onfinish = () => {
      te();
    })), b2 = true;
  }, ne = (e) => {
    e = Math.min(Math.max(e, 0), 0.9999), L2 && G2.forEach(((o) => {
      o.currentTime = o.effect.getComputedTiming().delay + _() * e, o.pause();
    }));
  }, re = (e) => {
    G2.forEach(((e2) => {
      e2.effect.updateTiming({ delay: oe(), duration: _(), easing: $(), iterations: ee(), fill: X(), direction: Y() });
    })), void 0 !== e && ne(e);
  }, ae = (e = false, o = true, t4) => (e && M2.forEach(((i2) => {
    i2.update(e, o, t4);
  })), L2 && re(t4), p2), se = () => {
    b2 && (L2 ? G2.forEach(((e) => {
      e.pause();
    })) : K.forEach(((e) => {
      i(e, "animation-play-state", "paused");
    })), F = true);
  }, de = (e) => new Promise(((o) => {
    e?.sync && (R = true, Q((() => R = false), { oneTimeCallback: true })), b2 || ie(), D2 && (L2 && (ne(0), re()), D2 = false), T && (j2 = M2.length + 1, T = false);
    const t4 = () => {
      O(i2, Z), o();
    }, i2 = () => {
      O(t4, I), o();
    };
    Q(i2, { oneTimeCallback: true }), I.push({ c: t4, o: { oneTimeCallback: true } }), M2.forEach(((e2) => {
      e2.play();
    })), L2 ? (G2.forEach(((e2) => {
      e2.play();
    })), 0 !== y2.length && 0 !== K.length || te()) : te(), F = false;
  })), fe = (e, o) => {
    const t4 = y2[0];
    return void 0 === t4 || void 0 !== t4.offset && 0 !== t4.offset ? y2 = [{ offset: 0, [e]: o }, ...y2] : t4[e] = o, p2;
  };
  return p2 = { parentAnimation: c2, elements: K, childAnimations: M2, id: P2, animationFinish: te, from: fe, to: (e, o) => {
    const t4 = y2[y2.length - 1];
    return void 0 === t4 || void 0 !== t4.offset && 1 !== t4.offset ? y2 = [...y2, { offset: 1, [e]: o }] : t4[e] = o, p2;
  }, fromTo: (e, o, t4) => fe(e, o).to(e, t4), parent: (e) => (c2 = e, p2), play: de, pause: () => (M2.forEach(((e) => {
    e.pause();
  })), se(), p2), stop: () => {
    M2.forEach(((e) => {
      e.stop();
    })), b2 && (U2(), b2 = false), k2 = false, R = false, T = true, v3 = void 0, m3 = void 0, u2 = void 0, j2 = 0, D2 = false, w2 = true, F = false, I.forEach(((e) => e.c(0, p2))), I.length = 0;
  }, destroy: (e) => (M2.forEach(((o) => {
    o.destroy(e);
  })), ((e2) => {
    U2(), e2 && V2();
  })(e), K.length = 0, M2.length = 0, y2.length = 0, W2.length = 0, Z.length = 0, b2 = false, T = true, p2), keyframes: (e) => {
    const o = y2 !== e;
    return y2 = e, o && ((e2) => {
      L2 && N().forEach(((o2) => {
        const t4 = o2.effect;
        if (t4.setKeyframes) t4.setKeyframes(e2);
        else {
          const i2 = new KeyframeEffect(t4.target, e2, t4.getTiming());
          o2.effect = i2;
        }
      }));
    })(y2), p2;
  }, addAnimation: (e) => {
    if (null != e) if (Array.isArray(e)) for (const o of e) o.parent(p2), M2.push(o);
    else e.parent(p2), M2.push(e);
    return p2;
  }, addElement: (o) => {
    if (null != o) if (1 === o.nodeType) K.push(o);
    else if (o.length >= 0) for (let e = 0; e < o.length; e++) K.push(o[e]);
    else d("createAnimation - Invalid addElement value.");
    return p2;
  }, update: ae, fill: (e) => (f2 = e, ae(true), p2), direction: (e) => (l2 = e, ae(true), p2), iterations: (e) => (d4 = e, ae(true), p2), duration: (e) => (L2 || 0 !== e || (e = 1), a2 = e, ae(true), p2), easing: (e) => (s2 = e, ae(true), p2), delay: (e) => (r3 = e, ae(true), p2), getWebAnimations: N, getKeyframes: () => y2, getFill: X, getDirection: Y, getDelay: oe, getIterations: ee, getEasing: $, getDuration: _, afterAddRead: (e) => (z2.push(e), p2), afterAddWrite: (e) => (B.push(e), p2), afterClearStyles: (e = []) => {
    for (const o of e) S[o] = "";
    return p2;
  }, afterStyles: (e = {}) => (S = e, p2), afterRemoveClass: (e) => (h2 = n2(h2, e), p2), afterAddClass: (e) => (E2 = n2(E2, e), p2), beforeAddRead: (e) => (J2.push(e), p2), beforeAddWrite: (e) => (q.push(e), p2), beforeClearStyles: (e = []) => {
    for (const o of e) C2[o] = "";
    return p2;
  }, beforeStyles: (e = {}) => (C2 = e, p2), beforeRemoveClass: (e) => (A2 = n2(A2, e), p2), beforeAddClass: (e) => (g2 = n2(g2, e), p2), onFinish: Q, isRunning: () => 0 !== j2 && !F, progressStart: (e = false, o) => (M2.forEach(((t4) => {
    t4.progressStart(e, o);
  })), se(), k2 = e, b2 || ie(), ae(false, true, o), p2), progressStep: (e) => (M2.forEach(((o) => {
    o.progressStep(e);
  })), ne(e), p2), progressEnd: (e, o, t4) => (k2 = false, M2.forEach(((i2) => {
    i2.progressEnd(e, o, t4);
  })), void 0 !== t4 && (m3 = t4), D2 = false, w2 = true, 0 === e ? (v3 = "reverse" === Y() ? "normal" : "reverse", "reverse" === v3 && (w2 = false), L2 ? (ae(), ne(1 - o)) : (u2 = (1 - o) * _() * -1, ae(false, false))) : 1 === e && (L2 ? (ae(), ne(o)) : (u2 = o * _() * -1, ae(false, false))), void 0 === e || c2 || de(), p2) };
};

// node_modules/@ionic/core/components/p-C4VpVfrJ.js
var r2 = "ionViewWillEnter";
var t2 = "ionViewDidEnter";
var s = "ionViewWillLeave";
var c = "ionViewDidLeave";
var l = "ionViewWillUnload";
var u = (n3) => {
  n3.tabIndex = -1, n3.focus();
};
var d3 = (n3) => null !== n3.offsetParent;
var f = "ion-last-focus";
var p = (e) => {
  if (n.get("focusManagerPriority", false)) {
    const n3 = document.activeElement;
    null !== n3 && e?.contains(n3) && n3.setAttribute(f, "true");
  }
};
var w = (i2) => {
  const a2 = n.get("focusManagerPriority", false);
  if (Array.isArray(a2) && !i2.contains(document.activeElement)) {
    const n3 = i2.querySelector(`[${f}]`);
    if (n3 && d3(n3)) return void u(n3);
    for (const n4 of a2) switch (n4) {
      case "content":
        const a3 = i2.querySelector('main, [role="main"]');
        if (a3 && d3(a3)) return void u(a3);
        break;
      case "heading":
        const o = i2.querySelector('h1, [role="heading"][aria-level="1"]');
        if (o && d3(o)) return void u(o);
        break;
      case "banner":
        const r3 = i2.querySelector('header, [role="banner"]');
        if (r3 && d3(r3)) return void u(r3);
        break;
      default:
        a(`Unrecognized focus manager priority value ${n4}`);
    }
    u(i2);
  }
};
var v2 = (n3) => new Promise(((e, a2) => {
  J((() => {
    const i2 = U(n3);
    m2(n3, i2), b(n3).then(((i3) => {
      i3.animation && i3.animation.destroy(), g(n3), e(i3);
    }), ((e2) => {
      g(n3), a2(e2);
    })).finally((() => {
      A(i2, false);
    }));
  }));
}));
var m2 = (n3, e) => {
  const i2 = n3.enteringEl, a2 = n3.leavingEl;
  p(a2), z(i2, a2, n3.direction), A(e, true), n3.showGoBack ? i2.classList.add("can-go-back") : i2.classList.remove("can-go-back"), W(i2, false), i2.style.setProperty("pointer-events", "none"), a2 && (W(a2, false), a2.style.setProperty("pointer-events", "none"));
};
var b = (n3) => __async(null, null, function* () {
  const e = yield h(n3);
  return e && v.isBrowser ? y(e, n3) : P(n3);
});
var g = (n3) => {
  const e = n3.enteringEl, i2 = n3.leavingEl;
  e.classList.remove("ion-page-invisible"), e.style.removeProperty("pointer-events"), void 0 !== i2 && (i2.classList.remove("ion-page-invisible"), i2.style.removeProperty("pointer-events")), w(e);
};
var h = (n3) => __async(null, null, function* () {
  if (n3.leavingEl && n3.animated && 0 !== n3.duration) return n3.animationBuilder ? n3.animationBuilder : "ios" === n3.mode ? (yield import("./p-5ldEpNdG-ESDHC4FV.js")).iosTransitionAnimation : (yield import("./p-CG_zZq_I-73HDAIIU.js")).mdTransitionAnimation;
});
var y = (n3, e) => __async(null, null, function* () {
  yield k(e, true);
  const i2 = n3(e.baseEl, e);
  j(e.enteringEl, e.leavingEl);
  const a2 = yield V(i2, e);
  return e.progressCallback && e.progressCallback(void 0), a2 && E(e.enteringEl, e.leavingEl), { hasCompleted: a2, animation: i2 };
});
var P = (e) => __async(null, null, function* () {
  const i2 = e.enteringEl, a2 = e.leavingEl, o = n.get("focusManagerPriority", false);
  return yield k(e, o), j(i2, a2), E(i2, a2), { hasCompleted: true };
});
var k = (n3, e) => __async(null, null, function* () {
  (void 0 !== n3.deepWait ? n3.deepWait : e) && (yield Promise.all([M(n3.enteringEl), M(n3.leavingEl)])), yield C(n3.viewIsReady, n3.enteringEl);
});
var C = (n3, e) => __async(null, null, function* () {
  n3 && (yield n3(e));
});
var V = (n3, e) => {
  const i2 = e.progressCallback, a2 = new Promise(((e2) => {
    n3.onFinish(((n4) => e2(1 === n4)));
  }));
  return i2 ? (n3.progressStart(true), i2(n3)) : n3.play(), a2;
};
var j = (n3, e) => {
  D(e, s), D(n3, r2);
};
var E = (n3, e) => {
  D(n3, t2), D(e, c);
};
var D = (n3, e) => {
  if (n3) {
    const i2 = new CustomEvent(e, { bubbles: false, cancelable: false });
    n3.dispatchEvent(i2);
  }
};
var L = () => new Promise(((n3) => m((() => m((() => n3()))))));
var M = (n3) => __async(null, null, function* () {
  const e = n3;
  if (e) {
    if (null != e.componentOnReady) {
      if (null != (yield e.componentOnReady())) return;
    } else if (null != e.__registerHost) {
      const n4 = new Promise(((n5) => m(n5)));
      return void (yield n4);
    }
    yield Promise.all(Array.from(e.children).map(M));
  }
});
var W = (n3, e) => {
  e ? (n3.setAttribute("aria-hidden", "true"), n3.classList.add("ion-page-hidden")) : (n3.hidden = false, n3.removeAttribute("aria-hidden"), n3.classList.remove("ion-page-hidden"));
};
var z = (n3, e, i2) => {
  void 0 !== n3 && (n3.style.zIndex = "back" === i2 ? "99" : "101"), void 0 !== e && (e.style.zIndex = "100");
};
var A = (n3, e) => {
  if (!n3) return;
  const i2 = "header-transitioning";
  e ? n3.classList.add(i2) : n3.classList.remove(i2);
};
var G = (n3) => {
  if (n3.classList.contains("ion-page")) return n3;
  return n3.querySelector(":scope > .ion-page, :scope > ion-nav, :scope > ion-tabs") || n3;
};
var U = (n3) => {
  if ("ios" !== n3.mode) return null;
  const e = "back" === n3.direction ? n3.leavingEl : n3.enteringEl;
  return e ? e.querySelector("ion-header") : null;
};

export {
  r,
  r2,
  t2 as t,
  s,
  c,
  l,
  v2 as v,
  D,
  L,
  M,
  W,
  G
};
//# sourceMappingURL=chunk-7H6F3GR6.js.map
