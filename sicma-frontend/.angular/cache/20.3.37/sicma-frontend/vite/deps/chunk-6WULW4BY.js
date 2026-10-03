import {
  G,
  r
} from "./chunk-7H6F3GR6.js";

// node_modules/@ionic/core/components/p-CG_zZq_I.js
var o = (o2, a) => {
  const i = "40px", n = "back" === a.direction, s = a.leavingEl, e = G(a.enteringEl), c = e.querySelector("ion-toolbar"), p = r();
  if (p.addElement(e).fill("both").beforeRemoveClass("ion-page-invisible"), n ? p.duration((a.duration ?? 0) || 200).easing("cubic-bezier(0.47,0,0.745,0.715)") : p.duration((a.duration ?? 0) || 280).easing("cubic-bezier(0.36,0.66,0.04,1)").fromTo("transform", `translateY(${i})`, "translateY(0px)").fromTo("opacity", 0.01, 1), c) {
    const r2 = r();
    r2.addElement(c), p.addAnimation(r2);
  }
  if (s && n) {
    p.duration((a.duration ?? 0) || 200).easing("cubic-bezier(0.47,0,0.745,0.715)");
    const o3 = r();
    o3.addElement(G(s)).onFinish(((t) => {
      1 === t && o3.elements.length > 0 && o3.elements[0].style.setProperty("display", "none");
    })).fromTo("transform", "translateY(0px)", `translateY(${i})`).fromTo("opacity", 1, 0), p.addAnimation(o3);
  }
  return p;
};

export {
  o
};
//# sourceMappingURL=chunk-6WULW4BY.js.map
